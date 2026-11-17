"""Readable offline reports; render saved evidence without executing extraction or API calls."""
import argparse
from collections import Counter
import difflib
from html import escape
import json
import os
from pathlib import Path
from urllib.parse import urlsplit

ROOT = Path(__file__).resolve().parent
LABELS = {'generation':'生成样本','development_feedback':'开发反馈','final_holdout':'最终测试',
          'historical_exposed_regression':'历史参考回归','paragraph':'段落','subheading':'小标题',
          'caption':'图说','code_block':'代码块','table':'表格','list':'列表','list_item':'列表项',
          'definition_term':'定义项','definition_description':'定义说明','footnote':'脚注',
          'author':'作者','editor':'责任编辑','source':'来源','published_at':'发布时间','date':'发布时间',
          'production_credit':'制作署名','metadata':'其他页面信息','excluded':'排除项',
          'pass':'检查通过','failed':'检查失败','needs_review':'待审核','development_failed':'开发检查未通过',
          'holdout_failed':'最终测试未通过','succeeded':'成功','started':'已发起'}

def e(value):
    return escape(str(value), quote=True)

def label(value):
    return LABELS.get(value, value)

def read_json(path, default=None):
    return json.loads(path.read_text(encoding='utf-8-sig')) if path.exists() else default

def local_file(out, name):
    path = (out/name).resolve()
    if not path.is_relative_to(out.resolve()):
        raise ValueError('Artifact path leaves report directory')
    return path

def link(url, title):
    if urlsplit(str(url)).scheme.lower() not in {'','http','https','file'}:
        return e(title)
    return '<a href="'+e(url)+'" target="_blank" rel="noopener">'+e(title)+'</a>'

def artifact(out, name, title):
    return link(name,title) if local_file(out,name).is_file() else '<span class="muted">'+e(title)+'（未生成）</span>'

def source_link(out, path):
    absolute = ROOT/path
    if not absolute.is_file():
        return '<span class="muted">未保存HTML快照</span>'
    try:
        url = os.path.relpath(absolute,out).replace(chr(92),'/')
    except ValueError:
        url = absolute.as_uri()
    return link(url,'原始 HTML 快照')

def badge(status):
    tone = 'good' if status in {'pass','succeeded'} else 'warn' if status in {'needs_review','reference','running'} else 'bad'
    return '<span class="badge '+tone+'">'+e(label(status))+'</span>'

def details(title, content):
    return '<details><summary>'+e(title)+'</summary>'+content+'</details>'

def code(value):
    return '<pre>'+e(value)+'</pre>'

def json_view(value):
    return code(json.dumps(value,ensure_ascii=False,indent=2))

def metadata_table(rows):
    if not rows:
        return '<p class="muted">本次未提取独立页面信息。</p>'
    return '<div class="table-wrap"><table><thead><tr><th>类别</th><th>内容</th><th>原文证据</th></tr></thead><tbody>'+''.join(
        '<tr><td><span class="kind">'+e(label(r.get('type',r.get('kind','metadata'))))+'</span></td><td>'+e(r.get('text',''))+
        '</td><td>'+details('查看 XPath',code(r.get('xpath','')) + ('属性：'+e(r['attribute']) if r.get('attribute') else ''))+'</td></tr>' for r in rows)+'</tbody></table></div>'

def block_html(block, index):
    kind = block.get('type',block.get('kind','paragraph'))
    text = e(block.get('text',''))
    if kind=='code_block':
        content='<pre class="body-code">'+text+'</pre>'
    elif kind=='table' and block.get('rows'):
        content='<div class="table-wrap"><table class="body-table"><tbody>'+''.join('<tr>'+''.join('<td>'+e(c)+'</td>' for c in row)+'</tr>' for row in block['rows'])+'</tbody></table></div>'
    elif kind=='subheading':
        content='<h3>'+text+'</h3>'
    else:
        content='<p>'+text+'</p>'
    evidence=code(block.get('xpath',''))
    if block.get('segment_index') is not None:
        evidence+='<p>容器分段索引：'+e(block['segment_index'])+'</p>'
    return '<li class="body-block"><div class="block-label"><span class="block-number">'+str(index)+'</span><span class="kind">'+e(label(kind))+'</span></div>'+content+details('XPath 原文定位',evidence)+'</li>'

def issues_html(issues):
    if not issues:
        return '<p class="muted">未记录结构检查问题。语义完整性仍需单独评估。</p>'
    return '<ul class="issues">'+''.join('<li><strong>'+e(i.get('kind','问题'))+'</strong><p>'+e(i.get('preview',i.get('message','')))+'</p>'+ (details('查看位置',code(i['xpath'])) if i.get('xpath') else '')+'</li>' for i in issues)+'</ul>'

