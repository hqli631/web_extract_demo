"""离线重跑第一个学习项目，汇总两类新闻模板的已知样例与检查。"""
import hashlib
import json
import os
import re
import subprocess
import sys
from datetime import datetime, timezone
from html import escape
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'output' / 'project1'
SINA = ['blog_01.html', 'collected_14a028de299edfab.html',
        'collected_af5904c15d1deebc.html']


def load(path):
    return json.loads(path.read_text(encoding='utf-8-sig'))


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def run_step(label, args, env):
    print(f'RUN: {label}', flush=True)
    result = subprocess.run([sys.executable, '-X', 'utf8', *args], cwd=ROOT,
                            env=env, capture_output=True, encoding='utf-8', errors='replace')
    record = {'label': label, 'arguments': args, 'returncode': result.returncode,
              'log': result.stdout + result.stderr}
    print(('PASS: ' if result.returncode == 0 else 'FAIL: ') + label, flush=True)
    return record


def source_info(filename):
    path = ROOT / 'samples' / filename
    # 手动保存的页面优先读取 saved-from-url 注释。
    head = path.read_text(encoding='utf-8', errors='replace')[:10000]
    saved = re.search(r'saved from url=\(\d+\)(https?://[^\s]+)', head)
    if saved:
        return saved.group(1)
    for item in load(ROOT / 'reports' / 'collection_manifest.json'):
        if item.get('file') == filename:
            return item.get('url')
    return None


def collect_pages():
    china = load(ROOT / 'output' / 'xpath_practice' / 'results.json')
    baseline = load(ROOT / 'output' / 'xpath_practice' / 'baseline.json')
    old = {p['file']: p for p in baseline['pages']}
    pages = []
    for page in china['pages']:
        filename = page['file']
        assert page['source_sha256'] == digest(ROOT / 'samples' / filename), '结果快照已过期'
        assert page['source_sha256'] == old[filename]['source_sha256'], '基准快照已变化'
        assert china['statuses'][filename] == '与基准一致', '原始结果与基准不同'
        assert page['semantic_review']['status'] == 'current', '保存的审核记录已过期或缺失'
        cleaned = page['cleaned']
        assert cleaned['status'] in {'applied', 'unchanged'}, '署名修正未正常执行'
        pages.append({'file': filename, 'template': '中新网', 'title': page['title'],
                      'source_sha256': page['source_sha256'], 'url': source_info(filename),
                      'raw_count': len(page['blocks']), 'content': cleaned['blocks'],
                      'authors': cleaned['authors'], 'sources': [], 'excluded': [],
                      'check': '冻结基准一致；保存的开发期审核有效；证据修正检查通过',
                      'audit_scope': '重放既有审核；本次没有调用 AI。图片像素未审核。'})
    assert len(pages) == 3, '本版范围固定为三篇中新网样例'
    for filename in SINA:
        page = load(ROOT / 'output' / 'xpath_sina' / (Path(filename).stem + '.json'))
        assert page['source_sha256'] == digest(ROOT / 'samples' / filename), '新浪结果快照已过期'
        pages.append({'file': filename, 'template': '新浪', 'title': page['title'],
                      'source_sha256': page['source_sha256'], 'url': source_info(filename),
                      'raw_count': len(page['raw_blocks']), 'content': page['content_blocks'],
                      'authors': [], 'sources': page['source_blocks'], 'excluded': page['excluded_blocks'],
                      'check': '固定样例的正文、来源、小标题、排除记录与顺序检查通过',
                      'audit_scope': '开发样例规则回归；居中样式只是小标题启发式，未完成通用性验证。'})
    return pages


