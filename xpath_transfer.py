"""Run the configured XPath on one isolated page without changing development baselines."""
import argparse
import json
import re
from html import escape
from pathlib import Path

from xpath_batch import ROOT, extract_page
from xpath_quality import inspect_page


def run(page_path, output_dir):
    page_path = Path(page_path).resolve()
    if not page_path.is_file():
        raise FileNotFoundError(page_path)
    rules = json.loads((ROOT / 'xpath_rules.json').read_text(encoding='utf-8-sig'))
    page = extract_page(page_path, rules)
    quality = inspect_page(page_path, rules, page)
    blocks = page['blocks']
    page['quality'] = quality
    page['review_state'] = 'not_reviewed'
    page['baseline_state'] = 'not_compared'
    page['transfer_evidence'] = compare_historical_reference(page)
    page['scope_note'] = (
        '隔离迁移检查：未读取或修改开发集冻结基准；结构检查不等于语义审核或准确率。'
    )
    output_dir = Path(output_dir).resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    stem = page_path.stem
    json_path = output_dir / f'{stem}.json'
    html_path = output_dir / f'{stem}.html'
    json_path.write_text(json.dumps(page, ensure_ascii=False, indent=2), encoding='utf-8')

    block_html = ''.join(
        f"<li><b>{'图片说明' if block['type'] == 'caption' else '段落'}</b>："
        f"{escape(block['text'])}<details><summary>XPath</summary>"
        f"<code>{escape(block['xpath'])}</code></details></li>"
        for block in blocks
    ) or '<li>未提取到正文文本块</li>'
    checks = ''.join(
        f"<tr><td>{escape(item['label'])}</td><td>{escape(item['status'])}</td>"
        f"<td>{escape(item['note'])}</td></tr>"
        for item in quality['checks']
    )
    reference = page['transfer_evidence']
    reference_html = (
        f"<h2>历史审核兼容性检查</h2><p>{escape(reference['status'])}："
        f"{escape(reference['note'])}</p>"
        if reference else '<h2>历史审核兼容性检查</h2><p>没有匹配的历史审核记录。</p>'
    )
    html_path.write_text(
        "<!doctype html><html lang='zh-CN'><meta charset='utf-8'><title>XPath迁移检查</title>"
        "<style>body{max-width:1000px;margin:32px auto;padding:0 20px;font:16px/1.7 sans-serif}"
        "table{border-collapse:collapse}td,th{border:1px solid #aaa;padding:8px;vertical-align:top}"
        "li{margin:14px 0}code{overflow-wrap:anywhere}</style>"
        f"<h1>{escape(page['title'] or '未找到标题')}</h1>"
        f"<p>文件：{escape(page_path.name)}；正文容器：{page['container_count']}；"
        f"正文与图说：{len(blocks)}；SHA256：<code>{page['source_sha256']}</code></p>"
        f"<p>{escape(page['scope_note'])}</p><p>语义审核：尚未进行。基准比较：未进行。</p>"
        "<h2>结构检查</h2><table><tr><th>检查项</th><th>状态</th><th>范围与说明</th></tr>"
        f"{checks}</table>{reference_html}<h2>XPath 抽取结果</h2><ol>{block_html}</ol></html>",
        encoding='utf-8',
    )
    return page, json_path, html_path


def compare_historical_reference(page):
    audit_path = ROOT / 'news_validation' / 'reports' / 'ai_audit.json'
    if not audit_path.exists():
        return None
    records = json.loads(audit_path.read_text(encoding='utf-8')).get('pages', [])
    matches = [record for record in records if record.get('file') == page['file']
               and record.get('snapshot') == page['source_sha256']]
    if len(matches) != 1:
        return None
    record = matches[0]
    compact = lambda text: re.sub(r'\s+', '', text)
    expected = [compact(text) for text in record.get('body_blocks', [])]
    actual = [compact(block['text']) for block in page['blocks'] if block['type'] == 'paragraph']
    matched = expected == actual
    return {
        'status': 'retrospective_match' if matched else 'retrospective_mismatch',
        'reference_source': 'news_validation/reports/ai_audit.json',
        'reference_kind': 'historical_development_audit',
        'expected_paragraphs': len(expected),
        'actual_paragraphs': len(actual),
        'ordered_text_match': matched,
        'note': (
            '逐段文字与历史审核正文顺序一致（忽略空白差异）；该页过去已参与抽取器比较和 AI 审核，只算回溯兼容性检查，不是未见页面或盲测。'
            if matched else '与历史审核段落存在差异；该页过去已参与开发审核，须先解释差异，不能计作盲测。'
        ),
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('html_file', help='隔离验证目录中的一个本地 HTML 文件')
    parser.add_argument('--output-dir', default=str(ROOT / 'output' / 'xpath_transfer'))
    args = parser.parse_args()
    page, json_path, html_path = run(args.html_file, args.output_dir)
    print(f"标题：{page['title'] or '未找到'}")
    print(f"正文容器：{page['container_count']}；正文与图说：{len(page['blocks'])}")
    print('审核状态：尚未语义审核；基准未比较；开发集未修改。')
    print(f'JSON：{json_path}')
    print(f'HTML：{html_path}')
    return 0 if page['container_count'] == 1 and page['title'] and page['blocks'] else 2


if __name__ == '__main__':
    raise SystemExit(main())