CSS = '''
:root{--ink:#18314a;--muted:#61748a;--line:#dce5ee;--blue:#235fba;--paper:#fff;--bg:#f3f6fa}
*{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--ink);font:15px/1.75 "Segoe UI","Microsoft YaHei",sans-serif}a{color:var(--blue);text-underline-offset:3px}button,input,select{font:inherit}button{cursor:pointer}button:focus-visible,a:focus-visible,input:focus-visible,select:focus-visible{outline:3px solid #e6a635;outline-offset:3px}[hidden]{display:none!important}.wrap{max-width:1440px;margin:auto;padding:30px 32px 64px}.hero{background:linear-gradient(115deg,#153952,#245d75);color:#fff;padding:28px 32px;border-radius:18px}.eyebrow{font-size:12px;letter-spacing:2px;color:#b8dce8}.hero h1{font-size:30px;line-height:1.4;margin:8px 0}.hero p{margin:8px 0;color:#d7e7ef}.hero .badge{margin-left:8px}.toplinks{display:flex;gap:16px;flex-wrap:wrap;margin-top:16px}.toplinks a{color:#dfedff}.metrics{display:grid;grid-template-columns:repeat(5,minmax(0,1fr));gap:12px;margin:18px 0}.metric{background:#fff;border:1px solid var(--line);border-radius:12px;padding:14px 18px}.metric small{display:block;color:var(--muted)}.metric strong{font-size:24px;display:block;overflow-wrap:anywhere}.metric .model{font-size:17px;line-height:42px}.metric span{font-size:12px;color:var(--muted)}.notice{border-left:3px solid #d2a453;background:#fff9ed;padding:12px 16px;margin:16px 0;border-radius:4px}.tabs{display:flex;gap:8px;flex-wrap:wrap;padding:12px 0;border-bottom:1px solid var(--line);margin-bottom:22px}.tab{border:1px solid var(--line);background:#fff;padding:9px 20px;border-radius:9px;color:var(--muted)}.tab[aria-selected=true]{background:var(--ink);border-color:var(--ink);color:white}.panel{background:white;border:1px solid var(--line);border-radius:14px;padding:24px;margin-bottom:20px}.panel h2{font-size:22px;margin:0 0 14px}h3{font-size:18px;margin:20px 0 10px}h4{margin:14px 0 8px}.muted{color:var(--muted)}.small{font-size:13px}.table-wrap{overflow:auto}table{width:100%;border-collapse:collapse;text-align:left;margin:12px 0}th{color:var(--muted);font-size:13px;background:#f4f7fa}td,th{padding:10px 12px;border-bottom:1px solid var(--line);vertical-align:top}td{overflow-wrap:anywhere}td details{min-width:90px;margin:0}td pre{max-width:400px}.badge,.kind{display:inline-block;padding:2px 9px;border-radius:5px;font-size:12px;font-weight:600;white-space:nowrap}.kind{color:#46627e;background:#edf3f9}.good{background:#e2f3ed;color:#196b50}.warn{background:#fff0d4;color:#89600a}.bad{background:#fde8e7;color:#ac3434}.workspace{display:grid;grid-template-columns:260px minmax(0,1fr);gap:20px;align-items:start}.sidebar{position:sticky;top:16px;background:#fff;border:1px solid var(--line);border-radius:14px;padding:18px}.sidebar h3{margin:0 0 10px}.sidebar input,.sidebar select,.round-select{border:1px solid #c9d6e4;background:#fff;border-radius:7px;padding:8px;width:100%;margin-bottom:10px}.page-nav{display:grid;gap:8px;margin-top:6px;max-height:58vh;overflow:auto}.page-button{text-align:left;border:1px solid var(--line);background:#fff;border-radius:8px;padding:10px 12px;color:var(--ink);width:100%}.page-button[aria-pressed=true]{border-color:var(--blue);background:#edf4ff;box-shadow:inset 3px 0 var(--blue)}.page-button small{display:block;color:var(--muted);margin-top:3px}.article{scroll-margin-top:16px}.article h2{font-size:26px;line-height:1.45}.article-links{display:flex;gap:15px;flex-wrap:wrap;margin:12px 0}.article-meta{display:flex;gap:12px;flex-wrap:wrap;color:var(--muted);font-size:13px}.content-title{display:flex;align-items:center;justify-content:space-between;gap:12px;margin-top:26px;border-top:1px solid var(--line);padding-top:20px}.content-title h3{margin:0}.body-list{list-style:none;margin:16px 0;padding:0}.body-block{padding:18px 0;border-bottom:1px solid #edf1f5}.block-label{display:flex;gap:8px;align-items:center}.block-number{font-size:12px;color:#7c8da0;min-width:22px}.body-block p{font-size:16px;line-height:1.95;margin:10px 0;color:#243c51}.body-block h3{font-size:20px;line-height:1.6}.body-block details{font-size:12px}.body-table td{border:1px solid var(--line)}details{margin:12px 0}summary{cursor:pointer;color:var(--blue);overflow-wrap:anywhere}pre{background:#f3f6fa;border:1px solid #e5ebf2;padding:14px;border-radius:8px;white-space:pre-wrap;overflow-wrap:anywhere;font:13px/1.7 Consolas,monospace;color:#29435d;max-height:540px;overflow:auto}.body-code{white-space:pre;overflow:auto;overflow-wrap:normal}.toolbar{display:flex;gap:10px;align-items:center;flex-wrap:wrap}.quiet{background:#f3f6fa;color:var(--ink);border:1px solid var(--line);border-radius:7px;padding:5px 10px;font-size:12px}.split{display:grid;grid-template-columns:1fr 1fr;gap:18px}.rule-row{padding:14px 0;border-bottom:1px solid var(--line)}.rule-row p{margin:0}.rule-row pre{margin:8px 0}.step{border-left:3px solid #b8cadf;padding-left:18px;margin:20px 0}.step h3{margin-bottom:6px}.issues li{padding:8px 0}.issues p{margin:2px 0}.comparison{background:#f7faff;border:1px solid #dce8f8;border-radius:8px;padding:14px}.empty{padding:24px;color:var(--muted)}.foot{font-size:12px;color:var(--muted);margin-top:24px}.count-note{font-size:12px;line-height:1.5}.round-select{max-width:280px}.nojs{background:#fff0d4;padding:10px}.skip{position:absolute;left:-9999px}.skip:focus{left:16px;top:8px;background:#fff;padding:10px;z-index:10}
@media(max-width:980px){.metrics{grid-template-columns:repeat(3,1fr)}.workspace{grid-template-columns:220px minmax(0,1fr)}.wrap{padding:20px}.hero{padding:22px}.split{grid-template-columns:1fr}}
@media(max-width:680px){.wrap{padding:12px}.hero h1{font-size:23px}.metrics{grid-template-columns:1fr 1fr}.metric{padding:12px}.workspace{display:block}.sidebar{position:static;margin-bottom:16px}.page-nav{max-height:220px}.panel{padding:17px}.article h2{font-size:22px}.tab{padding:8px 13px}.content-title{align-items:start}.toplinks{gap:10px}}
@media print{body{background:white}.wrap{padding:0}.hero{background:white;color:#18314a}.hero p,.hero a{color:#18314a}.tabs,.sidebar,.quiet{display:none}.workspace{display:block}.panel{break-inside:auto}.article[hidden]{display:block!important}pre{max-height:none}.view[hidden]{display:none!important}}
'''

