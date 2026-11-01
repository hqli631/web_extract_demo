"""Replay saved conversation audit expectations against scoped extraction.

These cases informed implementation: this is regression, not held-out accuracy.
"""
import hashlib
from html import escape
import json
from pathlib import Path

from dom_evidence import key
from extract import extract_file

ROOT = Path(__file__).resolve().parent


def main():
    read = lambda p: json.loads(p.read_text(encoding='utf-8-sig'))
    old = {p['file']: p for p in read(ROOT / 'reports/extractor_comparison.json') if 'error' not in p}
    audit = read(ROOT / 'reports/ai_review_suggestions.json')['records']
    pages = [extract_file(p) for p in sorted((ROOT / 'samples').glob('*.html'))]
    records = []
    for p in pages:
        snapshot = hashlib.sha256((ROOT / 'samples' / p['file']).read_bytes()).hexdigest()
        relevant = [r for r in audit if r['file'] == p['file']]
        checks = []
        for r in relevant:
            if r['snapshot'] != snapshot or r['decision'] == 'uncertain':
                checks.append(dict(id=r['id'], status='skipped', reason='stale_or_uncertain'))
                continue
            expected = r['decision'] == 'body'
            present = key(r['text']) in key(p['content'])
            checks.append(dict(id=r['id'], decision=r['decision'], text=r['text'],
                               status='pass' if present == expected else 'fail'))
        records.append(dict(file=p['file'], page_type=p['page_type'], scope_method=p['scope_method'],
                            before_chars=len(old.get(p['file'], {}).get('current_text', '')),
                            after_chars=len(p['content']), checks=checks))
    report = dict(note='Development regression using AI suggestions, not human gold or independent accuracy.',
                  passed=sum(c['status']=='pass' for r in records for c in r['checks']),
                  failed=sum(c['status']=='fail' for r in records for c in r['checks']),
                  skipped=sum(c['status']=='skipped' for r in records for c in r['checks']), pages=records)
    for path, data in [(ROOT/'output/scoped_results.json',pages), (ROOT/'reports/scope_v2/regression.json',report)]:
        path.parent.mkdir(exist_ok=True, parents=True)
        path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding='utf-8')
    sections=[]
    for p, r in zip(pages, records):
        failed = [c for c in r['checks'] if c['status']=='fail']
        display = p['content'] or ('列表页不输出单篇文章正文；应继续采集详情页。' if p['page_type']=='listing' else '未输出正文，需排查。')
        sections.append('<section><h2>'+escape(p['file'])+'</h2><p>'+escape(p['title'])+'</p><p>类型：'+escape(p['page_type'])+'；范围依据：'+escape(p['scope_method'])+f"；字符数：{r['before_chars']} → {r['after_chars']}"+'</p><p>'+escape(' '.join(p['warnings']))+'</p><p>审核样例回归未符合数：'+str(len(failed))+'</p><pre>'+escape(display)+'</pre></section>')
    html = '<!doctype html><html lang="zh-CN"><meta charset="utf-8"><title>正文范围优化结果</title><style>body{max-width:1100px;margin:30px auto;padding:20px;font:16px/1.8 system-ui}section{border-top:1px solid #ccc;margin-top:30px}pre{white-space:pre-wrap;font:inherit}p{overflow-wrap:anywhere}</style><h1>正文范围优化结果</h1><p>本轮规则：目标标题选择文章、原帖独立正文、短段落和列表保留、列表页单独识别、修复 read-break 被误识别为广告。</p>'+f"<p>此前 AI 审核样例回归：符合 {report['passed']}，不符合 {report['failed']}，跳过 {report['skipped']}。这些样例参与了本轮改进，不是独立准确率。</p>"+'<p><a href="extractor_comparison.html">查看新版与 Trafilatura 的逐页差异</a></p><p>本页为静态提取结果；浏览器复核页仍使用独立算法，本轮没有同步修改其标签。</p>'+''.join(sections)+'</html>'
    (ROOT/'reports/scope_v2/progress.html').write_text(html,encoding='utf-8')
    print(f"Regression: passed={report['passed']} failed={report['failed']} skipped={report['skipped']}; reports/scope_v2/progress.html")


if __name__ == '__main__':
    main()
