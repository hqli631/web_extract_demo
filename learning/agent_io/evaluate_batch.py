"""冻结样例上的定位边界实验；不修改规则，不声称盲测准确率。"""
import hashlib
import json
import sys
from collections import Counter
from html import escape
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
from lxml import etree, html

CONFIG = ROOT / 'config/agent_eval_batch.json'
OUT = ROOT / 'output/agent_io/evaluation'


def sha(path):
    data = path.read_bytes()
    # Git 在 Windows 可能转换文本换行；配置与代码按 LF 规范化，HTML快照保持字节哈希。
    if path.suffix in {'.json', '.py'}:
        data = data.replace(b'\r\n', b'\n')
    return hashlib.sha256(data).hexdigest()


def read(path):
    return json.loads(path.read_text(encoding='utf-8'))


def norm(node):
    return ' '.join(node.text_content().split())


def verify_freeze(config, root=ROOT):
    for name, expected in config['frozen_files'].items():
        path = root / name
        if not path.is_file() or sha(path) != expected:
            raise ValueError('冻结输入变化：' + name + '；不要覆盖冻结记录来消除差异，应另建版本。')
    # 对真实页按字节去重；受控变体显式继承源页，不算独立数据。
    seen = {}
    for case in config['cases']:
        if case['role'] != 'synthetic_probe':
            value = config['frozen_files'][case['source']]
            if value in seen:
                raise ValueError('真实页快照重复：' + case['id'] + ' 与 ' + seen[value])
            seen[value] = case['id']


def execute_case(case, rules, root=ROOT):
    tree = html.document_fromstring((root / case['source']).read_bytes())
    mutation = case.get('mutation')
    if mutation:
        containers = tree.xpath("//div[@id='artibody']")
        if len(containers) != 1:
            raise ValueError('受控实验源页容器不是一个')
        container = containers[0]
        paragraphs = [n for n in container if n.tag == 'p' and norm(n)]
        if mutation == 'wrap_first_p':
            target = paragraphs[0]
            position = container.index(target)
            wrapper = html.Element('div', {'class': 'experiment-wrapper'})
            container.insert(position, wrapper)
            wrapper.append(target)
        elif mutation == 'wrap_all_p':
            for target in paragraphs:
                position = container.index(target)
                wrapper = html.Element('div', {'class': 'experiment-wrapper'})
                container.insert(position, wrapper)
                wrapper.append(target)
        elif mutation == 'rename_container':
            container.set('id', 'article-body-v2')
        else:
            raise ValueError('未知受控变换')
    titles = tree.xpath(rules['title_xpath'])
    containers = tree.xpath(rules['container_xpath'])
    result = {'id': case['id'], 'role': case['role'], 'source': case['source'],
              'mutation': mutation, 'title_count': len(titles), 'container_count': len(containers),
              'raw_block_count': 0, 'status': None, 'semantic_review': 'not_performed',
              'expected_raw_count': case.get('expected_raw_count'), 'blocks': []}
    if len(containers) != 1:
        result['status'] = 'container_not_unique'
    elif len(titles) != 1 or not norm(titles[0]):
        result['status'] = 'title_not_unique'
    else:
        container = containers[0]
        selected = container.xpath(rules['block_xpath'])
        if not isinstance(selected, list) or not all(isinstance(n, html.HtmlElement) for n in selected):
            raise ValueError('块规则没有返回元素列表')
        nodes = [n for n in selected if norm(n)]
        result['raw_block_count'] = len(nodes)
        result['blocks'] = [{'index': i, 'text': norm(n), 'xpath': tree.getroottree().getpath(n)}
                            for i, n in enumerate(nodes, 1)]
        if not nodes:
            result['status'] = 'empty_blocks'
        elif case.get('expected_raw_count') is not None and len(nodes) != case['expected_raw_count']:
            result['status'] = 'raw_count_mismatch'
        else:
            result['status'] = 'structural_contract_pass'
    result['experiment_expectation_met'] = result['status'] == case['expected_status']
    result['interpretation'] = case['interpretation']
    return result