JS = '''
(()=>{
const tabs=[...document.querySelectorAll('[data-tab]')], views=[...document.querySelectorAll('[data-view]')];
function showTab(name){tabs.forEach(b=>b.setAttribute('aria-selected',String(b.dataset.tab===name)));views.forEach(v=>v.hidden=v.dataset.view!==name)}
tabs.forEach(b=>b.addEventListener('click',()=>showTab(b.dataset.tab)));
const nav=[...document.querySelectorAll('.page-button')], articles=[...document.querySelectorAll('.article')];
const input=document.getElementById('page-search'),role=document.getElementById('role-filter');
function selectPage(id,scroll=false){articles.forEach(a=>a.hidden=a.id!==id);nav.forEach(b=>b.setAttribute('aria-pressed',String(b.dataset.target===id)));if(scroll)document.getElementById(id)?.scrollIntoView({behavior:'smooth',block:'start'})}
nav.forEach(b=>b.addEventListener('click',()=>selectPage(b.dataset.target)));
function filter(){const q=input.value.trim().toLowerCase();nav.forEach(b=>b.hidden=!(b.textContent.toLowerCase().includes(q)&&(!role.value||b.dataset.role===role.value)));const visible=nav.filter(b=>!b.hidden);document.getElementById('nav-count').textContent=visible.length+' / '+nav.length+' 篇';document.getElementById('no-pages').hidden=visible.length>0;if(!visible.some(b=>b.getAttribute('aria-pressed')==='true')){if(visible.length)selectPage(visible[0].dataset.target);else articles.forEach(a=>a.hidden=true)}}
input.addEventListener('input',filter);role.addEventListener('change',filter);
document.querySelectorAll('[data-jump]').forEach(b=>b.addEventListener('click',()=>{showTab('results');input.value='';role.value='';filter();selectPage(b.dataset.jump,true)}));
document.querySelectorAll('[data-round-picker]').forEach(s=>{function choose(){const a=s.closest('.article');a.querySelectorAll('[data-version]').forEach(v=>v.hidden=v.dataset.version!==s.value)}s.addEventListener('change',choose);choose()});
document.querySelectorAll('[data-evidence-toggle]').forEach(b=>b.addEventListener('click',()=>{const a=b.closest('[data-version]'),ds=[...a.querySelectorAll('.body-block details')],open=ds.some(d=>!d.open);ds.forEach(d=>d.open=open);b.textContent=open?'收起全部原文定位':'展开全部原文定位'}));
showTab('results');if(nav.length)selectPage(nav[0].dataset.target);filter();
})();
'''

