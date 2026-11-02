from pathlib import Path
import json
import re
import csv

from bs4 import BeautifulSoup
from content_scope import select_scope
from review_source import marked_source


ROOT = Path(__file__).resolve().parent
INPUT_DIR = ROOT / "samples"
OUTPUT_DIR = ROOT / "output"


def prepare_html(html: str) -> str:
    """Expose captured declarative shadow text to static parsers on a copy.

    This is not browser slot composition or a visibility calculation.
    """
    soup = BeautifulSoup(html, "lxml")
    for template in list(soup.find_all("template")):
        if template.parent is None:
            continue
        if template.get("shadowrootmode") in {"open", "closed"}:
            template.unwrap()
        else:
            template.decompose()
    # Reparse serialized markup to turn BeautifulSoup TemplateString into text.
    return str(soup)


def clean_text(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()


NOISE_WORDS = re.compile(
    r"(nav|menu|header|footer|sidebar|side-bar|aside|advert|(?<![a-z])ad[-_]|banner|recommend|related|comment|share|login|register|breadcrumb|copyright)",
    re.I,
)


def classify_region(node, text: str) -> tuple[str, str]:
    tag = node.name.lower()
    # A topic landing-page link can sit inside the editorial article container.
    # Require a link-only paragraph; do not discard narrative mentioning a topic.
    links = node.find_all('a', href=True)
    if tag == 'p' and text.startswith('专题：') and len(links) == 1 and clean_text(links[0].get_text(' ', strip=True)) == text:
        return '杂质', '正文容器内的专题聚合链接，不是叙述正文'
    # Inspect containers too: a long paragraph inside navigation is still navigation.
    for ancestor in [node, *node.parents]:
        if ancestor.name in {"body", "html", "[document]"}:
            break
        identity = " ".join([str(ancestor.get("id", "")), " ".join(ancestor.get("class", []))])
        if ancestor.name == "header" and not ancestor.find_parent(["article", "main"]):
            return "杂质", "文章容器之外的站点页头"
        if NOISE_WORDS.search(identity) or ancestor.name in {"nav", "footer", "aside", "form"} or ancestor.get("role") in {"navigation", "complementary", "contentinfo"}:
            return "杂质", "当前节点或祖先容器显示为导航、广告、侧栏等"
    if tag in {"article", "main"}:
        return "正文候选", "语义标签为 article/main"
    if tag in {"h1", "h2", "h3"}:
        return "标题/小标题", "标题标签"
    if len(text) >= 80:
        return "正文候选", "文本较长且未命中明显噪声标识"
    return "待判断", "短文本或缺少明确区域信号"


def collect_regions(soup, scope=None):
    regions = []
    roots, page_type, method, warnings = scope or ([], 'unknown', '', [])
    inside = {id(n) for root in roots for n in [root, *root.descendants] if getattr(n, 'name', None)}
    # 以段落、标题和列表项为最小可读区域，避免输出整个 body 的巨量重复文本。
    for node in soup.find_all(["h1", "h2", "h3", "p", "li", "article", "main", "section", "div"]):
        if node.find_parent(["script", "style"]):
            continue
        if node.find(["p", "h1", "h2", "h3", "li"]):
            continue
        text = clean_text(node.get_text(" ", strip=True))
        if not text:
            continue
        auto_label, reason = classify_region(node, text)
        if page_type == 'listing':
            auto_label, reason = '杂质', '列表/目录页，不作为单篇文章正文'
        elif roots and id(node) not in inside:
            auto_label, reason = '杂质', '目标文章正文容器之外'
        elif method in {'ambiguous_articles', 'ambiguous_consumption_pages'}:
            auto_label, reason = '待判断', '多篇文章无法唯一选择目标'
        elif roots and auto_label != '杂质':
            if (node.name == 'h1'
                    or re.match(r'^(责任编辑[：:]|来源[：:]|作者[：:]|[（(](?:声明|文章来源)[：:])', text)
                    or re.fullmatch(r'(?:21世纪经济报道)?记者[ ：:]+[\u4e00-\u9fff·、 ]{2,20}', text)):
                auto_label, reason = '元数据', '文章标题、署名或声明单列'
            elif node.name in {'p', 'li', 'h2', 'h3', 'blockquote', 'pre'}:
                auto_label, reason = '正文候选', '目标正文容器内的段落/列表/小标题，不设80字门槛'
        regions.append({
            "region_id": len(regions) + 1,
            "source_node": node.get('data-review-node'),
            "tag": node.name,
            "id": node.get("id", ""),
            "class": " ".join(node.get("class", [])),
            "text": text,
            "auto_label": auto_label,
            "manual_label": "",
            "reason": reason,
        })
    # Remove only contiguous production credits at the end of narrative.
    for region in reversed(regions):
        if region['auto_label'] not in {'正文候选', '标题/小标题'}:
            continue
        if re.fullmatch(r'[｜|]\s*(?:(?:总策划|策划|统筹|执笔|审校|视觉)[：:]\s*[^。！？]{1,50}|[^。！？]{1,60}出品)', region['text']):
            region['auto_label'] = '元数据'
            region['reason'] = '正文末尾连续制作署名'
        else:
            break
    return regions


def extract_file(path: Path) -> dict:
    html = path.read_text(encoding="utf-8", errors="ignore")
    soup = BeautifulSoup(prepare_html(str(marked_source(html))), "lxml")

    for tag in soup(["script", "style"]):
        tag.decompose()

    title = clean_text(soup.title.get_text(" ", strip=True)) if soup.title else ""
    scope = select_scope(soup, title)
    regions = collect_regions(soup, scope)
    content = "\n".join(r["text"] for r in regions if r["auto_label"] in {"正文候选", "标题/小标题"})
    images = []
    seen_images = set()
    for root in scope[0]:
        for image in root.find_all('img'):
            if any(parent.name in {'aside', 'footer', 'nav'} or NOISE_WORDS.search(
                    ' '.join([str(parent.get('id', '')), ' '.join(parent.get('class', []))]))
                   for parent in [image, *image.parents] if getattr(parent, 'name', None)):
                continue
            src = image.get('data-src') or image.get('data-original') or image.get('src')
            if src and src not in seen_images:
                seen_images.add(src)
                images.append({'src': src, 'alt': image.get('alt', '')})
    warnings = list(scope[3])
    if images:
        warnings.append('正文范围包含图片；当前仅提取 DOM 文本，未识别图片中的文字。')
    ocr_candidate = len(images) >= 3 and len(content) < 300
    if ocr_candidate:
        warnings.append('图片较多且文本较少，疑似图片正文，需要 OCR 或图像审核。')
    return {"file": path.name, "title": title, "regions": regions,
            "content": content, "content_length": len(content),
            "page_type":scope[1], "scope_method":scope[2], "warnings":warnings,
            "body_images": images, "needs_ocr_candidate": ocr_candidate,
            "content_completeness": 'image_content_unverified' if images else 'text_only_not_independently_verified',
            "extraction_status":'not_article' if scope[1] == 'listing' else 'ok' if content else 'empty_body'}


def main() -> None:
    OUTPUT_DIR.mkdir(exist_ok=True)
    results = []
    for path in sorted(INPUT_DIR.glob("*.html")):
        try:
            results.append(extract_file(path))
            print(f"[OK] {path.name}")
        except Exception as exc:
            results.append({"file": path.name, "error": str(exc)})
            print(f"[ERROR] {path.name}: {exc}")

    output = OUTPUT_DIR / "results.json"
    output.write_text(json.dumps(results, ensure_ascii=False, indent=2), encoding="utf-8")
    review = ROOT / "reports" / "region_review.csv"
    review.parent.mkdir(exist_ok=True)
    with review.open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=["file", "region_id", "auto_label", "manual_label", "tag", "id", "class", "text", "reason", "source_node"])
        writer.writeheader()
        for item in results:
            for region in item.get("regions", []):
                writer.writerow({"file": item["file"], **region})
    print(f"结果已保存到: {output}")
    print(f"区域复核表已保存到: {review}")


if __name__ == "__main__":
    main()
