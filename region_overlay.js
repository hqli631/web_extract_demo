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
  let mainNode=null, chosen=null, focus=true, rules=[];
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
    // 先找正文主容器：可见文本量高、链接比例低、噪声身份少的容器。
    // Aggregate visible leaf text across shadow hosts: host.innerText does not
    // include text in its shadow tree and cannot score web components reliably.
    const stats=new Map();
    for(const c of candidates){const text=clean(c.innerText);if(!text)continue;const label=classify(c,text),likely=label==='body'||(label==='pending'&&c.matches('p,li,pre,blockquote'));
      let n=c.parentElement||c.getRootNode().host;
      while(n&&n!==document.body&&n!==document.documentElement){const s=stats.get(n)||{text:0,body:0};s.text+=text.length;if(likely)s.body+=text.length;stats.set(n,s);n=n.parentElement||n.getRootNode().host}
    }
    function mainScore(n){const s=stats.get(n),identity=(n.id+' '+n.className).toLowerCase();
      let score=Math.min(s.body,12000)/100-(s.text-s.body)/Math.max(s.text,1)*50+(n.matches('article,main')?25:0);
      if(/article|story|content|正文/.test(identity))score+=15;
      if(/nav|menu|side|aside|footer|comment|recommend|advert|banner/.test(identity)||n.matches('aside,nav,footer'))score-=100;
      if(n.querySelector('article,main'))score-=25;
      return score;
    }
    mainNode=[...stats.keys()].filter(n=>stats.get(n).body>=120).sort((a,b)=>mainScore(b)-mainScore(a))[0]||null;
    regions=candidates.map((node,i)=>{
      const text=clean(node.innerText)||node.alt||node.getAttribute('aria-label')||node.title||'['+node.tagName.toLowerCase()+' 非文本区域]';
      const label=classify(node,clean(node.innerText));
      const box=document.createElement('div');box.className='box '+label;
      const badge=document.createElement('button');badge.className='badge';badge.textContent=(i+1)+' '+names[label];
      badge.onclick=e=>{e.preventDefault();e.stopPropagation();select(i+1,false)};
      box.append(badge);ui.append(box);
      const inMain=!!(mainNode && contains(mainNode,node));
      const initial=inMain&&label==='pending'&&node.matches('p,li,pre,blockquote,h2,h3')?'body':label;
      return {id:i+1,node,box,text,locator:locator(node),tag:node.tagName.toLowerCase(),label:initial,auto_label:initial,predicted_label:initial,reviewed:false,kind:node.matches('img,svg,video,audio,iframe,canvas')?'media':'text',is_main:inMain};
    });
    applyRules();publish();draw();
  }
  function publish(){send('regions',{title:document.title,snapshot,regions:regions.map(({node,box,...r})=>r)})}
  function applyRules(){for(const r of regions){r.predicted_label=r.auto_label;for(const rule of rules){try{const target=resolve(rule.locator);if(target&&contains(target,r.node))r.predicted_label=rule.label}catch{}}r.label=r.predicted_label}}
  function select(id,scroll){selected=id;const r=regions.find(r=>r.id===id);if(!r)return;
    chosen=r.node;if(scroll)r.node.scrollIntoView({block:'center',behavior:'instant'});draw();send('selected',{id,locator:locator(chosen),text:clean(chosen.innerText).slice(0,180)});}
  function draw(){queued=false;host.style.display=enabled?'block':'none';for(const r of regions){const b=r.node.getBoundingClientRect();r.box.style.cssText=`left:${b.left}px;top:${b.top}px;width:${b.width}px;height:${b.height}px;display:${b.bottom<0||b.top>innerHeight||(focus&&!r.is_main&&!['body','missing'].includes(r.label)&&r.id!==selected)?'none':'block'}`;r.box.className='box '+r.label+(r.id===selected?' selected':'');r.box.querySelector('.badge').textContent=r.id+' '+names[r.label]}}
  function schedule(){if(!queued){queued=true;requestAnimationFrame(draw)}}
  addEventListener('scroll',schedule,true);addEventListener('resize',schedule);
  addEventListener('click',e=>{if(e.composedPath().includes(host))return;const r=regions.find(r=>e.composedPath().includes(r.node));if(r){e.preventDefault();e.stopPropagation();select(r.id,false)}},true);
  addEventListener('message',e=>{if(e.source!==parent||e.origin!==location.origin)return;const m=e.data;if(m.type==='select')select(m.id,true);if(m.type==='label'){const r=regions.find(r=>r.id===m.id);if(r){r.label=m.label;draw()}}if(m.type==='boxes'){enabled=m.enabled;focus=m.focus!==false;draw()}
    if(m.type==='parent'&&chosen){chosen=chosen.parentElement||chosen.getRootNode().host||chosen;const ids=regions.filter(r=>contains(chosen,r.node)).map(r=>r.id);send('group',{ids,locator:locator(chosen),text:clean(chosen.innerText).slice(0,180)})}
    if(m.type==='test-rule'){try{const target=resolve(m.locator);send('rule-match',{ids:regions.filter(r=>target&&contains(target,r.node)).map(r=>r.id)})}catch(err){send('rule-match',{ids:[],error:err.message})}}
  });
  let started=false;
  async function start(){if(started)return;started=true;try{const file=decodeURIComponent(location.pathname.split('/').pop());rules=(await (await fetch(location.origin+'/api/rules')).json()).filter(r=>(r.files||[r.file]).includes(file))}catch{}detect()}
  // 不等待远程广告和图片触发 load；稍后仍可通过刷新重新检测动态页面。
  if(document.readyState==='loading')addEventListener('DOMContentLoaded',()=>setTimeout(start,600),{once:true});else setTimeout(start,600);
  new ResizeObserver(schedule).observe(document.documentElement);
})();
