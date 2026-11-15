"""Offline evidence display: source snapshots, reference extraction, model code."""
from pathlib import Path
import json
import hashlib
import re
from html import escape
from urllib.parse import urljoin, urlsplit, unquote
from lxml import html

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'output/stage5/unit2/showcase'
RUN = ROOT / 'output/stage5/unit2/cloud_run_20261115'


def read(path):
    return json.loads(path.read_text(encoding='utf-8'))


def source_url(raw, tree):
    urls = tree.xpath('//link[@rel="canonical"]/@href | //meta[@property="og:url"]/@content')
    if urls:
        return urls[0]
    match = re.search(r'saved from url=\(\d+\)(https?://[^\s>]+)', raw[:3000])
    if match:
        return match.group(1)
    bases = tree.xpath('//base/@href')
    return bases[0] if bases and bases[0].startswith(('http://','https://')) else ''


def asset_cache():
    cache = {}
    for path in (ROOT / 'output/stage3/display').glob('*/*/manifest.json'):
        manifest = read(path)
        # Prefer processed CSS referenced by the display page: its assets are local.
        processed = []
        display = path.parent / (path.parent.name + '.html')
        if display.exists():
            processed = html.document_fromstring(display.read_bytes()).xpath('//link[contains(@rel,"stylesheet")]/@href')
        css_index = 0
        for item in manifest.get('assets', []):
            local = path.parent / item['local']
            if item['kind'] == 'css':
                if css_index < len(processed):
                    candidate = path.parent / processed[css_index]
                    if candidate.is_file():
                        local = candidate
                css_index += 1
            if local.is_file():
                cache.setdefault(item['url'], local)
    return cache


def snapshot(source, dest, original_url, cache):
    tree = html.document_fromstring(source.read_bytes())
    for node in list(tree.xpath('//script|//iframe|//object|//embed|//base|//meta[translate(@http-equiv,"REFSH","refsh")="refresh"]')):
        node.drop_tree()
    for node in tree.iter():
        if not isinstance(node.tag, str):
            continue
        for name in list(node.attrib):
            if name.lower().startswith('on') or name.lower() in {'srcdoc','srcset'}:
                del node.attrib[name]
        for attr in ('src', 'href'):
            value = node.get(attr)
            if not value or value.startswith(('data:', '#')):
                continue
            if value.lower().startswith('javascript:'):
                node.attrib.pop(attr, None)
                continue
            local = None
            if not urlsplit(value).scheme and not value.startswith(('/', '\\')):
                candidate = source.parent / unquote(value.split('?')[0])
                try:
                    if candidate.is_file():
                        local = candidate
                except OSError:
                    pass
            absolute = urljoin(original_url, value)
            target = local or cache.get(absolute)
            if target:
                import os
                node.set(attr, Path(os.path.relpath(target, dest.parent)).as_posix())
            elif attr == 'src' or node.tag == 'link':
                node.attrib.pop(attr, None)
            elif absolute.startswith(('https://','http://')):
                node.set(attr, absolute)
                node.set('target', '_blank')
    head = tree.find('head')
    if head is None:
        head = html.Element('head')
        tree.insert(0, head)
    csp = html.Element('meta')
    csp.set('http-equiv', 'Content-Security-Policy')
    csp.set('content', "default-src 'none'; style-src 'self' 'unsafe-inline' file:; img-src 'self' data: file:; font-src 'self' data: file:; script-src 'none'; form-action 'none'")
    head.insert(0, csp)
    head.insert(0, html.Element('meta', charset='utf-8'))
    style = html.Element('style')
    style.text = '#artibody,.left_zw{outline:3px solid #17825b!important;outline-offset:6px}h1{box-shadow:0 0 0 2px #2267c2!important}'
    head.append(style)
    dest.write_bytes(html.tostring(tree, encoding='utf-8', method='html', doctype='<!doctype html>'))


