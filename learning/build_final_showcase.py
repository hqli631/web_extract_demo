"""Build a self-contained, evidence-based project handoff page."""
import json
from html import escape
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'output/stage5/multitask'
def read(p):return json.loads(p.read_text(encoding='utf8'))
def build():
    results=read(OUT/'evaluation_results.json');manifest=read(OUT/'natural_tasks.json')
    proof=read(OUT/'capacity_update_proof.json');rows=results['records']
    models=[('base','原始基座'),('lora40','40 步 LoRA'),('lora120','120 步 LoRA'),('reviewed_reference','人工复核参考规则')]
    counts={m:{role:dict(passed=sum(r['contract_pass'] for r in rows if r['model']==m and r['role']==role),total=sum(r['model']==m and r['role']==role for r in rows)) for role in ['dev','test']} for m,_ in models}
    dest=OUT/'showcase';dest.mkdir(exist_ok=True)
    parts=['<!doctype html><html lang="zh-CN"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>网页抽取 · 模型效果与交付</title>',
      '<style>body{font:16px/1.65 system-ui,sans-serif;background:#f5f7fb;color:#172439;max-width:1360px;margin:auto;padding:24px}h1{font-size:30px}a{color:#165ca8}table{width:100%;border-collapse:collapse;background:white}th,td{padding:10px;text-align:left;border-bottom:1px solid #dce3ed}section{margin:24px 0;background:white;padding:22px;border-radius:12px}.note{background:#eaf1fb;padding:14px}.warn{background:#fff1d6;padding:14px}.cols{display:grid;grid-template-columns:1fr 1fr;gap:20px}pre{white-space:pre-wrap;overflow-wrap:anywhere;background:#edf1f6;padding:14px;max-height:480px;overflow:auto}button,select{font:inherit;padding:8px;margin:5px 10px 5px 0}iframe{width:100%;height:620px;border:1px solid #ccc}.block{border-bottom:1px solid #ddd;padding:12px 0}.kind{color:#596b84;font-size:14px}#bodyText{max-height:700px;overflow:auto}.pass{color:#09673b}.fail{color:#a12626}@media(max-width:850px){.cols{grid-template-columns:1fr}body{padding:12px}}</style>',
      '<h1>网页正文抽取：训练前后效果</h1><p>岗位主线：同布局采样 → 生成 Python/XPath → CPU 复用 → 证据检查 → 修复与回滚。</p>',
      '<p class="note"><b>工程 Demo 已形成。</b>120 步模型在 3 个开发页全部通过；封存新文章 2/3 通过。这里只证明已训练布局中的代码复用，不能代表跨布局或新闻全域准确率。</p>',
      '<section><h2>1．训练用了哪些网页</h2><p>新增 12 个真实网页组成 3 个代码任务；另加入历史新浪训练任务。历史中新网任务作开发对照。网页数量与任务数量分别统计。</p><table><tr><th>布局任务</th><th>训练页（两页组成一个任务）</th><th>开发页</th><th>最终测试页</th></tr>']
    for c in manifest['clusters']:
        cells=[]
        for role in ['train','dev','test']:
            cells.append('<br>'.join('<a target="_blank" rel="noopener" href="'+escape(p['url'],quote=True)+'">'+escape(p['url'].split('/')[-1] or p['url'])+'</a>' for p in c['pages'] if p['role']==role))
        parts.append('<tr><td>'+escape(c['task_id'])+'</td>'+''.join('<td>'+x+'</td>' for x in cells)+'</tr>')
    parts.append('</table><p>测试页先登记URL与哈希，最后一次性评估。现在已曝光，后续调试须另留新测试。公开链接可查看原站；本地快照保留原HTML，不承诺离线资源和原站完全一致。</p></section>')
    parts.append('<section><h2>2．固定条件下的效果对比</h2><table><tr><th>方法</th><th>开发页契约与证据通过</th><th>封存测试通过</th><th>解释</th></tr>')
    for m,label in models:
        d,t=counts[m]['dev'],counts[m]['test']
        parts.append(f'<tr><td>{label}</td><td>{d["passed"]}/{d["total"]}</td><td>{str(t["passed"])+"/"+str(t["total"]) if t["total"] else "未用于最终测试"}</td><td>'+('当前对话复核目标，非独立金标' if m=='reviewed_reference' else '通过要求：可执行、五字段契约、正文非空、XPath原文证据与顺序')+'</td></tr>')
    parts.append('</table><p class="warn">SQLite 测试页未命中 <code>div.fancy</code>，参考与模型均失败；失败保留并进入待修复列表。已通过页面与参考输出一致，不等于人工语义准确率100%。</p>')
    parts.append('<p>模型：Qwen2.5-Coder-0.5B-Instruct，固定 revision；LoRA r=16，7 类投影层，120 optimizer steps。可训练参数 '+str(proof['trainable_parameters'])+'；峰值 allocated '+f'{proof["peak_allocated_bytes"]/2**30:.2f}'+' GiB；训练 '+f'{proof["train_metrics"]["train_runtime"]:.1f}'+' 秒。此耗时不含生成、数据和评测，不折算未经核实的金额。</p></section>')
    parts.append('<section><h2>3．查看一篇网页的实际输出</h2><label>网页 <select id="page"></select></label><label>方法 <select id="model"></select></label><p id="status" aria-live="polite"></p><p><a id="original" target="_blank" rel="noopener">打开原网页</a> · <a id="snapshot" target="_blank" rel="noopener">打开原始HTML快照</a></p><div class="cols"><div><h3>提取标题与正文</h3><div id="bodyText"></div></div><div><h3>代码 / 错误 / 证据</h3><details open><summary>运行与质量边界</summary><pre id="evidence"></pre></details><details><summary>模型生成代码</summary><pre id="code"></pre></details></div></div></section>')
    parts.append('<section><h2>4．工程闭环与下一步</h2><p><a href="../../rsi_delivery/index.html">修复采用与拒绝回滚演示</a> · <a href="../../rubrics_calibration_v1/index.html">Rubrics 校准状态</a> · <a href="../../../../docs/PROJECT_DELIVERY.md">交付与学习回顾</a></p><p>当前提供可复核的模型与规则抽取 Demo。真实 GRPO 尚未执行；独立自然页语义评估、跨布局测试、图像/OCR与动态内容是后续研究项，不能用当前结果替代。</p></section>')
    codes={}
    for name,file in [('base','before_generation.json'),('lora40','after_generation.json'),('lora120','capacity_after_generation.json')]:
        for r in read(OUT/file)['outputs']:codes[name+'|'+r['task_id'].removeprefix('natural-')]=r['text']
    for c in manifest['clusters']:codes['reviewed_reference|'+c['task_id']]=(ROOT/c['target_code']['path']).read_text(encoding='utf8')
    payload=json.dumps(dict(rows=rows,codes=codes,models=models),ensure_ascii=False).replace('<','\\u003c')
    parts.append('<script id="payload" type="application/json">'+payload+'</script>')
    parts.append('''<script>
const data=JSON.parse(document.getElementById('payload').textContent);const el=id=>document.getElementById(id);
const pages=[...new Map(data.rows.map(r=>[r.task_id+'|'+r.role,r])).values()];
pages.forEach(r=>{const o=document.createElement('option');o.value=r.task_id+'|'+r.role;o.textContent=r.task_id+' / '+(r.role==='test'?'封存测试':'开发');el('page').append(o)});
data.models.forEach(([key,label])=>{let o=document.createElement('option');o.value=key;o.textContent=label;el('model').append(o)});el('model').value='lora120';
function render(){const [task,role]=el('page').value.split('|');const r=data.rows.find(r=>r.task_id===task&&r.role===role&&r.model===el('model').value);el('bodyText').replaceChildren();
if(!r){el('status').textContent='该方法未用于本页最终测试。';el('code').textContent='';el('evidence').textContent='';return;}
el('status').textContent=(r.contract_pass?'通过契约与原文证据检查':'未通过')+' · '+r.status;el('status').className=r.contract_pass?'pass':'fail';el('original').href=r.source.url;el('snapshot').href='../../../../'+r.source.path;
const result=r.result;if(result){let h=document.createElement('h3');h.textContent=result.title||'未提取标题';el('bodyText').append(h);(Array.isArray(result.blocks)?result.blocks:[]).forEach((b,i)=>{let d=document.createElement('div');d.className='block';let l=document.createElement('div');l.className='kind';l.textContent=(i+1)+' · '+b.kind;let p=document.createElement('p');p.textContent=b.text;d.append(l,p);el('bodyText').append(d)})}else{el('bodyText').textContent='本次运行未产生可用正文。'}
const copy={...r};delete copy.result;el('evidence').textContent=JSON.stringify(copy,null,2);el('code').textContent=data.codes[el('model').value+'|'+task]||'';}
el('page').addEventListener('change',render);el('model').addEventListener('change',render);render();
</script></html>''')
    (dest/'index.html').write_text(chr(10).join(parts),encoding='utf8')
    print(dest/'index.html');return counts
if __name__=='__main__':build()
