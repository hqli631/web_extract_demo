"""Unit 3.1: shell audit, deduplication and immutable holdout selection."""
import argparse
import hashlib
import json
import re
import sys
import time
from datetime import datetime, timezone
from html import escape
from pathlib import Path
from urllib.parse import urljoin, urlsplit, urlunsplit, parse_qs
from urllib.request import build_opener, ProxyHandler, Request
from urllib.robotparser import RobotFileParser

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from lxml import html
from learning.cluster_layouts import build, signature

OUT = ROOT/'output/stage3/protocol'
UA = 'WebExtractLearning/1.0'
TARGETS = {
    'sina': ('https://finance.sina.com.cn/roll/', "//div[@id='artibody']"),
    'chinanews': ('https://www.chinanews.com.cn/china/', "//div[contains(concat(' ',normalize-space(@class),' '),' left_zw ')]"),
}


def sha(data):
    return hashlib.sha256(data).hexdigest()


def read(path):
    return json.loads(path.read_text(encoding='utf-8'))


def write(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding='utf-8')


def canonical(url):
    p = urlsplit(url)
    return urlunsplit(('https', p.netloc.lower(), p.path, '', ''))


def shell(node):
    result = []
    for _ in range(5):
        if node is None:
            break
        result.append(signature(node))
        node = node.getparent()
    return result


def structure(data, xpath):
    tree = html.document_fromstring(data)
    nodes = tree.xpath(xpath)
    if len(nodes) != 1:
        return {'container_count': len(nodes), 'shell': [], 'body': ''}
    node = nodes[0]
    layout = shell(node)
    clone = html.fromstring(html.tostring(node))
    for junk in clone.xpath('.//script|.//style|.//noscript'):
        junk.drop_tree()
    text = ''.join(clone.text_content().split())
    return {'container_count': 1, 'shell': layout, 'body': text}


def grams(text):
    return {text[i:i+5] for i in range(max(0, len(text)-4))}


def near(a, b):
    return len(a & b)/len(a | b) if a | b else 0


def history():
    urls, bodies, hashes = set(), [], set()
    folders = ['samples','reports','config','docs','news_validation','validation_holdout',
               'validation_blind','validation_blind_round2','output/agent_io']
    for folder in folders:
        for path in sorted((ROOT/folder).rglob('*')):
            if not path.is_file() or path.suffix not in {'.html','.json','.md'}:
                continue
            data = path.read_bytes()
            for url in re.findall(r'https?://(?:finance\.sina\.com\.cn|www\.chinanews\.com\.cn)/[^\s"<>]+?\.shtml', data.decode('utf-8', errors='ignore')):
                urls.add(canonical(url))
            if path.suffix == '.html' and ('samples' in path.parts or path.parent.name == 'snapshots'):
                hashes.add(sha(data))
                for _, xpath in TARGETS.values():
                    s = structure(data, xpath)
                    if len(s['body']) >= 100:
                        bodies.append((path.relative_to(ROOT).as_posix(), sha(s['body'].encode()), grams(s['body'])))
                        break
    return urls, bodies, hashes


def audit():
    inventory = build()
    result = []
    for t in inventory['targets']:
        members = [p for p in inventory['pages'] if t['target_template']=='sina' and 'artibody' in p['region_xpath']
                   or t['target_template']=='chinanews' and 'left_zw' in p['region_xpath']]
        records = []
        for page in members:
            s = structure((ROOT/page['file']).read_bytes(), TARGETS[t['target_template']][1])
            records.append({'file':page['file'], 'sha256':page['sha256'], 'shell':s['shell'],
                            'local_cluster':page['cluster_id'], 'direct_tags':page['direct_tags']})
        verified = len({tuple(p['shell']) for p in records}) == 1
        result.append({**t, 'cluster_id':t['target_template']+'_shell_v2',
                       'shell_verified':verified, 'shell':records[0]['shell'], 'members':records})
    return result


def fetch(opener, url):
    with opener.open(Request(url, headers={'User-Agent':UA}), timeout=25) as response:
        data = response.read(5_000_001)
        if len(data)>5_000_000:
            raise ValueError('response exceeds 5MB')
        if urlsplit(response.geturl()).hostname != urlsplit(url).hostname:
            raise ValueError('redirect changed host')
        return data, response.geturl(), response.status


