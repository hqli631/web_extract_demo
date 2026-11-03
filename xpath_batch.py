"""批量执行 XPath 练习，比较固定样本的全文和顺序。"""
import argparse
import difflib
import hashlib
import json
from html import escape
from pathlib import Path

from lxml import html
from xpath_quality import inspect_page
from xpath_semantic import find_review
from xpath_corrections import compose_cleaned
from author_candidates import find_author_candidates

ROOT = Path(__file__).resolve().parent


def extract_page(path, rules):
    source = path.read_bytes()
    tree = html.document_fromstring(source)
    titles = [' '.join(n.text_content().split()) for n in tree.xpath(rules['title_xpath'])]
    titles = [s for s in titles if s]
    containers = tree.xpath(rules['container_xpath'])
    blocks = []
    for container in containers:
        for node in container.xpath(rules['block_xpath']):
            text = ' '.join(node.text_content().split())
            if text:
                blocks.append({
                    'type': 'caption' if 'pictext' in node.get('class', '').split() else 'paragraph',
                    'text': text,
                    'xpath': tree.getroottree().getpath(node),
                })
    return {'file': path.name, 'source_sha256': hashlib.sha256(source).hexdigest(),
            'title': titles[0] if titles else '', 'container_count': len(containers), 'blocks': blocks}


def signature(page):
    # 数量相同的文字变化、类型变化和顺序变化同样需要报告。
    return page['title'], page['container_count'], [(b['type'], b['text']) for b in page['blocks']]