def result_version(out, version, issues):
    result=version['data']
    parts=['<div data-version="'+e(version['key'])+'"><h3>页面信息 <span class="muted small">与正文分离</span></h3>',metadata_table(result.get('metadata',[]))]
    parts.append('<div class="content-title"><h3>提取正文 <span class="muted small">'+str(len(result.get('blocks',[])))+' 块，按原文顺序</span></h3><button class="quiet" data-evidence-toggle>展开全部原文定位</button></div>')
    parts.append('<ol class="body-list">'+''.join(block_html(b,i) for i,b in enumerate(result.get('blocks',[]),1))+'</ol>')
    if not result.get('blocks'):
        parts.append('<p class="empty">本轮没有可展示的正文文字块。</p>')
    excluded=result.get('excluded',[])
    parts.append(details('排除记录 · '+str(len(excluded))+' 项',metadata_table(excluded)))
    parts.append(details('检查问题 · '+str(len(issues))+' 项',issues_html(issues)))
    parts.append(details('局限与警告 · '+str(len(result.get('warnings',[])))+' 项','<ul>'+''.join('<li>'+e(w)+'</li>' for w in result.get('warnings',[]))+'</ul>'))
    parts.append(details('完整原始结果',artifact(out,version['file'],'打开结果 JSON')+json_view(result)))
    parts.append('</div>')
    return ''.join(parts)

def load_pages(out,trace):
    grouped={}
    inputs={p['id']:p for p in trace.get('input_pages',[])}
    def add(row,key,title):
        page=grouped.setdefault(row['id'],dict(inputs.get(row['id'],{}),id=row['id'],versions=[]))
        page.update({k:v for k,v in row.items() if k!='versions'})
        page['versions'].append(dict(key=key,label=title,row=row,data=read_json(local_file(out,row['result']),{}) if row.get('result') else None,file=row.get('result','')))
    for entry in trace.get('rounds',[]):
        for row in entry.get('pages',[]):
            add(row,'r'+str(entry['round']),'首轮候选' if entry['round']==0 else '修复后 · 轮次 '+str(entry['round']))
    for row in trace.get('holdout',[]):
        add(row,'holdout','冻结候选 · 最终测试')
    # Include skipped pages honestly, rather than hiding them on failures.
    for ident,item in inputs.items():
        if ident not in grouped:
            grouped[ident]=dict(item,versions=[],status='not_run')
    for page in grouped.values():
        page['display_title']=next((v['data']['title'] for v in reversed(page['versions']) if v['data'] and v['data'].get('title')),page['id'])
    return list(grouped.values())

