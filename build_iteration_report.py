"""Validate saved conversation audits and report scoped extraction iteration 3."""
from collections import Counter
import hashlib
from html import escape
import json
from pathlib import Path

from compare_extractors import normalize
from dom_evidence import key
from extract import extract_file

ROOT = Path(__file__).resolve().parent


def read(path):
    return json.loads(path.read_text(encoding='utf-8-sig'))


def write(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding='utf-8')


def signature(entry):
    return entry['file'], entry['snapshot'], entry['kind'], key(normalize(entry['text']))


def reconcile(queue, records):
    index = {signature(r): r for r in records}
    results = []
    for entry in queue:
        prior = index.get(signature(entry)) if 'text' in entry else None
        results.append(dict(file=entry['file'], text=entry.get('text', ''),
                            status='reviewed' if prior else 'unreviewed',
                            category=prior['category'] if prior else 'needs_review',
                            reason=prior['reason'] if prior else '无同快照同文本审核判断，不能自动沿用标签。'))
    return results


def verify_transfer(root):
    context = read(root/'evaluation_context.json')
    if any(hashlib.sha256((ROOT/name).read_bytes()).hexdigest() != digest
           for name, digest in context['frozen_code_sha256'].items()):
        raise ValueError('Extraction code changed after transfer-check freeze; do not claim frozen validation.')
    manifest = {e['file']: e for e in read(root/'reports/collection_manifest.json')}
    reviews = read(root/'reports/ai_review.json')['reviews']
    pages = []
    for review in reviews:
        source = root/'samples'/review['file']
        if manifest[review['file']]['url'] in context['development_urls']:
            raise ValueError('Transfer URL overlaps development set')
        if hashlib.sha256(source.read_bytes()).hexdigest() != review['snapshot']:
            raise ValueError('Transfer review snapshot is stale')
        page = extract_file(source)
        body_matches = key(page['content']) == key('\n'.join(review['body_blocks']))
        excluded = all(key(text) not in key(page['content']) for text in review['excluded_controls'])
        pages.append(dict(file=source.name, url=manifest[source.name]['url'], title=page['title'],
                          content=page['content'], page_type=page['page_type'],
                          scope_method=page['scope_method'], body_matches=body_matches,
                          controls_excluded=excluded, passed=body_matches and excluded,
                          label_source='conversation_ai_review', reviewed=False))
    return pages


def main():
    audit = read(ROOT/'reports/scope_v2/difference_audit.json')
    source_queue = ROOT/audit['source_queue']
    if hashlib.sha256(source_queue.read_bytes()).hexdigest() != audit['queue_sha256']:
        raise ValueError('Reviewed v2 queue changed')
    for r in audit['records']:
        if hashlib.sha256((ROOT/'samples'/r['file']).read_bytes()).hexdigest() != r['snapshot']:
            raise ValueError('Audited development snapshot changed')
    current = reconcile(read(ROOT/'reports/scope_v3/auto_review_queue.json'), audit['records'])
    transfer = verify_transfer(ROOT/'validation_holdout')
    pages = [extract_file(p) for p in sorted((ROOT/'samples').glob('*.html'))]
    report = dict(original_reviewed=len(audit['records']), original_categories=dict(Counter(r['category'] for r in audit['records'])),
                  current_raw_differences=len(current), current_unreviewed=sum(r['status']=='unreviewed' for r in current),
                  current_differences=current, transfer_pages=transfer,
                  note='AI content review and same-template transfer check; not independent accuracy or model training.')
    write(ROOT/'reports/scope_v3/iteration.json', report)
    write(ROOT/'output/scoped_results_v3.json', pages)
    write(ROOT/'validation_holdout/reports/extraction_validation.json', transfer)
    sections=[]
    for page in pages:
        rows = ''.join('<li><b>'+escape(r['category'])+'</b>：'+escape(r['text'])+'<p>'+escape(r['reason'])+'</p></li>' for r in current if r['file']==page['file'])
        display = page['content'] or ('列表/目录页不输出单篇文章正文。' if page['page_type']=='listing' else '未输出正文，需排查。')
        sections.append('<section><h2>'+escape(page['file'])+'</h2><p>'+escape(page['title'])+'</p><p>类型：'+escape(page['page_type'])+'；范围：'+escape(page['scope_method'])+'</p><pre>'+escape(display)+'</pre><details><summary>当前算法差异及已审核原因</summary><ul>'+rows+'</ul></details></section>')
    holdout=''.join('<section><h3>'+escape(p['title'])+'</h3><p><a href="'+escape(p['url'],quote=True)+'">来源帖子</a>；正文匹配：'+str(p['body_matches'])+'；控件排除：'+str(p['controls_excluded'])+'</p><pre>'+escape(p['content'])+'</pre></section>' for p in transfer)
    overview=f"原 27 条差异全部审核：修复 1 条专题入口误提，消除 4 条列表标记格式差异。剩余 {len(current)} 条为已解释的算法分歧；其中无审核依据 {report['current_unreviewed']} 条。"
    validation=f"另取 {len(transfer)} 个未用于改规则的同站帖子，冻结代码后检查，{sum(p['passed'] for p in transfer)} 页符合本次对话 AI 对正文边界的判断。仅验证这一模板，不代表跨站准确率。"
    document='<!doctype html><html lang="zh-CN"><meta charset="utf-8"><title>第三轮提取与差异审核</title><style>body{max-width:1100px;margin:30px auto;padding:20px;font:16px/1.8 system-ui}section{border-top:1px solid #ccc;margin:25px 0}pre{white-space:pre-wrap;font:inherit}p,li{overflow-wrap:anywhere}</style><h1>第三轮提取与差异审核</h1><p>'+overview+'</p><p>'+validation+'</p><p>来源说明：以下判断由当前对话中的 AI 完成，未作为人工真值，未训练模型。浏览器复核页标签尚未同步本轮静态规则。</p><p><a href="extractor_comparison.html">查看原始算法对比</a></p><h2>新页面验证</h2>'+holdout+'<h2>现有页面提取结果</h2>'+''.join(sections)+'</html>'
    (ROOT/'reports/scope_v3/progress.html').write_text(document,encoding='utf-8')
    print(f"Reviewed differences: {len(current)}, without prior review: {report['current_unreviewed']}; transfer passed: {sum(p['passed'] for p in transfer)}/{len(transfer)}")


if __name__ == '__main__':
    main()
