from pathlib import Path
import json
import re
import csv

from bs4 import BeautifulSoup


ROOT = Path(__file__).resolve().parent
INPUT_DIR = ROOT / "samples"
OUTPUT_DIR = ROOT / "output"


def clean_text(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()


NOISE_WORDS = re.compile(
    r"(nav|menu|header|footer|sidebar|side-bar|aside|advert|ad-|banner|recommend|related|comment|share|login|register|breadcrumb|copyright)",
    re.I,
)


def classify_region(node, text: str) -> tuple[str, str]:
    tag = node.name.lower()
    identity = " ".join([str(node.get("id", "")), " ".join(node.get("class", []))])
    if NOISE_WORDS.search(identity) or tag in {"nav", "header", "footer", "aside", "form"}:
        return "杂质", "标签或id/class显示为导航、广告、侧栏等"
    if tag in {"article", "main"}:
        return "正文候选", "语义标签为 article/main"
    if tag in {"h1", "h2", "h3"}:
        return "标题/小标题", "标题标签"
    if len(text) >= 80:
        return "正文候选", "文本较长且未命中明显噪声标识"
    return "待判断", "短文本或缺少明确区域信号"


def collect_regions(soup):
    regions = []
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
        regions.append({
            "region_id": len(regions) + 1,
            "tag": node.name,
            "id": node.get("id", ""),
            "class": " ".join(node.get("class", [])),
            "text": text,
            "auto_label": auto_label,
            "manual_label": "",
            "reason": reason,
        })
    return regions


def extract_file(path: Path) -> dict:
    html = path.read_text(encoding="utf-8", errors="ignore")
    soup = BeautifulSoup(html, "lxml")

    for tag in soup(["script", "style"]):
        tag.decompose()

    title = clean_text(soup.title.get_text(" ", strip=True)) if soup.title else ""
    regions = collect_regions(soup)
    content = "\n".join(r["text"] for r in regions if r["auto_label"] in {"正文候选", "标题/小标题"})
    return {"file": path.name, "title": title, "regions": regions,
            "content": content, "content_length": len(content)}


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
        writer = csv.DictWriter(f, fieldnames=["file", "region_id", "auto_label", "manual_label", "tag", "id", "class", "text", "reason"])
        writer.writeheader()
        for item in results:
            for region in item.get("regions", []):
                writer.writerow({"file": item["file"], **region})
    print(f"结果已保存到: {output}")
    print(f"区域复核表已保存到: {review}")


if __name__ == "__main__":
    main()