def rule_panel(out,trace,reference=False):
    names={'title_xpath':'标题定位','container_xpath':'正文容器','block_xpath':'正文块选择','exclude_xpath':'排除规则','metadata_xpath':'页面信息定位','metadata_fields':'细分页面信息','block_mode':'分块模式'}
    parts=['<div class="panel"><h2>生成规则与复用代码</h2><p class="muted">'+('本报告使用人工参考配方，未调用模型生成。' if reference else '模型生成 XPath 配置，固定模板导出 Python 模块，随后在 CPU 上复用。')+'</p>']
    if reference:
        for ident,rules in trace.get('_reference_recipes',{}).items():
            parts.append('<div class="step"><h3>'+e(ident)+' · 人工参考配方</h3>'+json_view(rules)+'</div>')
        parts.append('</div>')
        return ''.join(parts)
    for entry in trace.get('rounds',[]):
        n=entry['round']; rules=read_json(out/f'candidate_round_{n}.json')
        parts.append('<div class="step"><h3>'+('首轮规则' if n==0 else '修复后规则 · 轮次 '+str(n))+'</h3>')
        if rules is None:
            parts.append('<p class="muted">本轮未生成有效规则。</p>')
        else:
            for field,value in rules.items():
                parts.append('<div class="rule-row"><strong>'+e(names.get(field,field))+'</strong> <span class="muted small">'+e(field)+'</span>'+code(json.dumps(value,ensure_ascii=False,indent=2) if isinstance(value,dict) else value or '（空：本轮未设置）')+'</div>')
        parts.append('<p>'+artifact(out,f'candidate_round_{n}.json','下载规则 JSON')+' · '+artifact(out,f'candidate_round_{n}.py','打开本轮 Python')+'</p>')
        py=out/f'candidate_round_{n}.py'
        if py.exists():
            parts.append(details('查看 Python 模块',code(py.read_text(encoding='utf8'))))
        parts.append('</div>')
    if not trace.get('rounds'):
        parts.append('<p class="muted">未产生候选规则；请查看调用记录或失败信息。</p>')
    parts.append('<p>'+artifact(out,'extractor.py','冻结的 Python 模块')+' · '+artifact(out,'rules.json','冻结的规则')+'</p></div>')
    return ''.join(parts)

def process_panel(out,trace):
    if trace.get('provider')=='human_reference':
        rows=trace.get('_reference_comparisons',[])
        return '<div class="panel"><h2>参考回归对照</h2><p class="muted">本次未生成或修复模型规则。对比项目一已确认输出与项目二固定执行层结果。</p><div class="table-wrap"><table><thead><tr><th>样本</th><th>参考正文块</th><th>当前正文块</th><th>文字与顺序</th><th>待审核项</th></tr></thead><tbody>'+''.join('<tr><td>'+e(r['id'])+'</td><td>'+e(r['reference_blocks'])+'</td><td>'+e(r['current_blocks'])+'</td><td>'+('一致' if r['body_sequence_equal'] else '有变化')+'</td><td>'+str(len(r.get('issues',[])))+'</td></tr>' for r in rows)+'</tbody></table></div><p>正文一致和语义待审核分别记录；分类与排除未确认时不计作语义验收。</p></div>'
    parts=['<div class="panel"><h2>生成与修复过程</h2><p class="muted">首轮执行 → 收集实际问题 → 在预算内修复 → 冻结候选 → 执行最终测试。最终测试反馈不回传模型。</p>']
    for entry in trace.get('rounds',[]):
        pages=entry.get('pages',[])
        parts.append('<div class="step"><h3>'+('首轮候选' if entry['round']==0 else '修复候选 · 轮次 '+str(entry['round']))+'</h3><p>执行 '+str(len(pages))+' 篇；检查通过 '+str(sum(p.get('status')=='pass' for p in pages))+' 篇；反馈记录 '+str(len(entry.get('issues',[])))+' 组。</p>')
        parts.append('<div class="table-wrap"><table><thead><tr><th>页面</th><th>角色</th><th>正文块</th><th>检查状态</th><th>问题数</th></tr></thead><tbody>'+''.join('<tr><td>'+e(p['id'])+'</td><td>'+e(label(p.get('role','')))+'</td><td>'+e(p.get('blocks','—'))+'</td><td>'+badge(p.get('status','failed'))+'</td><td>'+str(len(p.get('issues',[])))+'</td></tr>' for p in pages)+'</tbody></table></div>')
        for item in entry.get('issues',[]):
            parts.append(details('反馈证据 · '+str(item.get('id',item.get('kind','候选错误'))),issues_html(item.get('issues',[item]))))
        n=entry['round']
        parts.append('<p>'+artifact(out,f'prompt_round_{n}.json','本轮模型输入')+' · '+artifact(out,f'response_round_{n}.txt','本轮模型响应')+'</p>')
        if n:
            old=read_json(out/f'candidate_round_{n-1}.json'); new=read_json(out/f'candidate_round_{n}.json')
            if old is not None and new is not None:
                diff=''.join(difflib.unified_diff(json.dumps(old,ensure_ascii=False,indent=2).splitlines(True),json.dumps(new,ensure_ascii=False,indent=2).splitlines(True),fromfile='上一轮规则',tofile='本轮规则'))
                parts.append(details('规则变化对比',code(diff or '规则未变化')))
        parts.append('</div>')
    if trace.get('frozen_before_holdout'):
        parts.append('<div class="step"><h3>冻结候选后测试</h3><p>最终测试 '+str(len(trace.get('holdout',[])))+' 篇。冻结哈希：</p>'+code(trace.get('frozen_candidate_sha256',''))+'</div>')
    else:
        parts.append('<div class="notice">本记录未确认候选在最终测试前冻结；未执行的页面在结果中明确标注。</div>')
    if trace.get('error'):
        parts.append('<div class="notice">'+e(trace['error'])+'</div>')
    parts.append('</div>')
    return ''.join(parts)