def lines(page):
    return [page['title']] + [f"[{b['type']}] {b['text']}" for b in page['blocks']]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--freeze-baseline', action='store_true', help='首次冻结结果，不覆盖已有基准')
    args = parser.parse_args()
    out = ROOT / 'output' / 'xpath_practice'
    out.mkdir(parents=True, exist_ok=True)
    base_path = out / 'baseline.json'
    if args.freeze_baseline and base_path.exists():
        parser.error('基准已存在，不会覆盖；请直接运行比较。')
    rules = json.loads((ROOT / 'xpath_rules.json').read_text(encoding='utf-8-sig'))
    review_path = ROOT / 'xpath_semantic_reviews.json'
    reviews = json.loads(review_path.read_text(encoding='utf-8')) if review_path.exists() else {}
    baseline = json.loads(base_path.read_text(encoding='utf-8')) if base_path.exists() else {}
    old_pages = {p['file']: p for p in baseline.get('pages', [])}
    paths = sorted((ROOT / 'samples').glob('xpath_practice*.html'))
    if not paths:
        parser.error('未找到 samples/xpath_practice*.html')
    pages, rows, details, errors, statuses = [], [], [], [], {}
    for path in paths:
        try:
            page = extract_page(path, rules)
            if page['container_count'] != 1 or not page['title'] or not page['blocks']:
                raise ValueError('需要一个正文容器、非空标题和非空正文')
            pages.append(page)
            page['quality'] = inspect_page(path, rules, page)
            page['semantic_review'] = find_review(page, rules, reviews)
            page['cleaned'] = compose_cleaned(page)
            page['author_candidates'] = find_author_candidates(page)
            old = old_pages.get(path.name)
            if old is None:
                status = '无基准，待核对'
            elif old['source_sha256'] != page['source_sha256']:
                status = '源文件已变化，需重新核对'
            elif signature(old) == signature(page):
                status = '与基准一致'
            else:
                status = '抽取结果变化，需检查'
            statuses[path.name] = status
            n_caption = sum(b['type'] == 'caption' for b in page['blocks'])
            n_paragraph = len(page['blocks']) - n_caption
            print(f"{path.name}: 段落 {n_paragraph}，图说 {n_caption}，合计 {len(page['blocks'])}；{status}")
            rows.append(f"<tr><td>{escape(path.name)}</td><td>{n_paragraph}</td><td>{n_caption}</td>"
                        f"<td>{len(page['blocks'])}</td><td>{escape(status)}</td></tr>")
            diff = '\n'.join(difflib.unified_diff(lines(old), lines(page),
                fromfile='基准', tofile='当前', lineterm='')) if old else '尚无基准。'
            blocks = ''.join(
                f"<li><b>{'图片说明' if b['type'] == 'caption' else '段落'}</b>：{escape(b['text'])}"
                f"<details><summary>XPath 位置</summary><code>{escape(b['xpath'])}</code></details></li>"
                for b in page['blocks'])
            details.append(f"<h2>{escape(path.name)}</h2><h3>{escape(page['title'])}</h3>"
                f"<details><summary>文字差异：减号为旧，加号为新</summary><pre>{escape(diff or '文字及顺序无变化；容器数量另行比较。')}</pre></details><ol>{blocks}</ol>")
            quality_rows = []
            labels = {'structural_pass': '结构检查通过', 'needs_review': '需要复核',
                      'unknown': '未判断', 'not_applicable': '不适用'}
            for item in page['quality']['checks']:
                evidence_html = ''.join(
                    f"<li>{escape(e['reason'])}<br>{escape(e['text'])}<br><code>{escape(e['xpath'])}</code></li>"
                    for e in item['evidence'])
                quality_rows.append(f"<tr><td>{escape(item['label'])}</td>"
                    f"<td>{labels[item['status']]}</td><td>{escape(item['note'])}<ul>{evidence_html}</ul></td></tr>")
            details[-1] = details[-1].replace('<ol>',
                '<h3>质量检查与证据</h3><table><tr><th>检查项</th><th>状态</th><th>依据和范围</th></tr>'
                + ''.join(quality_rows) + '</table><h3>提取文本</h3><ol>', 1)
            review = page['semantic_review']
            audit_html = '<h3>本次对话 AI 语义审核</h3><p>' + escape(review['note']) + '</p>'
            if review['status'] == 'current':
                record = review['record']
                audit_html += (f"<p>审核者：{escape(review['reviewer'])}；日期：{escape(review['reviewed_at'])}。</p>"
                               f"<p>{escape(review['scope'])}</p><p>{escape(record['summary'])}</p>")
                audit_html += '<table><tr><th>审核项</th><th>结论</th><th>理由与证据</th></tr>'
                for rubric in record['rubrics']:
                    evidence_html = ''.join(
                        f"<li>{escape(e['quote'])}<br><code>{escape(e['xpath'])}</code></li>"
                        for e in rubric['evidence'])
                    audit_html += (f"<tr><td>{escape(rubric['label'])}</td>"
                        f"<td>{ {'pass': '范围内未发现问题', 'needs_review': '发现待处理项', 'unknown': '未判断'}[rubric['status']] }</td>"
                        f"<td>{escape(rubric['reason'])}<ul>{evidence_html}</ul></td></tr>")
                audit_html += '</table><h4>原始审核建议（执行情况见下方修正结果）</h4><ul>'
                audit_html += ''.join('<li>' + escape(s) + '</li>' for s in record['proposals']) + '</ul>'
            details[-1] = details[-1].replace('<h3>提取文本</h3>', audit_html + '<h3>提取文本</h3>', 1)
            cleaned = page['cleaned']
            author_html = ''.join(
                f"<li>{escape(a['name'])}；原始署名：{escape(a['byline'])}；原始块 {a['raw_block_index']}"
                f"<br><code>{escape(a['xpath'])}</code></li>" for a in cleaned['authors'])
            clean_blocks = ''.join(
                f"<li><b>{'图片说明' if b['type'] == 'caption' else '段落'}</b>：{escape(b['text'])}</li>"
                for b in cleaned['blocks'])
            clean_html = (f"<h3>修正后的作者与正文</h3><p>{escape(cleaned['note'])}</p>"
                f"<p>执行状态：{escape(cleaned['status'])}；原始 {len(page['blocks'])} 块，"
                f"修正后 {len(cleaned['blocks'])} 块；独立署名 {len(cleaned['authors'])} 条。</p>"
                f"<p>作者：</p><ul>{author_html or '<li>未确认独立署名</li>'}</ul>"
                f"<details open><summary>清理后正文（仍含图片说明）</summary><ol>{clean_blocks}</ol></details>")
            candidate_html = ''.join(
                f"<li>原始块 {c['raw_block_index']}：{escape(c['text'])}；"
                f"<code>{escape(c['xpath'])}</code><br>{escape(c['reason'])}</li>"
                for c in page['author_candidates'])
            candidate_html = ("<h3>自动署名候选（只供审核）</h3>"
                              "<p>候选扫描不会自动删除或移动正文；需由语义审核记录明确确认。</p>"
                              f"<ul>{candidate_html or '<li>未发现候选</li>'}</ul>")
            details[-1] = details[-1].replace('<h3>提取文本</h3>',
                clean_html + candidate_html + '<h3>原始提取文本（回归比较对象）</h3>', 1)
            print(f"  署名修正：{cleaned['status']}；清理后 {len(cleaned['blocks'])} 块；作者 {len(cleaned['authors'])} 条")
        except Exception as exc:
            errors.append(f'{path.name}: {exc}')
            statuses[path.name] = '运行异常'
            rows.append(f"<tr><td>{escape(path.name)}</td><td colspan='4'>运行异常：{escape(str(exc))}</td></tr>")
    missing = sorted(set(old_pages) - {p.name for p in paths})
    for name in missing:
        rows.append(f"<tr><td>{escape(name)}</td><td colspan='4'>基准样本缺失</td></tr>")
    report = {'rules': rules, 'pages': pages, 'statuses': statuses, 'errors': errors, 'missing_samples': missing}
    if args.freeze_baseline and not errors:
        with base_path.open('x', encoding='utf-8') as file:
            json.dump({'rules': rules, 'pages': pages}, file, ensure_ascii=False, indent=2)
        print('已冻结当前结果。这是回归基准，不是全文正确答案。')
    (out / 'results.json').write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
    rule_status = '无旧规则' if not baseline else ('规则未变化' if baseline['rules'] == rules else '规则配置已变化')
    page_html = ("<!doctype html><html lang='zh-CN'><meta charset='utf-8'><title>XPath 批量实验</title>"
        "<style>body{max-width:1100px;margin:30px auto;padding:0 20px;font:16px/1.7 sans-serif}"
        "table{border-collapse:collapse}td,th{border:1px solid #ccc;padding:8px}li{margin:14px 0}"
        "pre,code{white-space:pre-wrap;overflow-wrap:anywhere}</style><h1>XPath 批量实验</h1>"
        f"<p>规则：{escape(str(rules['name']))}，版本 {escape(str(rules['version']))}；{rule_status}。</p>"
        "<p>与基准一致只表示结果未变化，不代表准确率。结构检查与对话 AI 审核分别显示；"
        "运行脚本不会调用模型，新样本需要新增审核记录；输入、规则或输出变化会使旧审核失效。"
        "首次冻结后请再运行一次比较；新样本不会自动加入基准。</p>"
        "<table><tr><th>文件</th><th>段落</th><th>图片说明</th><th>总块数</th><th>状态</th></tr>"
        + ''.join(rows) + '</table>' + ''.join(details) + '</html>')
    (out / 'summary.html').write_text(page_html, encoding='utf-8')
    for error in errors:
        print('运行异常：' + error)
    print(f"报告：{out / 'summary.html'}")
    return 1 if errors or missing else 0


if __name__ == '__main__':
    raise SystemExit(main())
