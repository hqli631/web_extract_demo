"""独立检查候选 XPath 的任务契约；不评分、不发布、不改基准。"""
import argparse
import hashlib
import json
import sys
from html import escape
from pathlib import Path

from lxml import etree, html

ROOT = Path(__file__).resolve().parents[2]
KEYS = {'title_xpath', 'container_xpath', 'block_xpath'}


def text(node):
    return ' '.join(node.text_content().split())


def validate(task, candidate, sample_dir):
    result = {'accepted': False, 'semantic_review': 'pending', 'published': False,
              'ai_calls': 0, 'checks': [], 'pages': []}

    def check(name, ok, detail):
        result['checks'].append({'name': name, 'pass': bool(ok), 'detail': detail})
        return bool(ok)

    if not check('JSON 对象', isinstance(task, dict) and isinstance(candidate, dict), '任务与候选必须为对象。'):
        return result
    shape = (set(candidate) == {'task_id', 'source_sha256', 'rules', 'explanations', 'limitations'}
             and isinstance(candidate.get('task_id'), str) and isinstance(candidate.get('source_sha256'), dict))
    for field in ['rules', 'explanations']:
        value = candidate.get(field)
        shape = shape and isinstance(value, dict) and set(value) == KEYS
        if isinstance(value, dict):
            shape = shape and all(isinstance(v, str) and v.strip() for v in value.values())
    limits = candidate.get('limitations')
    shape = shape and isinstance(limits, list) and len(limits) >= 2
    if isinstance(limits, list):
        shape = shape and all(isinstance(v, str) and v.strip() for v in limits)
    if not check('返回字段', shape, '三条规则及解释必须完整，限制至少两条。'):
        return result
    payload = json.dumps({k: v for k, v in task.items() if k != 'task_id'},
                         ensure_ascii=False, sort_keys=True, separators=(',', ':'))
    computed = 'sina-selector-' + hashlib.sha256(payload.encode('utf-8')).hexdigest()[:16]
    if not check('任务对应', computed == task.get('task_id') == candidate['task_id'],
                 '重算内容编号；这是对应关系检查，不是身份认证。'):
        return result
    samples = task.get('samples')
    if not check('样例清单', isinstance(samples, list) and bool(samples) and all(
            isinstance(p, dict) and isinstance(p.get('file'), str)
            and isinstance(p.get('source_sha256'), str) for p in samples), '任务必须列出样例。'):
        return result
    names = [p['file'] for p in samples]
    if not check('样例路径', len(set(names)) == len(names) and all(
            n and n not in {'.', '..'} and not any(c in n for c in '/\\:') for n in names),
            '只读取 samples 内的独立文件名。'):
        return result
    hashes = {p['file']: p['source_sha256'] for p in samples}
    if not check('候选快照对应', candidate['source_sha256'] == hashes, '逐页 SHA256 必须与任务一致。'):
        return result
    rules = candidate['rules']
    if not check('块规则相对执行', rules['block_xpath'].startswith('./'),
                 '本课要求以 ./ 开始；完整结果范围还要逐节点验证。'):
        return result
    try:
        compiled = {k: etree.XPath(v) for k, v in rules.items()}
    except etree.XPathError as exc:
        check('XPath 编译', False, str(exc))
        return result
    check('XPath 编译', True, '语法正确不等于抽取正确。')
    for sample in samples:
        name = sample['file']
        path = sample_dir / name
        if not check(name + ' 快照', path.is_file() and hashlib.sha256(path.read_bytes()).hexdigest() == hashes[name],
                     '本地 HTML 字节必须与任务一致。'):
            continue
        try:
            tree = html.document_fromstring(path.read_bytes())
            dom = tree.getroottree()
            title_nodes = compiled['title_xpath'](tree)
            containers = compiled['container_xpath'](tree)
            for label, nodes in [('标题', title_nodes), ('容器', containers)]:
                if not isinstance(nodes, list) or not all(isinstance(n, html.HtmlElement) for n in nodes):
                    raise ValueError(label + ' XPath 必须返回元素列表，不能是字符串或数字')
                if len(nodes) != 1 or not text(nodes[0]):
                    raise ValueError(label + ' 必须唯一且非空')
            container = containers[0]
            if dom.getpath(container) != sample['candidate_container']['xpath']:
                raise ValueError('容器与任务证据位置不一致')
            if not any(dom.getpath(title_nodes[0]) == n['xpath'] and text(title_nodes[0]) == n['text']
                       for n in sample['h1_candidates']):
                raise ValueError('标题与任务证据不一致')
            selected = compiled['block_xpath'](container)
            if not isinstance(selected, list) or not all(isinstance(n, html.HtmlElement) for n in selected):
                raise ValueError('块 XPath 必须返回元素列表')
            actual = [n for n in selected if text(n)]
            # 独立遍历原始 DOM，避免用候选规则自己给自己生成参照。
            expected = [n for n in container if n.tag == 'p' and text(n)]
            expected_paths = [dom.getpath(n) for n in expected]
            actual_paths = [dom.getpath(n) for n in actual]
            evidence = [c for c in sample['children'] if c['tag'] == 'p' and c['text_characters'] > 0]
            if expected_paths != [c['xpath'] for c in evidence] or any(
                    text(n)[:140] != c['text_preview'] or len(text(n)) != c['text_characters']
                    for n, c in zip(expected, evidence)):
                raise ValueError('任务段落证据与快照不一致')
            same = actual_paths == expected_paths
            check(name + ' 原始段落', same,
                  f'actual={len(actual)}, expected={len(expected)}；逐节点对比位置和顺序。')
            result['pages'].append({'file': name, 'title': text(title_nodes[0]), 'source_sha256': hashes[name],
                                   'actual_count': len(actual), 'expected_count': len(expected), 'pass': same,
                                   'missing_xpaths': [p for p in expected_paths if p not in actual_paths],
                                   'extra_xpaths': [p for p in actual_paths if p not in expected_paths],
                                   'blocks': [{'index': i, 'xpath': dom.getpath(n), 'text': text(n)}
                                              for i, n in enumerate(actual, 1)]})
        except (etree.Error, ValueError, KeyError, TypeError) as exc:
            check(name + ' 执行', False, str(exc))
    result['accepted'] = bool(result['checks']) and all(c['pass'] for c in result['checks'])
    return result


