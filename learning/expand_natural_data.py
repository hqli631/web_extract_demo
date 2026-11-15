"""Fetch a preregistered bounded set of natural pages without inspecting test DOM."""
from __future__ import annotations
import argparse
import hashlib
import json
from pathlib import Path
import time
from urllib.error import HTTPError
from urllib.parse import urlsplit
from urllib.request import Request, build_opener, HTTPRedirectHandler
from urllib.robotparser import RobotFileParser

ROOT = Path(__file__).resolve().parents[1]
UA = 'WebExtractLearning/1.0'
MAX_BYTES = 5_000_000

def sha(raw):
    return hashlib.sha256(raw).hexdigest()

def fetch(config_path=ROOT/'config/natural_expansion_v1.json'):
    config_raw = config_path.read_bytes()
    config = json.loads(config_raw)
    allowed = {urlsplit(p['url']).hostname for c in config['clusters'] for p in c['pages']}
    class Redirect(HTTPRedirectHandler):
        def redirect_request(self, req, fp, code, msg, headers, newurl):
            if urlsplit(newurl).hostname not in allowed:
                raise ValueError('redirect outside preregistered domains')
            return super().redirect_request(req, fp, code, msg, headers, newurl)
    opener = build_opener(Redirect())
    robots = {}
    manifest = dict(format_version=1, preregistration_path=str(config_path.relative_to(ROOT)).replace('\\','/'),
                    preregistration_sha256=sha(config_raw), test_dom_inspected=False, clusters=[], errors=[])
    for cluster in config['clusters']:
        result = {k:v for k,v in cluster.items() if k != 'pages'}
        result['pages'] = []
        for i,page in enumerate(cluster['pages']):
            url = page['url']; parts = urlsplit(url); origin = parts.scheme+'://'+parts.netloc
            try:
                if origin not in robots:
                    parser = RobotFileParser()
                    try:
                        with opener.open(Request(origin+'/robots.txt',headers={'User-Agent':UA}),timeout=20) as response:
                            parser.parse(response.read(MAX_BYTES).decode('utf8','replace').splitlines())
                    except HTTPError as error:
                        if error.code == 404: parser.parse([])
                        else: raise
                    robots[origin] = parser
                if not robots[origin].can_fetch(UA,url): raise ValueError('robots disallow')
                destination = ROOT/'data/natural_v1'/cluster['task_id']/(page['role']+'_'+str(i+1)+'.html')
                if destination.exists():
                    raw=destination.read_bytes(); final=url; content_type='text/html'; status='reused_frozen_snapshot'
                else:
                    time.sleep(0.3)
                    with opener.open(Request(url,headers={'User-Agent':UA}),timeout=30) as response:
                        raw=response.read(MAX_BYTES+1); final=response.geturl(); content_type=response.headers.get_content_type()
                    if len(raw)>MAX_BYTES: raise ValueError('response exceeds bound')
                    if content_type not in {'text/html','application/xhtml+xml'}: raise ValueError('not HTML')
                    if not robots[origin].can_fetch(UA,final): raise ValueError('robots disallow redirect')
                    destination.parent.mkdir(parents=True,exist_ok=True);destination.write_bytes(raw);status='downloaded'
                result['pages'].append(dict(page,path=str(destination.relative_to(ROOT)).replace('\\','/'),
                    sha256=sha(raw),bytes=len(raw),final_url=final,content_type=content_type,
                    exposure='new' if page['role']=='test' else 'development_exposed',
                    fetched_at=time.strftime('%Y-%m-%dT%H:%M:%SZ',time.gmtime()),status=status))
            except Exception as error:
                manifest['errors'].append(dict(task_id=cluster['task_id'],url=url,error=str(error)))
        manifest['clusters'].append(result)
    destination=ROOT/'output/stage5/multitask/natural_manifest.json'
    destination.parent.mkdir(parents=True,exist_ok=True)
    destination.write_text(json.dumps(manifest,ensure_ascii=False,indent=2)+'\n',encoding='utf8')
    print(json.dumps(dict(pages=sum(len(c['pages']) for c in manifest['clusters']),errors=manifest['errors'],test_dom_inspected=False)))
    return manifest

if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--config',type=Path,default=ROOT/'config/natural_expansion_v1.json')
    args=parser.parse_args();fetch(args.config)
