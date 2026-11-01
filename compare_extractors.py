"""Compare the local heuristic extractor with Trafilatura on saved HTML pages."""
import argparse
import hashlib
import importlib.util
import json
import re
from collections import Counter
from html import escape
from pathlib import Path

from extract import extract_file, prepare_html
from dom_evidence import make_queue
from bs4 import BeautifulSoup


ROOT = Path(__file__).resolve().parent
SAMPLES = ROOT / "samples"
REPORTS = ROOT / "reports"


def normalize(text):
    # Text-only baselines may serialize actual HTML list items with a marker.
    text = re.sub(r'(?m)^\s*[-*+]\s+', '', text or '')
    return re.sub(r"\s+", " ", text).strip().casefold()


def blocks(text):
    return [normalize(line) for line in (text or "").splitlines() if normalize(line)]


def compact(text):
    return re.sub(r"\s+", "", normalize(text))


def contained(block, other_blocks):
    # Direction matters: one matching short sentence cannot explain a whole block.
    value = compact(block)
    return bool(value) and value in compact("".join(other_blocks))


def similarity(left, right):
    """Symmetric multiset character 5-gram Dice, bounded to [0, 1]."""
    def grams(text):
        text = compact(text)
        size = min(5, len(text))
        return Counter(text[i:i + size] for i in range(len(text) - size + 1)) if size else Counter()
    a, b = grams(left), grams(right)
    total = sum(a.values()) + sum(b.values())
    return round(2 * sum((a & b).values()) / total, 4) if total else None


def compare_page(name, current_blocks, baseline_text):
    baseline_blocks = blocks(baseline_text)
    current_only = [value for value in current_blocks if not contained(value, baseline_blocks)]
    baseline_only = [value for value in baseline_blocks if not contained(value, current_blocks)]
    current_chars = sum(map(len, current_blocks))
    baseline_chars = sum(map(len, baseline_blocks))
    return {
        "file": name,
        "current_chars": current_chars,
        "baseline_chars": baseline_chars,
        "similarity_estimate": similarity("\n".join(current_blocks), baseline_text),
        "current_only": current_only,
        "baseline_only": baseline_only,
    }


def analyze(path):
    try:
        import trafilatura
    except ImportError as exc:
        raise RuntimeError(
            "缺少 Trafilatura。请先运行: python -m pip install --target .deps -r requirements.txt"
        ) from exc
    html = path.read_text(encoding="utf-8", errors="ignore")
    current = extract_file(path)
    baseline_soup = BeautifulSoup(prepare_html(html), 'lxml')
    # Captured computed styles can be tens of MB; they are presentation, not text.
    for node in baseline_soup.find_all(style=True):
        del node['style']
    baseline = trafilatura.extract(
        str(baseline_soup),
        url=None,
        include_comments=False,
        include_tables=True,
        favor_precision=True,
        output_format="txt",
    ) or ""
    current_blocks = [
        normalize(region["text"])
        for region in current["regions"]
        if region["auto_label"] in {"正文候选", "标题/小标题"} and normalize(region["text"])
    ]
    result = compare_page(path.name, current_blocks, baseline)
    result["title"] = current["title"]
    result['page_type'] = current['page_type']
    result['scope_method'] = current['scope_method']
    result['warnings'] = current['warnings']
    result["current_text"] = current["content"]
    result["baseline_text"] = baseline
    result["status"] = "empty_output" if not current_blocks or not baseline.strip() else (
        "short_output" if min(result["current_chars"], result["baseline_chars"]) < 100 else "disagreement" if result["current_only"] or result["baseline_only"] else "agreement")
    if current['extraction_status'] == 'not_article':
        result['status'] = 'not_article'
    result["snapshot"] = hashlib.sha256(path.read_bytes()).hexdigest()
    result['queue'] = [] if result['status'] == 'not_article' else make_queue(result, html)
    return result