def calls_panel(out,trace):
    attempts=trace.get('api_attempts',[])
    parts=['<div class="panel"><h2>API 调用与运行证据</h2><p>模型：<strong>'+e(trace.get('model','未记录'))+'</strong> · 提供方：'+e(trace.get('provider','未记录'))+' · API 尝试：'+str(len(attempts))+'</p>']
    parts.append('<p class="muted">全流程耗时：'+e(trace.get('elapsed_seconds','未记录'))+' 秒 · 修复预算：'+e(trace.get('max_repairs','不适用'))+' 次</p>')
    parts.append('<div class="table-wrap"><table><thead><tr><th>候选轮次</th><th>状态</th><th>输入 tokens</th><th>输出 tokens</th><th>合计 tokens</th><th>耗时</th></tr></thead><tbody>')
    for a in attempts:
        usage=a.get('usage',{})
        parts.append('<tr><td>'+e(a.get('round','—'))+'</td><td>'+badge(a.get('status','failed'))+'</td>'+''.join('<td>'+e(usage.get(k,'未返回'))+'</td>' for k in ('prompt_tokens','completion_tokens','total_tokens'))+'<td>'+e(a.get('seconds','未记录'))+' s</td></tr>')
    parts.append('</tbody></table></div>')
    if not attempts:
        parts.append('<p class="muted">本记录没有 API 请求；模拟演示或参考回归不代表真实模型调用。</p>')
    parts.append('<p class="muted">用量仅汇总服务端已返回的记录；失败请求可能没有返回用量。未配置价格，不计算金额。耗时为单次运行记录，不是性能基准。</p>')
    parts.append(details('任务与执行器版本',json_view({k:trace[k] for k in ('task_id','engine_protocol','engine_sha256','worker_sha256','frozen_candidate_sha256','evaluation_scope','holdout_policy','candidate_hash_scheme') if k in trace})))
    if trace.get('provider')=='human_reference':
        parts.append(details('完整参考回归记录',artifact(out,'report.json','打开 report.json')+json_view({k:v for k,v in trace.items() if not k.startswith('_')})))
    else:
        parts.append(details('完整运行轨迹',artifact(out,'trace.json','打开 trace.json')+json_view(trace)))
    parts.append('</div>')
    return ''.join(parts)