def build():
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / 'pages').mkdir(exist_ok=True)
    summary = read(RUN / 'summary.json')
    reference = read(ROOT / 'output/stage3/repair/results.json')
    outputs = {p['file']: p['after'] for p in reference['pages'] if p.get('role') == 'generation'}
    cache = asset_cache()
    pages = []
    for split in ('train', 'dev'):
        row = json.loads((ROOT / f'output/stage5/unit2/sft_prep/{split}.jsonl').read_text(encoding='utf-8'))
        for item in row['sources']:
            source = ROOT / item['path']
            raw_bytes = source.read_bytes()
            if hashlib.sha256(raw_bytes).hexdigest() != item['sha256']:
                raise ValueError('source changed')
            raw = raw_bytes.decode('utf-8', errors='replace')
            tree = html.document_fromstring(raw_bytes)
            url = source_url(raw, tree)
            result = outputs[item['path']]
            name = source.stem + '.html'
            snapshot(source, OUT / 'pages' / name, url, cache)
            pages.append(dict(split=split, title=result['title'], file=item['path'], url=url,
                              snapshot='pages/' + name, source_sha256=item['sha256'], reference=result))
    before, after = [read(RUN / (name + '_generation.json')) for name in ('before','after')]
    payload = dict(pages=pages, before=before['outputs'], after=after['outputs'], summary=summary)
    (OUT / 'evidence.json').write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding='utf-8')
    data = json.dumps(payload, ensure_ascii=False).replace('<', '\\u003c')
    page = '''<!doctype html><html lang="zh"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>训练网页与实际效果</title>
<style>*{box-sizing:border-box}body{margin:0;background:#f4f6fa;color:#203047;font:15px/1.65 system-ui,"Microsoft YaHei",sans-serif}header,main{max-width:1500px;margin:auto;padding:22px}h1{font-size:28px;margin:0 0 10px}h2{font-size:19px}.cards{display:grid;grid-template-columns:repeat(4,1fr);gap:12px}.card,.panel{background:white;border:1px solid #dce3ec;border-radius:10px;padding:17px;margin-bottom:15px}.card b{display:block;font-size:22px;color:#146b52}.notice{background:#fff2d8;border-left:4px solid #b77910;padding:12px}.layout{display:grid;grid-template-columns:minmax(0,1.25fr) minmax(380px,1fr);gap:16px}iframe{width:100%;height:740px;border:1px solid #d1d9e3;background:#fff}select,button{padding:9px;border:1px solid #b8c8d9;border-radius:6px;background:white;font:inherit;cursor:pointer}select{width:100%;margin:8px 0}.scroll{max-height:650px;overflow:auto}.block{padding:9px;border-bottom:1px solid #e3e7ed}.kind{font-size:12px;color:#176846;background:#e7f3ef;padding:2px 6px}.meta{background:#edf2fa}.exclude{background:#fff1ee}pre{white-space:pre-wrap;overflow-wrap:anywhere;font:13px/1.55 Consolas,monospace;background:#f4f6f9;padding:12px;max-height:500px;overflow:auto}.codegrid{display:grid;grid-template-columns:1fr 1fr;gap:14px}a{color:#1765aa}small{color:#66758a}details{margin:10px 0}summary{cursor:pointer;font-weight:600}#title{font-size:18px}table{border-collapse:collapse;width:100%}td,th{border-bottom:1px solid #ddd;padding:9px;text-align:left}button.active{background:#e4f1ec} @media(max-width:950px){.layout,.codegrid,.cards{grid-template-columns:1fr}} </style>
<header><h1>训练用了哪些网页？实际效果如何？</h1><p>岗位主线：同簇少量网页 → 模型生成抽取代码 → CPU批量执行。这里把参考代码、训练模型和质量证据分开展示。</p>
<div class="cards"><div class="card"><b>1 条训练任务</b>新浪3篇共同输入，参与参数更新</div><div class="card"><b>1 条开发任务</b>中新网3篇，仅检查不更新参数</div><div class="card"><b>1 次真实更新</b>540672个LoRA参数，保存重载通过</div><div class="card"><b>效果尚未达标</b>模型生成代码存在字段与类型错误</div></div>
<div class="notice">本次训练验证了流程，没有证明质量提升。下方正文来自<strong>历史人工/对话审核过的参考v2代码</strong>，不是小模型训练后的提取结果。小模型候选未执行，不能拿参考输出冒充模型成果。</div></header>
<main><div class="panel"><h2>① 选择网页：查看来源与正文</h2><select id="pick" aria-label="选取网页"></select><div id="title"></div><div id="source"></div></div>
<div class="layout"><section class="panel"><h2>网页完整静态快照与容器定位</h2><p><small>绿框为参考正文容器，蓝框为标题。保持原DOM与可用本地资源；已停用脚本和外部动态内容，不能保证与在线页面像素一致。原始文件未修改。</small></p><iframe id="frame" title="网页快照" sandbox="allow-same-origin"></iframe></section>
<section class="panel"><h2>参考抽取器的真实输出</h2><p id="counts"></p><button id="b0" class="active" onclick="mode(0)">正文全文</button> <button id="b1" onclick="mode(1)">元数据</button> <button id="b2" onclick="mode(2)">排除内容</button><div id="blocks" class="scroll"></div><p><small>块数是输出规模，不是准确率。图片像素、动态加载内容未识别，完整性可能仍为unknown。</small></p></section></div>
<section class="panel"><h2>② 这一个布局任务：模型训练前后生成了什么？</h2><p id="modelstate"></p><div id="issues" class="notice"></div><div class="codegrid"><div><h3>基座模型 · 训练前</h3><pre id="before"></pre></div><div><h3>基座＋LoRA · 一次更新后</h3><pre id="after"></pre></div></div><p>本页不执行候选代码。输出可以解析为Python，也可能提取失败或字段不符合要求。</p></section>
<section class="panel"><h2>③ 当前成果与下一步</h2><table><tr><th>层面</th><th>当前结论</th></tr><tr><td>已有项目</td><td>布局分组、XPath参考代码、CPU批量抽取、证据/回归、Rubrics原型可演示。</td></tr><tr><td>真实训练</td><td>单次LoRA参数更新、保存与重载已完成；并非GRPO。</td></tr><tr><td>训练后能力</td><td>新浪生成文本相同，中新网有变化；两任务静态契约仍失败，尚不可采用。</td></tr><tr><td>质量与泛化</td><td>只有历史任务，没有独立未见测试，不能报告提升率。</td></tr><tr><td>下一步来源</td><td>从当前字段/类型等失败出发，完善任务输入和多布局监督样例；冻结新的测试，再做基座/适配器同预算比较。先不盲目增加轮数。</td></tr></table><p>服务器按天租用，按用户要求保留；没有新GPU任务在运行。</p><p><a href="../cloud_run_20261115/index.html">查看参数更新证据</a> · <a href="../../../../docs/STAGE5_CLOUD_SMOKE.md">操作与知识回顾</a></p></section></main>
<script id="data" type="application/json">DATA</script><script>
const D=JSON.parse(document.getElementById('data').textContent);let idx=0,m=0;const $=id=>document.getElementById(id);D.pages.forEach((p,i)=>{let o=document.createElement('option');o.value=i;o.textContent=(p.split==='train'?'训练 · 新浪':'开发 · 中新网')+'｜'+p.title;$('pick').append(o)});$('pick').onchange=()=>{idx=Number($('pick').value);show()};
function mode(v){m=v;renderBlocks();[0,1,2].forEach(i=>$('b'+i).classList.toggle('active',i===m))}
function renderBlocks(){const p=D.pages[idx],g=['blocks','metadata','excluded'][m];$('blocks').replaceChildren();p.reference[g].forEach((b,i)=>{const e=document.createElement('div');e.className='block '+(m===1?'meta':m===2?'exclude':'');const tag=document.createElement('span');tag.className='kind';tag.textContent=(i+1)+' · '+b.kind;const t=document.createElement('p');t.textContent=b.text;const xp=document.createElement('small');xp.textContent=b.xpath;e.append(tag,t,xp);$('blocks').append(e)});if(!p.reference[g].length)$('blocks').textContent='本页此列表为空。'}
function show(){const p=D.pages[idx],a=D.before.find(x=>x.split===p.split),b=D.after.find(x=>x.split===p.split),c=D.summary.comparison.find(x=>x.split===p.split);$('title').textContent=p.title;$('source').replaceChildren();let s=document.createElement('small');s.textContent=p.file+' ｜ '+(p.split==='train'?'参与参数更新':'仅开发检查，不参与更新');$('source').append(s);if(p.url){let link=document.createElement('a');link.href=p.url;link.target='_blank';link.rel='noopener';link.textContent='  打开原网站';$('source').append(link)}$('frame').src=p.snapshot;$('counts').textContent='正文 '+p.reference.blocks.length+' 块｜元数据 '+p.reference.metadata.length+' 条｜排除 '+p.reference.excluded.length+' 条';$('before').textContent=a.text;$('after').textContent=b.text;$('modelstate').textContent='三个同簇网页共同组成一个代码生成任务，不是每篇分别训练。'+(c.same_text?'本任务训练前后生成文本相同。':'本任务训练后生成文本有变化。')+' 长度 '+c.before_tokens+' → '+c.after_tokens+' token。';$('issues').textContent='静态检查：'+[...new Set([...c.before_static.issues,...c.after_static.issues])].join('；')+'。这些输出未执行，尚无模型正文提取成功结果。';mode(m)}show();</script></html>'''
    (OUT / 'index.html').write_text(page.replace('DATA', data), encoding='utf-8')
    print('SHOWCASE: 3 train pages + 3 dev pages; reference extraction separate from model outputs.')
    print(OUT / 'index.html')


if __name__ == '__main__':
    build()
