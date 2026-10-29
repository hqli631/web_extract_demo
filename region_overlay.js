(() => {
  const semantic = 'p,h1,h2,h3,h4,h5,h6,li,pre,td,th,figcaption,blockquote,dt,dd';
  const clean = s => (s || '').replace(/\s+/g, ' ').trim();
  const names={body:'正文',title:'标题',time:'发布时间',source:'来源',author:'作者',navigation:'导航',advertisement:'广告',recommendation:'相关推荐',sidebar:'侧栏',comment:'评论',toolbar:'功能工具',footer:'页脚版权',image:'图片',media:'音视频',noise:'其他杂质',pending:'待判断',missing:'缺漏'};
  function classify(node,text){
    const own=(node.id+' '+node.className+' '+node.tagName).toLowerCase();
    let n=node, identity='';
    while(n){identity+=' '+n.tagName+' '+n.id+' '+n.className;n=n.parentElement||n.getRootNode().host}
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
  const send = (type, extra={}) => parent.postMessage({source:'region-review',type,...extra},location.origin);
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
    regions=candidates.map((node,i)=>{
      const text=clean(node.innerText)||node.alt||node.getAttribute('aria-label')||node.title||'['+node.tagName.toLowerCase()+' 非文本区域]';
      const label=classify(node,clean(node.innerText));
      const box=document.createElement('div');box.className='box '+label;
      const badge=document.createElement('button');badge.className='badge';badge.textContent=(i+1)+' '+names[label];
      badge.onclick=e=>{e.preventDefault();e.stopPropagation();select(i+1,false)};
      box.append(badge);ui.append(box);
      return {id:i+1,node,box,text,tag:node.tagName.toLowerCase(),label,auto_label:label,kind:node.matches('img,svg,video,audio,iframe,canvas')?'media':'text'};
    });
    send('regions',{title:document.title,regions:regions.map(({node,box,...r})=>r)});draw();
  }
  function select(id,scroll){selected=id;const r=regions.find(r=>r.id===id);if(!r)return;
    if(scroll)r.node.scrollIntoView({block:'center',behavior:'instant'});draw();send('selected',{id});}
  function draw(){queued=false;host.style.display=enabled?'block':'none';for(const r of regions){const b=r.node.getBoundingClientRect();r.box.style.cssText=`left:${b.left}px;top:${b.top}px;width:${b.width}px;height:${b.height}px;display:${b.bottom<0||b.top>innerHeight?'none':'block'}`;r.box.className='box '+r.label+(r.id===selected?' selected':'');r.box.querySelector('.badge').textContent=r.id+' '+names[r.label]}}
  function schedule(){if(!queued){queued=true;requestAnimationFrame(draw)}}
  addEventListener('scroll',schedule,true);addEventListener('resize',schedule);
  addEventListener('click',e=>{if(e.composedPath().includes(host))return;const r=regions.find(r=>e.composedPath().includes(r.node));if(r){e.preventDefault();e.stopPropagation();select(r.id,false)}},true);
  addEventListener('message',e=>{if(e.source!==parent||e.origin!==location.origin)return;const m=e.data;if(m.type==='select')select(m.id,true);if(m.type==='label'){const r=regions.find(r=>r.id===m.id);if(r){r.label=m.label;draw()}}if(m.type==='boxes'){enabled=m.enabled;draw()}});
  if(document.readyState==='complete')detect();else addEventListener('load',detect,{once:true});
  new ResizeObserver(schedule).observe(document.documentElement);
})();
