"""Build resource-backed display copies for frozen Stage 3 snapshots.

The frozen HTML and evaluation hashes are never modified. Display copies are
for visual comparison only; extraction and quality evidence continue to use
the original bytes.
"""
import hashlib
import json
import re
import sys
from pathlib import Path
from urllib.parse import urljoin, urlsplit
from urllib.request import ProxyHandler, Request, build_opener

from lxml import html as lxml_html

ROOT=Path(__file__).resolve().parents[1]
PROTOCOL=ROOT/'output/stage3/protocol'
OUT=ROOT/'output/stage3/display'
UA='WebExtractLearningDisplay/1.0'


def digest(data):
    return hashlib.sha256(data).hexdigest()


def ext(url, content_type=''):
    suffix=Path(urlsplit(url).path).suffix.lower()
    if suffix and len(suffix)<=8 and re.fullmatch(r'\.[a-z0-9]+',suffix):
        return suffix
    mapping={'text/css':'.css','image/jpeg':'.jpg','image/png':'.png','image/gif':'.gif',
             'image/webp':'.webp','font/woff':'.woff','font/woff2':'.woff2','image/svg+xml':'.svg'}
    return mapping.get(content_type.split(';')[0].lower(),'.bin')


class Cache:
    def __init__(self, root, opener):
        self.root=root
        self.opener=opener
        self.records=[]
        self.memo={}
        self.errors=[]

    def fetch(self, url, kind):
        if not url.startswith(('http://','https://')):
            return None
        if url in self.memo:
            return self.memo[url]
        try:
            response=self.opener.open(Request(url,headers={'User-Agent':UA}),timeout=20)
            data=response.read(8_000_001)
            if len(data)>8_000_000:
                raise ValueError('resource exceeds 8MB')
            ctype=response.headers.get('Content-Type','application/octet-stream')
            if kind=='css' and 'text/html' in ctype.lower():
                raise ValueError('CSS URL returned HTML')
            name=digest(data)[:20]+ext(url,ctype)
            path=self.root/'assets'/name
            path.parent.mkdir(parents=True,exist_ok=True)
            path.write_bytes(data)
            relative='assets/'+name
            self.memo[url]=relative
            self.records.append({'url':url,'kind':kind,'status':getattr(response,'status',200),
                                 'content_type':ctype,'bytes':len(data),'sha256':digest(data),'local':relative})
            return relative,data,ctype
        except Exception as exc:
            self.errors.append({'url':url,'kind':kind,'error':str(exc)})
            self.memo[url]=None
            return None


def css_urls(text):
    values = re.findall(r'url\(([^)]*)\)', text, flags=re.I)
    return [value.strip().strip(chr(34) + chr(39)) for value in values]


def process_css(cache, data, css_url):
    text=data.decode('utf-8-sig',errors='replace')
    for ref in css_urls(text):
        if ref.startswith(('data:','#')):
            continue
        absolute=urljoin(css_url,ref)
        result=cache.fetch(absolute,'css_asset')
        if not result:
            continue
        local=result[0]
        # CSS is stored in the common assets directory; references are relative
        # to that directory, so the filename is sufficient for cached assets.
        text=text.replace(ref,Path(local).name)
    return text.encode('utf-8')


