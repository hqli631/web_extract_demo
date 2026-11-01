"""Collect bounded news batches, compare extractors, replay saved AI audits."""
import argparse
import hashlib
import json
from html import escape
from pathlib import Path
import shutil

from collect_pages import collect
from compare_extractors import analyze, write_reports
from extract import extract_file

ROOT = Path(__file__).resolve().parent


def read(path):
    return json.loads(path.read_text(encoding='utf-8-sig'))


def write(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding='utf-8')


def check_audit(result, snapshot, audit):
    if not audit:
        return {'status': 'unreviewed', 'reason': '新增页面需要新的 AI 审核记录'}
    if audit.get('snapshot') != snapshot:
        return {'status': 'stale', 'reason': '样本已变，禁止复用旧审核'}
    expected = audit['body_blocks']
    actual = result['content'].splitlines()
    missing = [t for t in expected if t not in actual]
    extra = [t for t in actual if t not in expected]
    contaminated = [t for t in audit.get('excluded_blocks', []) + audit.get('metadata_blocks', [])
                    if t and t in result['content']]
    passed = actual == expected and not contaminated
    return {'status': 'pass' if passed else 'fail', 'missing': missing,
            'extra': extra, 'contaminated': contaminated, 'exact_order_match': actual == expected}


def run(batch, do_collect=False, publish=False):
    if do_collect:
        for config in read(ROOT / 'config/collection_news.json')['targets']:
            report = collect(config, root=batch)
            write(batch / 'reports' / ('collection_' + config['name'] + '.json'), report)
            print(config['name'], 'added:', len(report['added']), 'errors:', len(report['errors']), flush=True)
    paths = sorted((batch / 'samples').glob('*.html'))
    if not paths:
        raise ValueError('没有新闻样本；首次运行添加 --collect')
    comparisons = [analyze(path) for path in paths]
    write_reports(comparisons, batch / 'reports/current')
    audit_path = batch / 'reports/ai_audit.json'
    audits = {p['file']: p for p in read(audit_path)['pages']} if audit_path.exists() else {}
    checks, results = [], []
    for path, comparison in zip(paths, comparisons):
        result = extract_file(path)
        results.append(result)
        snapshot = hashlib.sha256(path.read_bytes()).hexdigest()
        checks.append({'file': path.name, 'snapshot': snapshot, 'title': result['title'],
                       'scope_method': result['scope_method'], 'content_chars': result['content_length'],
                       'comparison_status': comparison['status'], **check_audit(result, snapshot, audits.get(path.name))})
    summary = {'note': 'Current-conversation AI development audits, not human gold or independent accuracy.',
               'passed': sum(c['status'] == 'pass' for c in checks),
               'total': len(checks), 'checks': checks}
    write(batch / 'reports/regression.json', summary)
    write(batch / 'reports/results.json', results)
    write(batch / 'reports/code_context.json', {name: hashlib.sha256((ROOT/name).read_bytes()).hexdigest()
          for name in ('extract.py', 'content_scope.py', 'review_source.py', 'run_news_validation.py')})
    before_path = batch / 'reports/before/extractor_comparison.json'
    before = {p['file']: p for p in read(before_path)} if before_path.exists() else {}
    sections = []
    for check, result in zip(checks, results):
        old = before.get(check['file'], {})
        sections.append('<section><h2>' + escape(check['title']) + '</h2><p>' + escape(check['file'])
                        + '</p><p>审核回归：' + escape(check['status']) + '；范围：' + escape(check['scope_method'])
                        + f"；字符数：{len(old.get('current_text', ''))} → {check['content_chars']}"
                        + '</p><details><summary>正文与检查详情</summary><pre>' + escape(result['content'])
                        + '</pre><pre>' + escape(json.dumps(check, ensure_ascii=False, indent=2)) + '</pre></details></section>')
    html = '<!doctype html><html lang="zh-CN"><meta charset="utf-8"><title>新闻扩展与自动回归</title><style>body{max-width:1100px;margin:30px auto;padding:20px;font:16px/1.8 system-ui;color:#213047}section{border-top:1px solid #ccd4df;padding:15px 0}pre{white-space:pre-wrap;overflow-wrap:anywhere;font:inherit}</style><h1>新闻扩展与自动回归</h1>'
    html += f'<p>本批 {len(checks)} 页；符合已保存 AI 审核预期 {summary["passed"]} 页。</p>'
    html += '<p>采集来自中新网和新浪财经栏目链接。自动比较只产生差异；AI 审核由当前对话完成并保存，重跑脚本不会产生新的 AI 判断。这批样本参与了规则修改，结果属于开发回归，不能当作跨站准确率。</p><p>改进：中新网限定 .left_zw 主区并保留短段落；独立记者署名、文章来源单列；图注、编辑、APP 推广、版权不并入正文。保留原文中的股票链接和新闻小标题，不照抄基线算法的删减。</p><p><a href="current/extractor_comparison.html">当前算法与 Trafilatura 对比</a> · <a href="before/extractor_comparison.html">改进前对比</a></p>'
    (batch / 'reports/progress.html').write_text(html + ''.join(sections) + '</html>', encoding='utf-8')
    if publish:
        if summary['passed'] != len(checks):
            raise ValueError('有未审核、快照过期或回归失败页面，未发布至主项目')
        manifest_path = ROOT / 'reports/collection_manifest.json'
        manifest = read(manifest_path) if manifest_path.exists() else []
        incoming = read(batch / 'reports/collection_manifest.json')
        for path in paths:
            target = ROOT / 'samples' / path.name
            if target.exists() and target.read_bytes() != path.read_bytes():
                raise ValueError('同名主样本不同，拒绝覆盖：' + path.name)
        for path in paths:
            shutil.copyfile(path, ROOT / 'samples' / path.name)
        names = {p.name for p in paths}
        write(manifest_path, [m for m in manifest if m['file'] not in names] + incoming)
        print('Published:', len(paths), 'pages')
    print('Audit regression:', summary['passed'], '/', len(checks))
    print(batch / 'reports/progress.html')
    return summary


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--collect', action='store_true', help='访问栏目并定向发现新详情页')
    parser.add_argument('--publish', action='store_true', help='仅在全部匹配审核预期时加入主项目样本')
    parser.add_argument('--batch', type=Path, default=ROOT / 'news_validation')
    args = parser.parse_args()
    summary = run(args.batch, args.collect, args.publish)
    if summary['passed'] != summary['total']:
        raise SystemExit(1)
