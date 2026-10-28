from pathlib import Path
import json

ROOT = Path(__file__).resolve().parent
data = json.loads((ROOT / 'output/results.json').read_text(encoding='utf-8'))
template = '''<!doctype html><meta charset="utf-8"><title>网页区域复核</title>
<style>body{font:16px sans-serif;background:#f4f6fa;margin:24px}header{position:sticky;top:0;background:white;padding:16px;z-index:1}button,select{padding:8px;margin:4px}article{background:white;border:2px solid #aaa;padding:18px;margin:14px 0;white-space:pre-wrap;line-height:1.8}small{color:#555}textarea{width:98%;height:120px}h2{font-size:19px}</style>
<header><b>区域复核：正文 / 杂质 / 缺漏</b><br><select id="page"></select><select id="filter"><option>全部</option><option>正文</option><option>杂质</option><option>缺漏</option><option>待判断</option></select><button id="save">导出标注及修正正文</button><p>缺漏＝自动结果未选中、但应补回的正文。标注只在当前页面内存中保存，刷新前请导出。此页按 DOM 文本块展示，不是原网页坐标框选。</p><div id="stats"></div></header><main id="blocks"></main>
<script>
const data=__DATA__,page=document.querySelector('#page'),filter=document.querySelector('#filter'),blocks=document.querySelector('#blocks');
data.forEach((p,i)=>{let o=document.createElement('option');o.value=i;o.textContent=p.file+' — '+p.title;page.append(o);(p.regions||[]).forEach(r=>r.label=['正文候选','标题/小标题'].includes(r.auto_label)?'正文':r.auto_label==='杂质'?'杂质':'待判断')});
function render(){blocks.replaceChildren();let p=data[page.value];if(!p)return;document.querySelector('#stats').textContent='当前页面共 '+p.regions.length+' 个区域；正文定义由人工确认，自动标签仅供参考。';p.regions.forEach(r=>{if(filter.value!=='全部'&&r.label!==filter.value)return;let a=document.createElement('article'),title=document.createElement('h2'),meta=document.createElement('small'),s=document.createElement('select'),text=document.createElement('div');title.textContent='区域 '+r.region_id;meta.textContent=r.tag+' #'+r.id+' .'+r.class+' | 自动判断：'+r.auto_label+' | '+r.reason;['正文','杂质','缺漏','待判断'].forEach(x=>{let o=document.createElement('option');o.textContent=x;s.append(o)});s.value=r.label;s.onchange=()=>{r.label=s.value;render()};text.textContent=r.text;a.style.borderColor=({正文:'#23985d',杂质:'#d95555',缺漏:'#e9a020',待判断:'#999'})[r.label];a.append(title,meta,s,text);blocks.append(a)})}
page.onchange=render;filter.onchange=render;document.querySelector('#save').onclick=()=>{let out=data.map(p=>({...p,content:p.regions.filter(r=>['正文','缺漏'].includes(r.label)).map(r=>r.text).join('\\n')}));let u=URL.createObjectURL(new Blob([JSON.stringify(out,null,2)],{type:'application/json'}));let a=document.createElement('a');a.href=u;a.download='reviewed_results.json';a.click();setTimeout(()=>URL.revokeObjectURL(u),1000)};render();
</script>'''
(ROOT / 'output/review.html').write_text(template.replace('__DATA__', json.dumps(data, ensure_ascii=False).replace('<', '\\u003c')), encoding='utf-8')
print('output/review.html ready')