def build_page(site,index,source,original_url,opener):
    page_dir=OUT/site/f'test_{index:02d}'
    page_dir.mkdir(parents=True,exist_ok=True)
    cache=Cache(page_dir,opener)
    raw=source.read_text(encoding='utf-8',errors='replace')
    soup=lxml_html.document_fromstring(raw)
    original_base=original_url
    for base in soup.xpath('//base'):
        if base.get('href'):
            original_base=urljoin(original_url,base['href'])
        base.getparent().remove(base)
    # Do not execute captured JavaScript: it can redirect, rewrite the DOM or
    # create a new live page. Keep the node as a visible note for auditability.
    for script in soup.xpath('//script'):
        script.set('type','application/x-disabled-stage3-snapshot')
    for link in soup.xpath('//link'):
        href=link.get('href')
        if not href or 'stylesheet' not in (link.get('rel') or '').lower():
            continue
        absolute=urljoin(original_base,href)
        result=cache.fetch(absolute,'css')
        if result:
            css_text=process_css(cache,result[1],absolute)
            local=page_dir/'assets'/(digest(css_text)[:20]+'.css')
            local.write_bytes(css_text)
            link.set('href',f'assets/{local.name}')
    for node in soup.xpath('//img|//source|//video|//audio'):
        attr='src'
        value=node.get(attr)
        if not value:
            continue
        result=cache.fetch(urljoin(original_base,value),'media')
        if result:
            node.set(attr,result[0])
    head=soup.xpath('//head')
    head=head[0] if head else lxml_html.Element('head')
    if not head.getparent():
        soup.insert(0,head)
    meta=lxml_html.Element('meta',charset='utf-8')
    head.insert(0,meta)
    banner=lxml_html.Element('div',id='stage3-display-notice')
    banner.set('style','position:relative;z-index:2147483647;background:#fff3cd;color:#664d03;padding:10px;font:14px/1.5 sans-serif;border-bottom:2px solid #e0b000;')
    banner.text=f'阶段3展示副本：{site}/test_{index:02d}。仅用于视觉对照；抽取与评测仍使用冻结原HTML。原网页：{original_url}。脚本已停用，无法恢复的视频/动态组件请看报告说明。'
    body=soup.xpath('//body')
    (body[0] if body else soup).insert(0,banner)
    output=page_dir/f'test_{index:02d}.html'
    output.write_bytes(lxml_html.tostring(soup,encoding='utf-8',doctype='<!doctype html>',method='html'))
    manifest={'site':site,'index':index,'source':str(source.relative_to(ROOT)),'source_sha256':digest(source.read_bytes()),
              'original_url':original_url,'display_file':str(output.relative_to(ROOT)),'assets':cache.records,'errors':cache.errors,
              'scripts_disabled':True,'evaluation_uses_source':True}
    (page_dir/'manifest.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2),encoding='utf-8')
    return manifest


def run():
    opener=build_opener(ProxyHandler({'http':'http://127.0.0.1:7897','https':'http://127.0.0.1:7897'}))
    all_manifests=[]
    for site in ['sina','chinanews']:
        urls=json.loads((PROTOCOL/site/'selection.json').read_text(encoding='utf-8'))['urls']
        for i,url in enumerate(urls,1):
            source=PROTOCOL/site/f'test_{i:02d}.html'
            all_manifests.append(build_page(site,i,source,url,opener))
            m=all_manifests[-1]
            print(f"{site}/test_{i:02d}: assets={len(m['assets'])} errors={len(m['errors'])}")
    OUT.mkdir(parents=True,exist_ok=True)
    index=['<!doctype html><meta charset="utf-8"><title>Stage 3 原网页展示副本</title>',
           '<style>body{font:16px sans-serif;max-width:1000px;margin:30px auto}li{margin:8px 0}</style>',
           '<h1>Stage 3 原网页展示副本</h1><p>这些副本只为恢复静态样式和资源，抽取评测仍使用冻结源HTML。脚本已停用，动态/视频能力不能由静态快照凭空恢复。</p><ul>']
    for m in all_manifests:
        index.append(f"<li><a href='{m['site']}/test_{m['index']:02d}/test_{m['index']:02d}.html'>{m['site']}/test_{m['index']:02d}</a>；资源 {len(m['assets'])}，失败 {len(m['errors'])}；<a href='{m['site']}/test_{m['index']:02d}/manifest.json'>资源清单</a></li>")
    index.append('</ul>')
    (OUT/'index.html').write_text('\n'.join(index),encoding='utf-8')
    (OUT/'manifest.json').write_text(json.dumps(all_manifests,ensure_ascii=False,indent=2),encoding='utf-8')
    print('DISPLAY READY:',OUT/'index.html')


if __name__=='__main__':
    run()