def render_report(out,trace,reference=False):
    out=Path(out); pages=load_pages(out,trace)
    attempts=trace.get('api_attempts',[])
    totals=[a.get('usage',{}).get('total_tokens') for a in attempts]
    known=[v for v in totals if isinstance(v,(int,float))]
    tokens=f'{sum(known):,}' if known else '未返回' if attempts else '0'
    if known and len(known)<len(attempts):
        tokens+='（部分）'
    experiment='人工参考回归' if reference else '受控修复实验' if trace.get('initial_candidate')=='controlled_ablation' else '离线模拟演示' if trace.get('provider')=='mock' else '真实 API 实验'
    role_counts=Counter(p.get('role','') for p in pages)
    metrics=[('模型',trace.get('model','未记录'),'本次记录中的模型'),('API 尝试',len(attempts),str(sum(a.get('status')=='succeeded' for a in attempts))+' 次返回成功'),('参考配方' if reference else '候选轮次',len(trace.get('_reference_recipes',{})) if reference else len(trace.get('rounds',[])),'人工登记，非模型生成' if reference else '含首轮，不等于 API 次数'),('网页数量',len(pages),' · '.join(label(k)+' '+str(v) for k,v in role_counts.items())),('总 tokens',tokens,'仅统计已返回用量')]
    parts=['<!doctype html><html lang="zh-CN"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>项目二 · 单 Agent 正文提取报告</title><style>'+CSS+'</style></head><body><a class="skip" href="#report-content">跳到报告内容</a><div class="wrap"><header class="hero"><div class="eyebrow">PROJECT 02 / EXTRACTION AGENT</div><h1>单 Agent 网页正文提取报告</h1><p>'+e(experiment)+' '+badge(trace.get('final_status','failed'))+'</p><p>从少量同布局样本生成规则，在 CPU 上复用；把提取结果与生成证据放在一起。</p><div class="toplinks">'+artifact(out,'trace.json','完整运行记录')+' · '+artifact(out,'rules.json','冻结规则')+' · '+artifact(out,'extractor.py','Python 提取器')+'</div></header>',
           '<div class="metrics">'+''.join('<div class="metric"><small>'+e(name)+'</small><strong'+(' class="model"' if name=='模型' else '')+'>'+e(value)+'</strong><span>'+e(note)+'</span></div>' for name,value,note in metrics)+'</div>',
           '<div class="notice small">'+('人工配方与已曝光样例，只验证固定执行层；模型生成成绩不适用。' if reference else '检查通过表示本任务的结构与执行检查通过，不等于正文语义准确率。')+' 图片像素和动态内容未评估；HTML 快照不保证原站视觉还原。'+(' 此次从人为漏提规则开始，不能当作新增泛化成绩。' if trace.get('initial_candidate')=='controlled_ablation' else '')+'</div>',
           '<nav class="tabs" role="tablist" aria-label="报告视图">'+''.join('<button type="button" role="tab" id="tab-'+key+'" aria-controls="view-'+key+'" aria-selected="'+str(key=='results').lower()+'" class="tab" data-tab="'+key+'">'+name+'</button>' for key,name in [('results','提取结果'),('process','生成与修复'),('rules','规则与代码'),('calls','调用记录')])+'</nav>',
           '<noscript><p class="nojs">JavaScript 已禁用。所有报告内容仍可阅读，筛选和切换不可用。</p></noscript><main id="report-content"><section class="view" role="tabpanel" aria-labelledby="tab-results" id="view-results" data-view="results">',
           '<div class="panel"><h2>样本与结果汇总</h2><p class="muted small">点击标题进入正文。生成页可影响规则；开发页可提供修复反馈；最终测试页只在冻结候选后执行。</p><div class="table-wrap"><table><thead><tr><th>文章 / 样本</th><th>角色</th><th>状态</th><th>正文块</th><th>页面信息</th><th>排除项</th></tr></thead><tbody>']
    review = read_json(out/'review.json')
    if review:
        parts.insert(len(parts)-1, '<div class="panel"><h2>冻结后专项复核</h2><p>'+e(review.get('summary',''))+'</p><p class="muted small">'+e(review.get('scope',''))+'</p>'+details('逐页检查与限制',json_view(review))+'</div>')
    nav=[]; articles=[]
    for i,page in enumerate(pages):
        ident='page-'+str(i); versions=[v for v in page['versions'] if v['data'] is not None]; last=versions[-1]['data'] if versions else {}
        status=page.get('status','not_run')
        if status=='not_run':
            status_html='<span class="badge warn">未执行</span>'
        else:
            status_html=badge(status)
        parts.append('<tr><td><button class="quiet" data-jump="'+ident+'">'+e(page['display_title'])+'</button><br><span class="muted small">'+e(page['id'])+'</span></td><td>'+e(label(page.get('role','')))+'</td><td>'+status_html+'</td><td>'+str(len(last.get('blocks',[])))+'</td><td>'+str(len(last.get('metadata',[])))+'</td><td>'+str(len(last.get('excluded',[])))+'</td></tr>')
        nav.append('<button class="page-button" data-target="'+ident+'" data-role="'+e(page.get('role',''))+'" aria-pressed="false">'+e(page['display_title'])+'<small>'+e(label(page.get('role','')))+' · '+str(len(last.get('blocks',[])))+' 块</small></button>')
        content=['<article class="panel article" id="'+ident+'"><div class="article-meta"><span>'+e(label(page.get('role','')))+'</span><span>'+e(page['id'])+'</span>'+status_html+'</div><h2>'+e(page['display_title'])+'</h2><div class="article-links">']
        if page.get('url'):
            content.append(link(page['url'],'原站地址'))
        path=page.get('source_path',page.get('path',''))
        if path:
            content.append(source_link(out,path))
        content.append('</div>')
        if versions and page['versions'][-1]['data'] is None:
            content.append('<div class="notice">最近一轮未生成有效结果，下面展示此前保存的候选正文，请勿当作最近一轮成功输出。</div>'+issues_html(page['versions'][-1]['row'].get('issues',[])))
        if reference:
            comparison=next((r for r in trace.get('_reference_comparisons',[]) if r['id']==page['id']),None)
            if comparison:
                content.append('<div class="comparison small">项目一参考 '+str(comparison['reference_blocks'])+' 块 → 当前 '+str(comparison['current_blocks'])+' 块；文字与顺序'+('一致' if comparison['body_sequence_equal'] else '存在变化')+'。'+details('查看差异记录',json_view({k:comparison.get(k,[]) for k in ('missing','added')}))+'</div>')
        if len(versions)>1:
            content.append('<label class="small" for="round-'+ident+'">查看候选版本</label><br><select class="round-select" id="round-'+ident+'" data-round-picker>'+''.join('<option value="'+e(v['key'])+'"'+(' selected' if n==len(versions)-1 else '')+'>'+e(v['label'])+'</option>' for n,v in enumerate(versions))+'</select>')
            first=versions[0]['data']; final=versions[-1]['data']
            content.append('<div class="comparison small">首轮 → 最终：正文块 '+str(len(first.get('blocks',[])))+' → '+str(len(final.get('blocks',[])))+'；检查问题 '+str(len(versions[0]['row'].get('issues',[])))+' → '+str(len(versions[-1]['row'].get('issues',[])))+'。块数变化不等于质量提升，可切换版本查看全文。</div>')
        if versions:
            for v in versions:
                content.append(result_version(out,v,v['row'].get('issues',[])))
        else:
            content.append('<div class="notice">本次没有可展示的提取结果。'+('候选未达到开发检查要求，最终测试未执行。' if page.get('role')=='final_holdout' else '请查看生成过程或调用记录。')+'</div>'+issues_html(page.get('issues',[])))
        content.append('</article>'); articles.append(''.join(content))
    parts.append('</tbody></table></div></div><div class="workspace"><aside class="sidebar"><h3>浏览文章</h3><label class="small" for="page-search">搜索标题或样本</label><input id="page-search" type="search" placeholder="输入关键词…"><label class="small" for="role-filter">样本角色</label><select id="role-filter"><option value="">全部角色</option>'+''.join('<option value="'+e(role)+'">'+e(label(role))+'</option>' for role in role_counts)+'</select><p class="muted small" id="nav-count">'+str(len(pages))+' 篇</p><div class="page-nav">'+''.join(nav)+'</div><p id="no-pages" class="muted small" hidden>没有匹配的文章，请更换关键词或角色。</p></aside><div>'+''.join(articles)+('</div>' if articles else '<p class="empty">没有页面执行记录。</p></div>')+'</div></section>')
    parts.append('<section class="view" role="tabpanel" aria-labelledby="tab-process" id="view-process" data-view="process">'+process_panel(out,trace)+'</section>')
    parts.append('<section class="view" role="tabpanel" aria-labelledby="tab-rules" id="view-rules" data-view="rules">'+rule_panel(out,trace,reference)+'</section>')
    parts.append('<section class="view" role="tabpanel" aria-labelledby="tab-calls" id="view-calls" data-view="calls">'+calls_panel(out,trace)+'</section></main><footer class="foot">此页面仅展示已保存的实验记录。筛选、切换与展开不会发起 API 请求，也不会修改标注或提取结果。</footer></div><script>'+JS+'</script></body></html>')
    (out/'index.html').write_bytes('\n'.join(parts).encode('utf8'))