def evaluate(config, root=ROOT):
    verify_freeze(config, root)
    rules = read(root / 'output/agent_io/candidate.json')['rules']
    cases = [execute_case(c, rules, root) for c in config['cases']]
    return {'batch_id': config['batch_id'], 'cases': cases,
            'experiment_checks_pass': all(c['experiment_expectation_met'] for c in cases),
            'groups': dict(Counter(c['role'] for c in cases)), 'unseen_page_count': 0,
            'semantic_accuracy': None, 'ai_calls': 0, 'published': False,
            'limits': config['limits']}


def save(result):
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / 'results.json').write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding='utf-8')
    lines = ['<!doctype html><html lang=zh-CN><meta charset=utf-8><title>冻结评估实验</title>',
             '<style>body{font:16px/1.7 system-ui;max-width:1200px;margin:30px auto;padding:16px}',
             'table{border-collapse:collapse;width:100%}td,th{border:1px solid #ddd;padding:8px}',
             'code{overflow-wrap:anywhere}</style><h1>冻结规则与样例：定位边界实验</h1>',
             '<p>未见页 0；不报告语义准确率。受控变体不是新采集网页。检查符合预期，不等于所有页面抽取成功。</p>']
    if result.get('error'):
        lines.append('<h2>实验中止</h2><p>' + escape(result['error']) + '</p>')
    else:
        lines.append('<table><tr><th>样例/用途</th><th>标题/容器数</th><th>提取/参照段数</th><th>实际状态</th><th>实验预期是否符合</th></tr>')
        for c in result['cases']:
            lines.append('<tr><td>' + escape(c['id']) + '<br>' + escape(c['role'])
                         + '</td><td>' + str(c['title_count']) + '/' + str(c['container_count']) + '</td><td>'
                         + str(c['raw_block_count']) + '/' + str(c['expected_raw_count'])
                         + '</td><td>' + escape(c['status']) + '</td><td>'
                         + ('符合' if c['experiment_expectation_met'] else '异常') + '</td></tr>')
        lines.append('</table>')
        for c in result['cases']:
            link = (ROOT / c['source']).resolve().as_uri()
            lines += ['<h2>' + escape(c['id']) + '</h2><p>' + escape(c['interpretation']) + '</p>',
                      '<p><a href="' + escape(link, quote=True) + '">打开源网页</a>'
                      + ('；变体仅在内存构造，源文件未改动。' if c['mutation'] else '；保存的原始快照。') + '</p>',
                      '<details><summary>查看实际提取文本</summary>']
            lines += ['<p>' + escape(b['text']) + '<br><code>' + escape(b['xpath']) + '</code></p>' for b in c['blocks']]
            lines.append('</details>')
        lines.append('<h2>下一批真实未见页的要求</h2><p>先冻结规则、质量标准与采样条件，再采集独立新页面；按 URL 和内容去重，记录采集时间及快照哈希。抽取后独立审查完整性与杂质。用评估结果调试过的页面应改记为开发/回归，另建评估批次。</p>')
    lines.append('</html>')
    (OUT / 'index.html').write_text('\n'.join(lines), encoding='utf-8')


def main():
    try:
        result = evaluate(read(CONFIG))
    except (OSError, ValueError, KeyError, TypeError, etree.Error) as exc:
        result = {'experiment_checks_pass': False, 'error': str(exc), 'cases': []}
    save(result)
    if result.get('error'):
        print('FROZEN BATCH REJECTED: ' + result['error'])
        return 1
    for c in result['cases']:
        print(f"{c['id']}: containers={c['container_count']}; blocks={c['raw_block_count']}/{c['expected_raw_count']}; {c['status']}")
    print('EXPERIMENT CHECKS: ' + ('PASS' if result['experiment_checks_pass'] else 'FAIL'))
    print('UNSEEN PAGES: 0; semantic accuracy: NOT MEASURED; rules unchanged.')
    print('REPORT: ' + str(OUT / 'index.html'))
    return 0 if result['experiment_checks_pass'] else 1


if __name__ == '__main__':
    sys.exit(main())