def select_urls(data, listing, target, known):
    urls = []
    for href in html.document_fromstring(data).xpath('//a/@href'):
        url = urljoin(listing, href)
        p = urlsplit(url)
        if p.hostname=='cj.sina.cn' and p.path=='/article/norm_detail':
            url = parse_qs(p.query).get('url',[''])[0]
        url = canonical(url)
        pattern = (r'^https://finance\.sina\.com\.cn/.*/doc-[a-z0-9]+\.shtml$' if target=='sina'
                   else r'^https://www\.chinanews\.com\.cn/gn/\d{4}/\d{2}-\d{2}/\d+\.shtml$')
        if re.match(pattern,url) and url not in known and url not in urls:
            urls.append(url)
        if len(urls)==6:
            break
    return urls


def collect():
    OUT.mkdir(parents=True, exist_ok=True)
    protocol_path = OUT/'protocol.json'
    if protocol_path.exists():
        raise ValueError('Existing protocol: refuse recollection/reselection. Use default replay.')
    known, _, _ = history()
    protocol = {'version':1, 'created_at':datetime.now(timezone.utc).isoformat(),
                'selection':'each listing: first 6 historically unknown article URLs in DOM order; no replacement on failures',
                'targets':{k:{'listing':v[0],'container_xpath':v[1]} for k,v in TARGETS.items()},
                'near_duplicate_threshold':.85, 'historical_urls':sorted(known),
                'historical_shell_audit':audit(), 'script_sha256':sha(Path(__file__).read_bytes()),
                'scope':'static shell/dedup only; no extraction quality evaluation or test text in generation prompt'}
    write(protocol_path, protocol)
    opener = build_opener(ProxyHandler({'http':'http://127.0.0.1:7897','https':'http://127.0.0.1:7897'}))
    manifest = []
    for name, (listing, _) in TARGETS.items():
        folder=OUT/name
        folder.mkdir(exist_ok=True)
        try:
            robots_data, _, _ = fetch(opener, urljoin(listing,'/robots.txt'))
            (folder/'robots.txt').write_bytes(robots_data)
            robots=RobotFileParser()
            robots.parse(robots_data.decode('utf-8',errors='replace').splitlines())
            if not robots.can_fetch(UA,listing):
                raise ValueError('robots disallows listing')
            listing_data, _, _ = fetch(opener,listing)
            (folder/'listing.html').write_bytes(listing_data)
            urls=select_urls(listing_data,listing,name,known)
            write(folder/'selection.json', {'listing_sha256':sha(listing_data),'urls':urls})
            for i,url in enumerate(urls,1):
                record={'target':name,'url':url,'role':'sealed_test','attempted_at':datetime.now(timezone.utc).isoformat()}
                try:
                    if not robots.can_fetch(UA,url):
                        raise ValueError('robots disallows article')
                    data, final, status=fetch(opener,url)
                    path=folder/f'test_{i:02d}.html'
                    path.write_bytes(data)
                    record.update(status='fetched',http_status=status,final_url=final,
                                  file=path.relative_to(ROOT).as_posix(),sha256=sha(data))
                except Exception as exc:
                    record.update(status='failed',error=str(exc))
                manifest.append(record)
                write(OUT/'manifest.json',manifest)
                print(name,i,record['status'],flush=True)
                time.sleep(1)
        except Exception as exc:
            manifest.append({'target':name,'status':'discovery_failed','error':str(exc)})
            write(OUT/'manifest.json',manifest)