def render_reference(out):
    report=read_json(out/'report.json')
    config=read_json(ROOT/'config/project2_foundation_reference.json',{'pages':[]})
    pages=[]
    mapping={p['id']:p for p in config['pages']}
    for row in report['pages']:
        source=mapping.get(row['id'],{})
        pages.append(dict(id=row['id'],role='historical_exposed_regression',status='needs_review' if row.get('issues') else 'pass',
                          url=source.get('url',''),source_path=source.get('path',''),result=row['id']+'.json',issues=row.get('issues',[])))
    trace=dict(task_id='foundation-reference',provider='human_reference',model='不适用（人工参考规则）',api_attempts=[],input_pages=pages,
               rounds=[dict(round=0,pages=pages,issues=[])],holdout=[],final_status='needs_review' if any(p['issues'] for p in pages) else 'pass',
               initial_candidate='human_reference',evaluation_scope=report['scope'],
               _reference_comparisons=report['pages'],_reference_recipes={p['id']:p['rules'] for p in config['pages']})
    # Reference recipes are shown in the same layout, without creating model artifacts.
    render_report(out,trace,reference=True)

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('directories',nargs='+',help='Saved Agent run or foundation reference directories')
    args=parser.parse_args()
    for name in args.directories:
        out=Path(name).resolve()
        if (out/'trace.json').exists():
            render_report(out,read_json(out/'trace.json'))
        elif (out/'report.json').exists():
            render_reference(out)
        else:
            parser.error('No trace.json or reference report.json: '+name)
        print(out/'index.html')

if __name__=='__main__':
    main()