def write_reports(results, reports_dir=REPORTS):
    reports_dir.mkdir(parents=True, exist_ok=True)
    (reports_dir / "extractor_comparison.json").write_text(
        json.dumps(results, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    queue = [entry for result in results for entry in result.get('queue', [])]
    (reports_dir / 'auto_review_queue.json').write_text(json.dumps(queue, ensure_ascii=False, indent=2), encoding='utf-8')
    lines = [
        "# 自动抽取器对比",
        "",
        "当前启发式抽取器与 Trafilatura 的差异候选。两者一致不等于正确，分歧也不自动代表错误。",
        "",
        "| 页面 | 当前字符数 | 基线字符数 | 相似度估计 | 当前独有段落 | 基线独有段落 |",
        "|---|---:|---:|---:|---:|---:|",
    ]
    for item in results:
        if "error" in item:
            lines.append(f"| {item['file']} | ERROR | — | — | — | — |")
            continue
        similarity = "N/A" if item["similarity_estimate"] is None else f'{item["similarity_estimate"]:.1%}'
        lines.append(
            f"| {item['file']} | {item['current_chars']} | {item['baseline_chars']} | {similarity} | "
            f"{len(item['current_only'])} | {len(item['baseline_only'])} |"
        )
    lines += ["", "相似度采用去空白后的字符五元组 Dice；它不是准确率。差异按单向文本包含判断，段落格式和标点差异仍可能产生分歧。", ""]
    for item in results:
        if "error" in item:
            lines.extend([f"### {item['file']}：运行失败", "", str(item['error']), ""])
            continue
        lines.extend([f"## {item['file']}（{item.get('status', 'unknown')}）", ""])
        for heading, key in (("当前抽取独有", "current_only"), ("基线抽取独有", "baseline_only")):
            excerpts = item[key][:5]
            if excerpts:
                lines.extend(["", f"### {item['file']}：{heading}", ""])
                lines.extend(f"- {excerpt[:240]}" for excerpt in excerpts)
                if len(item[key]) > len(excerpts):
                    lines.append(f"- 另有 {len(item[key]) - len(excerpts)} 段，见 JSON 报告。")
    (reports_dir / "extractor_comparison.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    sections = []
    for item in results:
        title = escape(item['file'])
        if 'error' in item:
            sections.append(f"<section><h2>{title}</h2><pre>{escape(str(item['error']))}</pre></section>")
            continue
        columns = []
        for heading, key in (("当前提取结果", "current_text"), ("Trafilatura 结果", "baseline_text")):
            columns.append(f"<div><h3>{heading}</h3><pre>{escape(item.get(key, ''))}</pre></div>")
        details = ''.join(f"<h3>{label}</h3><ul>" + ''.join(f"<li>{escape(text)}</li>" for text in item[key]) + '</ul>' for label, key in (("当前独有：可能误提", "current_only"), ("基线独有：可能漏提", "baseline_only")))
        evidence_html = ''
        for entry in item.get('queue', []):
            evidence_html += '<li>' + escape(entry.get('kind', '')) + ': ' + escape(entry.get('text', entry.get('reason', '')))
            evidence_html += '<p>定位：' + escape(entry.get('match_status', '需诊断')) + '；建议未启用</p>'
            for evidence in entry.get('evidence', []):
                evidence_html += '<pre>' + escape(json.dumps({'locator': evidence['locator'], 'containers': evidence['containers']}, ensure_ascii=False, indent=2)) + '</pre>'
            evidence_html += '</li>'
        details += '<h3>DOM / XPath 定位依据</h3><p>unique 表示唯一文本匹配；ambiguous 表示存在多处；unresolved 表示暂未定位。定位成功不代表标签正确。</p><ul>' + evidence_html + '</ul>'
        status_text = {'not_article': '列表/目录页，跳过单篇正文对比，应采集详情页', 'empty_output': '至少一个提取器未输出正文（不代表网页无内容）', 'short_output': '至少一个提取结果偏短，需排查', 'disagreement': '两种提取结果有分歧', 'agreement': '两种结果一致，尚不代表正确'}.get(item.get('status'), '未知')
        score = '无法计算' if item['similarity_estimate'] is None else f"{item['similarity_estimate']:.1%}"
        scope = escape(item.get('scope_method', ''))
        warnings = escape(' '.join(item.get('warnings', [])))
        sections.append(f"<section><h2>{title}</h2><p>状态：{status_text}；字符数 {item['current_chars']} / {item['baseline_chars']}；相似度 {score}</p><p>正文范围依据：{scope} {warnings}</p><div class='columns'>{''.join(columns)}</div><details><summary>查看差异候选</summary>{details}</details></section>")
    document = "<!doctype html><html lang='zh-CN'><meta charset='utf-8'><title>自动正文对比</title><style>body{margin:24px;font:16px/1.6 system-ui;background:#f2f5fa;color:#203047}section{padding:20px;background:white;margin:24px 0;border-radius:10px}.columns{display:grid;grid-template-columns:1fr 1fr;gap:24px}pre{white-space:pre-wrap;overflow-wrap:anywhere;font:inherit;max-height:65vh;overflow:auto}li{margin:12px 0}h2{overflow-wrap:anywhere}@media(max-width:800px){.columns{grid-template-columns:1fr}}</style><h1>自动正文对比</h1><p>先看空输出、短输出与明显分歧。两种算法一致并不代表正确；此页不修改标注，也不代表浏览器复核页预测。</p>" + ''.join(sections) + '</html>'
    (reports_dir / "extractor_comparison.html").write_text(document, encoding='utf-8')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--sample", action="append", help="只对比指定样本文件名；可重复传入")
    parser.add_argument('--reports-dir', type=Path, default=REPORTS, help='报告目录；可用于保留之前的审核输入')
    args = parser.parse_args()
    if importlib.util.find_spec("trafilatura") is None:
        raise SystemExit("缺少 Trafilatura。请先运行: python -m pip install --target .deps -r requirements.txt")
    paths = [SAMPLES / name for name in args.sample] if args.sample else sorted(SAMPLES.glob("*.html"))
    missing = [path.name for path in paths if not path.is_file()]
    if missing:
        parser.error("找不到样本文件: " + ", ".join(missing))
    results = []
    for path in paths:
        try:
            results.append(analyze(path))
            print(f"[OK] {path.name}")
        except Exception as exc:
            results.append({"file": path.name, "error": str(exc)})
            print(f"[ERROR] {path.name}: {exc}")
    write_reports(results, args.reports_dir)
    print(f"Reports: {args.reports_dir / 'extractor_comparison.html'}")


if __name__ == "__main__":
    main()