def replay():
    protocol=read(OUT/'protocol.json')
    groups=protocol['historical_shell_audit']
    for group in groups:
        for member in group['members']:
            if sha((ROOT/member['file']).read_bytes()) != member['sha256']:
                raise ValueError('historical snapshot changed: '+member['file'])
    manifest=read(OUT/'manifest.json')
    for name in TARGETS:
        selection=read(OUT/name/'selection.json')
        if sha((OUT/name/'listing.html').read_bytes()) != selection['listing_sha256']:
            raise ValueError('listing snapshot changed')
        if selection['urls'] != select_urls((OUT/name/'listing.html').read_bytes(),TARGETS[name][0],name,set(protocol['historical_urls'])):
            raise ValueError('selection no longer matches original listing order')
        if [r.get('url') for r in manifest if r['target']==name and r.get('url')] != selection['urls']:
            raise ValueError('manifest/selection mismatch')
    known,bodies,hashes=history()
    historic_duplicates=[]
    for i,(name,digest,g) in enumerate(bodies):
        for old,old_digest,og in bodies[:i]:
            score=near(g,og)
            if digest==old_digest or score>=.85:
                historic_duplicates.append({'left':old,'right':name,'similarity':round(score,6)})
    tests=[]
    for record in manifest:
        item=dict(record)
        if record['status']=='fetched':
            data=(ROOT/record['file']).read_bytes()
            if sha(data)!=record['sha256']:
                raise ValueError('snapshot changed: '+record['file'])
            s=structure(data,TARGETS[record['target']][1])
            g=grams(s['body'])
            best=max([(near(g,og),old) for old,_,og in bodies],default=(0,None))
            group=next(t for t in groups if t['target_template']==record['target'])
            item.update(shell_match=s['shell']==group['shell'],body_chars=len(s['body']),
                        exact_snapshot_duplicate=sha(data) in hashes,
                        historical_url_overlap=record['url'] in protocol['historical_urls'],
                        nearest_file=best[1],char5_jaccard=round(best[0],6),
                        near_duplicate=best[0]>=protocol['near_duplicate_threshold'])
            item['short_static_text_risk']=item['body_chars']<100
            item['eligible']=item['shell_match'] and not any(
                item[k] for k in ['exact_snapshot_duplicate','historical_url_overlap','near_duplicate'])
            bodies.append((record['file'],sha(s['body'].encode()),g))
            hashes.add(sha(data))
        else:
            item['eligible']=False
        tests.append(item)
    counts={name:sum(t['eligible'] and t['target']==name for t in tests) for name in TARGETS}
    ready=all(n==6 for n in counts.values()) and all(g['shell_verified'] for g in groups)
    corrections=[]
    for group in groups:
        selected=[]
        for path in group['generation_files']:
            body=structure((ROOT/path).read_bytes(),TARGETS[group['target_template']][1])['body']
            selected.append((path,grams(body)))
        repair=[]
        for path in group['repair_pool']:
            g=grams(structure((ROOT/path).read_bytes(),TARGETS[group['target_template']][1])['body'])
            duplicate=next((old for old,og in selected if near(g,og)>=.85),None)
            if duplicate:
                corrections.append({'removed_from_repair':path,'duplicate_of':duplicate})
            else:
                repair.append(path)
                selected.append((path,g))
        # Fixed path ordering, historical pool only; never borrow a sealed test page.
        for path,_,g in sorted(bodies[:len(bodies)-sum(t['status']=='fetched' for t in tests)],key=lambda x:x[0]):
            if len(repair)>=3:
                break
            if path in [p for p,_ in selected] or any(near(g,og)>=.85 for _,og in selected):
                continue
            s=structure((ROOT/path).read_bytes(),TARGETS[group['target_template']][1])
            if s['shell']!=group['shell']:
                continue
            repair.append(path)
            selected.append((path,g))
            corrections.append({'added_to_repair':path,'selection':'first historical path in lexical order with matching shell and no near duplicate'})
        group['verified_repair']=repair
    ready=ready and all(len(g['verified_repair'])==3 for g in groups)
    result={'unit':'3.1','status':'ready_for_user_learning_check' if ready else 'incomplete_sample_gap',
            'test_counts':counts,'historical_duplicate_pairs':historic_duplicates,
            'protocol_sha256':sha((OUT/'protocol.json').read_bytes()),
            'tests':tests,'source_text_exposed_in_report':False,'split_corrections':corrections,
            'preflight_revision':'Removed unregistered >=100 character eligibility cutoff before split freeze; short pages retained as risks, no replacement URLs.',
            'limitations':['历史知识辅助的任务壳簇，不是无监督或视觉聚类。',
                          '新测试只做结构/去重预检，未检查抽取效果；后续生成器不得读测试原文。',
                          '字符5gram去重是启发式，不能证明所有语义重复均被识别。']}
    write(OUT/'verification.json',result)
    split={'protocol_sha256':result['protocol_sha256'],'status':'frozen' if ready else 'provisional',
           'revision':2,'supersedes':'split.json (initial assignment; contains historical generation/repair duplicate)',
           'clusters':[{'cluster_id':g['cluster_id'],'generation':g['generation_files'],
                        'repair':g['verified_repair'],'test':[t['file'] for t in tests if t.get('file') and t['target']==g['target_template'] and t['eligible']],
                        'snapshot_sha256':{p['file']:p['sha256'] for p in g['members']} |
                            {p:sha((ROOT/p).read_bytes()) for p in g['verified_repair']} |
                            {t['file']:t['sha256'] for t in tests if t.get('file') and t['target']==g['target_template'] and t['eligible']}}
                       for g in groups]}
    path=OUT/'split_v2.json'
    if path.exists() and read(path)['status']=='frozen' and read(path)!=split:
        raise ValueError('refuse changed frozen split')
    for group in split['clusters']:
        for file,digest in group['snapshot_sha256'].items():
            if sha((ROOT/file).read_bytes())!=digest:
                raise ValueError('split snapshot changed: '+file)
    write(path,split)
    sections=['<!doctype html><meta charset="utf-8"><title>3.1 样本协议</title>',
              '<style>body{font:16px/1.8 sans-serif;max-width:1100px;margin:30px auto}pre{white-space:pre-wrap}td,th{padding:8px;border:1px solid #ccc}table{border-collapse:collapse}</style>',
              '<h1>3.1 模板壳核验与样本协议</h1><p>状态：'+escape(result['status'])+'</p>',
              '<p>保留v1内容路径分组；v2另用五级祖先壳路径核验，先依据历史页面制定，再验证新页，不按抽取效果调分组。</p>']
    for group in groups:
        sections += ['<h2>'+group['cluster_id']+'</h2><pre>'+escape('\n'.join(group['shell']))+'</pre>',
                     '<p>历史页6：生成3、修复3；合格封存新页：'+str(counts[group['target_template']])+'/6</p>',
                     '<p>簇内变体（只展示历史页）：</p><pre>'+escape(json.dumps(group['members'],ensure_ascii=False,indent=2))+'</pre>']
    sections += ['<h2>封存页预检（不展示正文）</h2><p>静态文字短不是淘汰条件，不按预检结果更换页面。低于100字只记风险，图片/动态完整性后续评估。</p><table><tr><th>模板</th><th>文件/失败</th><th>壳匹配</th><th>近重复</th><th>短文本风险</th><th>可纳入</th></tr>']
    for t in tests:
        sections += ['<tr>'+''.join('<td>'+escape(str(t.get(k)))+'</td>' for k in ['target','file','shell_match','near_duplicate','short_static_text_risk','eligible'])+'</tr>']
    sections += ['</table><p>历史重复候选对数：'+str(len(historic_duplicates))+'。详情见verification.json；不计为新增样本。</p>',
                 '<h2>使用split_v2.json：历史重复修订</h2><pre>'+escape(json.dumps(corrections,ensure_ascii=False,indent=2))+'</pre>',
                 '<h2>最终分工（新测试正文不展示）</h2><pre>'+escape(json.dumps(split,ensure_ascii=False,indent=2))+'</pre>',
                 '<h2>边界</h2><ul>']+['<li>'+escape(n)+'</li>' for n in result['limitations']]+['</ul>']
    (OUT/'index.html').write_text('\n'.join(sections),encoding='utf-8')
    print('SHELL CLUSTERS:',len(groups),'verified:',all(g['shell_verified'] for g in groups))
    print('SEALED TEST ELIGIBLE:',counts)
    print('UNIT 3.1:',result['status'],'; split:',split['status'])
    print(OUT/'index.html')


if __name__=='__main__':
    parser=argparse.ArgumentParser()
    parser.add_argument('--collect',action='store_true')
    args=parser.parse_args()
    if args.collect:
        collect()
    replay()