def save_report(result, out, sample_dir):
    out.mkdir(parents=True, exist_ok=True)
    (out / 'check.json').write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding='utf-8')
    title = 'PASS：任务契约通过' if result['accepted'] else 'REJECT：候选未通过'
    lines = ['<!doctype html><html lang=zh-CN><meta charset=utf-8><title>XPath 候选检查</title>',
             '<style>body{font:16px/1.7 system-ui;max-width:1100px;margin:30px auto;padding:16px}',
             'td,th{border:1px solid #ddd;padding:8px}table{border-collapse:collapse;width:100%}',
             'code{overflow-wrap:anywhere}li{margin-bottom:12px}</style>', '<h1>' + title + '</h1>',
             '<p>语义审核：待做；发布：未执行；检查程序 AI 调用：0。</p>',
             '<p>只验证已知开发页的原始段落契约，不报告正文准确率，不修改正式配置或基准。</p>',
             '<table><tr><th>检查</th><th>结果</th><th>说明</th></tr>']
    for c in result['checks']:
        lines.append('<tr><td>' + escape(c['name']) + '</td><td>' + ('PASS' if c['pass'] else 'FAIL')
                     + '</td><td>' + escape(c['detail']) + '</td></tr>')
    lines.append('</table>')
    for p in result['pages']:
        link = (sample_dir / p['file']).resolve().as_uri()
        lines += ['<h2>' + escape(p['file']) + '</h2><p>' + escape(p['title']) + '</p>',
                  '<p><a href="' + escape(link, quote=True) + '">打开保存的原网页</a>；',
                  f"实际 {p['actual_count']} / 预期 {p['expected_count']} 段。</p>",
                  '<p>缺少 XPath：<code>' + escape(str(p['missing_xpaths'])) + '</code><br>',
                  '额外 XPath：<code>' + escape(str(p['extra_xpaths'])) + '</code></p>',
                  '<details><summary>展开完整原始段落与位置</summary><ol>']
        for b in p['blocks']:
            lines.append('<li>' + escape(b['text']) + '<br><code>' + escape(b['xpath']) + '</code></li>')
        lines.append('</ol></details>')
    lines.append('</html>')
    (out / 'check.html').write_text('\n'.join(lines), encoding='utf-8')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--candidate', type=Path, default=ROOT / 'output/agent_io/candidate.json')
    parser.add_argument('--task', type=Path, default=ROOT / 'output/agent_io/task.json')
    parser.add_argument('--output-dir', type=Path, default=ROOT / 'output/agent_io')
    args = parser.parse_args()
    try:
        task = json.loads(args.task.read_text(encoding='utf-8'))
        candidate = json.loads(args.candidate.read_text(encoding='utf-8'))
    except (OSError, ValueError) as exc:
        result = {'accepted': False, 'checks': [{'name': '读取 JSON', 'pass': False, 'detail': str(exc)}], 'pages': []}
    else:
        result = validate(task, candidate, ROOT / 'samples')
    save_report(result, args.output_dir, ROOT / 'samples')
    for c in result['checks']:
        if not c['pass']:
            print('FAIL: ' + c['name'] + '; ' + c['detail'])
    for p in result['pages']:
        print(f"{p['file']}: actual={p['actual_count']} expected={p['expected_count']}; "
              + ('PASS' if p['pass'] else 'FAIL'))
    print('CONTRACT PASS; semantic review pending; NOT PUBLISHED.' if result['accepted'] else 'REJECTED; NOT PUBLISHED.')
    print('REPORT: ' + str(args.output_dir / 'check.html'))
    return 0 if result['accepted'] else 1


if __name__ == '__main__':
    sys.exit(main())