def write_report(steps, pages, failure):
    status = 'failed' if failure else 'passed'
    totals = {'pages': len(pages), 'templates': len({p['template'] for p in pages}),
              'raw_blocks': sum(p['raw_count'] for p in pages),
              'readable_blocks': sum(len(p['content']) for p in pages),
              'authors': sum(len(p['authors']) for p in pages),
              'sources': sum(len(p['sources']) for p in pages),
              'excluded': sum(len(p['excluded']) for p in pages)}
    report = {'schema_version': 1, 'generated_at': datetime.now(timezone.utc).isoformat(),
              'status': status, 'failure': failure, 'scope': '6 篇已知开发样例、2 类模板；离线功能验收',
              'unseen_validation': 'not_completed', 'live_ai_calls': 0, 'totals': totals,
              'baseline_sha256': digest(ROOT / 'output/xpath_practice/baseline.json'),
              'implementation_sha256': {str(p.relative_to(ROOT)): digest(p) for p in [
                  Path(__file__), ROOT / 'xpath_batch.py', ROOT / 'xpath_rules.json',
                  ROOT / 'xpath_corrections.py', ROOT / 'xpath_semantic.py', ROOT / 'xpath_quality.py',
                  ROOT / 'author_candidates.py', ROOT / 'learning/xpath/xpath_practice_sina.py',
                  ROOT / 'learning/xpath/check_xpath_sina_batch.py', ROOT / 'config/xpath_sina.json']},
              'steps': steps, 'pages': pages}
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / 'results.json').write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
    rows, sections = [], []
    type_labels = {'paragraph': '段落', 'caption': '图说', 'subheading': '小标题'}
    for number, page in enumerate(pages, 1):
        filename = page['file']
        local = '../../samples/' + filename
        online = (f'<a href="{escape(page["url"], quote=True)}" target="_blank" rel="noopener">线上来源</a>'
                  if page['url'] else '无可核实线上来源')
        captions = sum(b['type'] == 'caption' for b in page['content'])
        headings = sum(b['type'] == 'subheading' for b in page['content'])
        rows.append(f'<tr><td>{escape(page["template"])}</td><td><a href="#page{number}">{escape(page["title"])}</a></td>'
                    f'<td>{page["raw_count"]}</td><td>{len(page["content"])}</td><td>{captions}</td><td>{headings}</td>'
                    f'<td>{len(page["authors"])}</td><td>{len(page["sources"])}</td><td>{len(page["excluded"])}</td></tr>')
        content = []
        for block in page['content']:
            kind = block['type']
            tag = 'h3' if kind == 'subheading' else 'p'
            content.append(f'<li><span class="badge">{type_labels[kind]}</span><{tag}>{escape(block["text"])}</{tag}>'
                           f'<details><summary>原文定位</summary><code>{escape(block["xpath"])}</code></details></li>')
        metadata = json.dumps({k: page[k] for k in ['authors', 'sources', 'excluded']}, ensure_ascii=False, indent=2)
        sections.append(f'<section id="page{number}"><h2>{escape(page["title"])}</h2>'
                        f'<p><a href="{local}" target="_blank" rel="noopener">打开本地原网页</a> · {online}</p>'
                        f'<p>文件：{escape(filename)}<br>SHA256：<code>{page["source_sha256"]}</code></p>'
                        f'<p>{escape(page["check"])}。{escape(page["audit_scope"])}</p>'
                        f'<details><summary>作者、来源及排除证据</summary><pre>{escape(metadata)}</pre></details>'
                        f'<ol>{"".join(content)}</ol><a href="#top">返回汇总</a></section>')
    logs = ''.join(f'<details><summary>{escape(s["label"])}：退出码 {s["returncode"]}</summary>'
                   f'<pre>{escape(s["log"])}</pre></details>' for s in steps)
    doc = ('<!doctype html><html lang="zh-CN"><meta charset="utf-8"><title>第一个项目验收报告</title>'
           '<style>body{max-width:1180px;margin:30px auto;padding:0 22px;font:16px/1.7 sans-serif;color:#172b40}'
           'table{border-collapse:collapse;width:100%}td,th{border:1px solid #ccd5df;padding:8px}section{border-top:2px solid #ccd5df;margin-top:36px}'
           'pre{white-space:pre-wrap}code{overflow-wrap:anywhere}.badge{background:#e8eff8;padding:3px 8px;border-radius:4px}li{margin:18px 0}</style>'
           f'<h1 id="top">第一个项目：新闻正文结构化提取 v1</h1><p>本次状态：<strong>{status}</strong>；范围：六篇开发样例、两种模板。</p>'
           f'<p>原始块 {totals["raw_blocks"]}；可读内容 {totals["readable_blocks"]}；作者 {totals["authors"]}；来源 {totals["sources"]}；排除 {totals["excluded"]}。</p>'
           '<p>这是可复现的功能演示，不是跨站准确率评测。没有新增未见样本验证，本次 AI 调用为 0。保存的 AI 审核属于既有开发证据。</p>'
           '<p>学习操作：①打开博盈特焊的本地原网页；②核对小标题与最后一段，查看来源字段；③打开中新网访谈，确认记者问题与图说仍保留。原页面依赖的远程样式或图片可能不可用，不能据此认定文字漏提。</p>'
           f'<p>{escape(failure or "本轮必需检查均已通过。")}</p>'
           '<table><tr><th>模板</th><th>标题</th><th>原始</th><th>可读</th><th>图说</th><th>小标题</th><th>作者</th><th>来源</th><th>排除</th></tr>'
           + ''.join(rows) + '</table><h2>运行与检查日志</h2>' + logs + ''.join(sections) + '</html>')
    (OUT / 'index.html').write_text(doc, encoding='utf-8')
    return report


def main():
    env = dict(os.environ)
    env['PYTHONIOENCODING'] = 'utf-8'
    env['PYTHONPATH'] = os.pathsep.join(filter(None, [str(ROOT / '.deps'), str(ROOT), env.get('PYTHONPATH')]))
    steps = []
    pages = []
    failure = None
    baseline = ROOT / 'output/xpath_practice/baseline.json'
    before = digest(baseline)
    commands = [('中新网批量提取与历史审核重放', ['xpath_batch.py'])]
    commands += [(f'新浪提取：{name}', ['learning/xpath/xpath_practice_sina.py', name]) for name in SINA]
    commands += [('新浪三页分类回归', ['learning/xpath/check_xpath_sina_batch.py']),
                 ('正常链接及风险声明保护', ['learning/xpath/check_xpath_sina.py']),
                 ('工程单元测试', ['-m', 'unittest', 'discover', '-s', 'tests'])]
    try:
        for label, args in commands:
            step = run_step(label, args, env)
            steps.append(step)
            if step['returncode'] != 0:
                raise RuntimeError(f'{label}失败，详见报告日志')
        assert before == digest(baseline), '冻结基准被修改'
        pages = collect_pages()
    except Exception as exc:
        failure = str(exc)
    report = write_report(steps, pages, failure)
    print(f'STATUS: {report["status"]}; report: {OUT / "index.html"}')
    return 1 if failure else 0


if __name__ == '__main__':
    raise SystemExit(main())
