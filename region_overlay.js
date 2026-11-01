(() => {
  const semantic = 'p,h1,h2,h3,h4,h5,h6,li,pre,td,th,figcaption,blockquote,dt,dd';
  const clean = s => (s || '').replace(/\s+/g, ' ').trim();
  const names={body:'正文',title:'标题',time:'发布时间',source:'来源',author:'作者',navigation:'导航',advertisement:'广告',recommendation:'相关推荐',sidebar:'侧栏',comment:'评论',toolbar:'功能工具',footer:'页脚版权',image:'图片',media:'音视频',noise:'其他杂质',pending:'待判断',missing:'缺漏'};
  function classify(node,text){
    const own=(node.id+' '+node.className+' '+node.tagName).toLowerCase();
    let n=node, identity='';
    while(n&&n!==document.body&&n!==document.documentElement){identity+=' '+n.tagName+' '+n.id+' '+n.className;n=n.parentElement||n.getRootNode().host}
    if(/(^|[\s_-])(ad|ads|advert|advertisement|adcontainer|adbox)([\s_-]|$)/i.test(identity)||/^(广告|推广|赞助内容)$/.test(text))return 'advertisement';
    if(/\bdate\b|publish.?time|timestamp|\btime\b/.test(own)||/^\d{4}年\d{1,2}月\d{1,2}日/.test(text))return 'time';
    if(/\bsource\b|文章来源/.test(own))return 'source';
    if(/author|byline|作者/.test(own))return 'author';
    if(/page-tools|tool-icon|toolbar|share|floating|float-menu|audio-pop|right-bar|btn-home/i.test(identity))return 'toolbar';
    if(/comment|评论/i.test(identity))return 'comment';
    if(/recommend|related|猜你喜欢|相关新闻/i.test(identity))return 'recommendation';
    if(/footer|copyright/i.test(identity))return 'footer';
    if(/aside|sidebar|cj-r-|rightbar|right-side/i.test(identity))return 'sidebar';
    if(/nav|breadcrumb|menu|crumb/i.test(identity))return 'navigation';
    if(/^H1$/.test(node.tagName))return 'title';
    if(node.matches('img,svg')||(!text&&getComputedStyle(node).backgroundImage!=='none'))return 'image';
    if(node.matches('video,audio,iframe,canvas'))return 'media';
    return text.length>=80?'body':'pending';
  }
  const host = document.createElement('div');
  host.style.cssText = 'position:fixed;inset:0;pointer-events:none;z-index:2147483647';
  const ui = host.attachShadow({mode:'open'});
  ui.innerHTML = '<style>.box{position:fixed;box-sizing:border-box;border:1px solid #888;pointer-events:none}.selected{border:3px solid #006aff!important;background:#006aff18}.badge{position:absolute;left:0;top:0;color:white;background:#555;font:12px Arial;pointer-events:auto;cursor:pointer;padding:2px 4px}.body{border-color:#16894c}.body .badge{background:#16894c}.noise{border-color:#d34040}.noise .badge{background:#d34040}.missing{border-color:#d88b00}.missing .badge{background:#d88b00}</style>';
  document.documentElement.append(host);
  const colors={title:'#087f8c',time:'#7653b7',source:'#7653b7',author:'#7653b7',navigation:'#64748b',advertisement:'#c2410c',recommendation:'#b45309',sidebar:'#9a6700',comment:'#be185d',toolbar:'#475569',footer:'#64748b',image:'#0369a1',media:'#0369a1'};
  const css=document.createElement('style');css.textContent='.badge{white-space:nowrap;max-width:150px;overflow:hidden;text-overflow:ellipsis;border:0;line-height:16px}.box:hover{z-index:2}'+Object.entries(colors).map(([k,v])=>`.${k}{border-color:${v}}.${k} .badge{background:${v}}`).join('');ui.append(css);
  let regions=[], selected=0, queued=false, enabled=true;
  let chosen=null, focus=true, rules=[], prediction=null;
  const snapshot=document.querySelector('meta[name="review-snapshot"]')?.content||'';
  function xpath(n){let parts=[];while(n?.nodeType===1){let i=1,p=n.previousElementSibling;while(p){if(p.localName===n.localName)i++;p=p.previousElementSibling}parts.unshift('*[local-name()="'+n.localName+'"]['+i+']');n=n.parentElement}return './'+parts.join('/')}
  function locator(n){const root=n.getRootNode();return root.host?[...locator(root.host),xpath(n)]:[xpath(n)]}
  function resolve(chain){let root=document,node;for(let i=0;i<chain.length;i++){if(i)root=node?.shadowRoot;if(!root)return null;
    // XPath engines do not accept ShadowRoot context. Evaluate in a temporary clone, then map the element path back.
    if(root instanceof ShadowRoot){const clone=document.createElement('div');clone.innerHTML=root.innerHTML;const found=document.evaluate(chain[i],clone,null,XPathResult.FIRST_ORDERED_NODE_TYPE,null).singleNodeValue;if(!found)return null;let indices=[],p=found;while(p&&p!==clone){indices.unshift([...p.parentNode.children].indexOf(p));p=p.parentNode}node=indices.reduce((n,j)=>n?.children[j],root)}
    else node=document.evaluate(chain[i],root,null,XPathResult.FIRST_ORDERED_NODE_TYPE,null).singleNodeValue;
  }return node}
  function contains(parent,node){while(node){if(node===parent)return true;node=node.parentElement||node.getRootNode().host}return false}
  const send = (type, extra={}) => parent.postMessage({source:'region-review',type,file:decodeURIComponent(location.pathname.split('/').pop()),...extra},location.origin);
  function walk(root, all) {
    for(const n of root.children || []) {
      if(n===host || /^(SCRIPT|STYLE|TEMPLATE|NOSCRIPT)$/.test(n.tagName)) continue;
      all.push(n); if(n.shadowRoot) walk(n.shadowRoot,all); walk(n,all);
    }
  }
  function detect() {
    const all=[];walk(document.body,all);
    const raw=all.filter(n=>{
      const r=n.getBoundingClientRect();
      if(r.width<5 || r.height<5 || getComputedStyle(n).visibility==='hidden') return false;
      if(n.matches('img,video,audio,iframe,canvas,svg'))return !n.parentElement?.closest('svg');
      if(!n.matches(semantic+',div,section,article,main,span,a,button,label,time'))return false;
      if(n.shadowRoot || n.querySelector(semantic))return false;
      if(!n.matches(semantic) && n.children.length && [...n.children].some(c=>clean(c.innerText).length>0))return false;
      return clean(n.innerText).length>=1 || !!(n.title||n.getAttribute('aria-label')) || (getComputedStyle(n).backgroundImage!=='none'&&r.width>=16&&r.height>=16);
    });
    const eligible=new Set(raw);
    const candidates=raw.filter(n=>{
      if(n.matches('img,video,audio,iframe,canvas,svg'))return true;
      let p=n.parentElement;
      while(p){if(p.matches(semantic)&&eligible.has(p))return false;p=p.parentElement}
      return true;
    });
    // The Python extractor owns body decisions and text order. Visible DOM
    // candidates only supplement ancillary labels; they cannot invent body text.
    const byId=new Map(all.map(n=>[n.getAttribute('data-review-node'),n]));
    const covered=[];
    const entries=prediction.regions.map(r=>{
      const node=byId.get(r.source_node)||null;
      if(node)covered.push(node);
      const auxiliary=node?classify(node,r.text):'pending';
      let label=['正文候选','标题/小标题'].includes(r.auto_label)?'body':r.auto_label==='待判断'?'pending':r.auto_label==='元数据'?(auxiliary==='body'||auxiliary==='pending'?'source':auxiliary):(auxiliary==='body'||auxiliary==='pending'?'noise':auxiliary);
      return {node,text:r.text,label,reason:r.reason,canonical_id:r.region_id};
    });
    for(const node of candidates){
      if(covered.some(n=>contains(n,node)||contains(node,n)))continue;
      const text=clean(node.innerText)||node.alt||node.getAttribute('aria-label')||node.title||'['+node.tagName.toLowerCase()+' 非文本区域]';
      let label=classify(node,clean(node.innerText));
      if(label==='body')label='pending';
      entries.push({node,text,label,reason:'未被静态提取器收录的可见区域',canonical_id:null});
    }
    regions=entries.map((entry,i)=>{
      const {node,text,label}=entry;
      const box=document.createElement('div');box.className='box '+label;
      const badge=document.createElement('button');badge.className='badge';
      badge.onclick=e=>{e.preventDefault();e.stopPropagation();select(i+1,false)};
      box.append(badge);ui.append(box);
      const rect=node?.getBoundingClientRect();
      const mapping_status=!node?'unmapped':!rect.width||!rect.height||getComputedStyle(node).visibility==='hidden'?'hidden':'mapped';
      return {id:i+1,node,box,text,locator:node?locator(node):[],tag:node?.tagName.toLowerCase()||'unknown',label,auto_label:label,predicted_label:label,reviewed:false,kind:'text',is_main:label==='body',canonical_id:entry.canonical_id,reason:entry.reason,mapping_status};
    });
    applyRules();publish();draw();
  }
  function publish(){send('regions',{title:document.title,snapshot,extraction:{page_type:prediction.page_type,scope_method:prediction.scope_method,content:prediction.content,status:prediction.extraction_status},regions:regions.map(({node,box,...r})=>r)})}
  function applyRules(){for(const r of regions){r.predicted_label=r.auto_label;for(const rule of rules){try{const target=resolve(rule.locator);if(target&&r.node&&contains(target,r.node))r.predicted_label=rule.label}catch{}}r.label=r.predicted_label}}
  function select(id,scroll){selected=id;const r=regions.find(r=>r.id===id);if(!r)return;
    chosen=r.node;if(!chosen){send('mapping-error',{message:'此静态区域在快照中未定位，正文仍保留在预览中。'});return}if(scroll)r.node.scrollIntoView({block:'center',behavior:'instant'});draw();send('selected',{id,locator:locator(chosen),text:clean(chosen.innerText).slice(0,180)});}
  function draw(){queued=false;host.style.display=enabled?'block':'none';for(const r of regions){if(!r.node||r.mapping_status==='hidden'){r.box.style.display='none';continue}const b=r.node.getBoundingClientRect();r.box.style.cssText=`left:${b.left}px;top:${b.top}px;width:${b.width}px;height:${b.height}px;display:${b.bottom<0||b.top>innerHeight||(focus&&!r.is_main&&!['body','missing'].includes(r.label)&&r.id!==selected)?'none':'block'}`;r.box.className='box '+r.label+(r.id===selected?' selected':'');r.box.querySelector('.badge').textContent=r.id+' '+names[r.label]}}
  function schedule(){if(!queued){queued=true;requestAnimationFrame(draw)}}
  addEventListener('scroll',schedule,true);addEventListener('resize',schedule);
  addEventListener('click',e=>{if(e.composedPath().includes(host))return;const r=regions.find(r=>e.composedPath().includes(r.node));if(r){e.preventDefault();e.stopPropagation();select(r.id,false)}},true);
  addEventListener('message',e=>{if(e.source!==parent||e.origin!==location.origin)return;const m=e.data;if(m.type==='select')select(m.id,true);if(m.type==='label'){const r=regions.find(r=>r.id===m.id);if(r){r.label=m.label;draw()}}if(m.type==='boxes'){enabled=m.enabled;focus=m.focus!==false;draw()}
    if(m.type==='parent'&&chosen){chosen=chosen.parentElement||chosen.getRootNode().host||chosen;const ids=regions.filter(r=>contains(chosen,r.node)).map(r=>r.id);send('group',{ids,locator:locator(chosen),text:clean(chosen.innerText).slice(0,180)})}
    if(m.type==='test-rule'){try{const target=resolve(m.locator);send('rule-match',{ids:regions.filter(r=>target&&contains(target,r.node)).map(r=>r.id)})}catch(err){send('rule-match',{ids:[],error:err.message})}}
  });
  let started=false;
  async function start(){
    if(started)return;started=true;
    try{
      const file=decodeURIComponent(location.pathname.split('/').pop());
      const response=await fetch(location.origin+'/api/extraction/'+encodeURIComponent(file),{cache:'no-store'});
      if(!response.ok)throw Error('正文接口不可用（HTTP '+response.status+'），请重新启动 start_review.ps1，并打开新终端打印的地址。');
      prediction=await response.json();
      if(prediction.snapshot!==snapshot)throw Error('网页已更新，请重新加载以匹配快照。');
      const ruleResponse=await fetch(location.origin+'/api/rules',{cache:'no-store'});
      if(!ruleResponse.ok)throw Error('XPath 规则加载失败，请重试。');
      rules=(await ruleResponse.json()).filter(r=>(r.files||[r.file]).includes(file));
      detect();
    }catch(err){send('error',{message:err.message})}
  }
  // 不等待远程广告和图片触发 load；稍后仍可通过刷新重新检测动态页面。
  if(document.readyState==='loading')addEventListener('DOMContentLoaded',()=>setTimeout(start,600),{once:true});else setTimeout(start,600);
  new ResizeObserver(schedule).observe(document.documentElement);
})();
