"""Apply confirmed policy to historical candidates; no old output or score edits."""
import copy
import json
import hashlib
import re
import sys
from collections import Counter
from html import escape
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from lxml import html
from learning.agent_io.review_pipeline import digest

OUT=ROOT/'output/stage4/policy_v2'
NATURAL=ROOT/'output/stage4/natural_review'

def read(path):
    return json.loads(path.read_text(encoding='utf-8'))

def write_frozen(path,value):
    path.parent.mkdir(parents=True,exist_ok=True)
    if path.exists() and read(path)!=value:
        raise ValueError('Frozen policy record differs; create a new version: '+str(path))
    path.write_text(json.dumps(value,ensure_ascii=False,indent=2),encoding='utf-8',newline='\n')

def normalized(node):
    return ' '.join(node.text_content().split())

def caption_evidence(tree,block):
    """A caption node/class with matching text, not a caption keyword heuristic."""
    nodes=tree.xpath(block['xpath'])
    if len(nodes)!=1 or normalized(nodes[0])!=block['text']:
        return None
    node=nodes[0]
    classes=set((node.get('class') or '').split())
    direct=node.tag=='figcaption' or bool(classes & {'pictext','img_descr'})
    if direct:
        return tree.getroottree().getpath(node)
    if 'img_wrapper' not in classes or not node.xpath('.//img'):
        return None
    captions=node.xpath('.//*[contains(concat(" ",normalize-space(@class)," ")," img_descr ")]')
    if len(captions)==1 and normalized(captions[0])==block['text']:
        return tree.getroottree().getpath(captions[0])
    return None

def transform(case,tree):
    before=copy.deepcopy(case)
    after=copy.deepcopy(case)
    real=[b for b in case['output'] if b['id'] not in {'title','inventory'}]
    kept=[]
    changes=[]
    metadata=copy.deepcopy(case.get('metadata',[]))
    for position,block in enumerate(real):
        row=copy.deepcopy(block)
        if (position<5 and case['output'][0]['text'].strip() and
                re.match(r'^原标题\s*[:：]\s*\S',row['text'])):
            nodes=tree.xpath(row['xpath'])
            if len(nodes)!=1 or normalized(nodes[0])!=row['text']:
                raise ValueError('Original title evidence mismatch')
            row['kind']='original_title'
            metadata.append(row)
            changes.append({'decision_id':'D1','id':row['id'],'text':row['text'],
                            'xpath':row['xpath'],'action':'body_to_metadata',
                            'old_kind':block['kind'],'new_kind':row['kind']})
            continue
        path=caption_evidence(tree,row)
        if path and row.get('kind')!='caption':
            row['kind']='caption'
            changes.append({'decision_id':'D2','id':row['id'],'text':row['text'],
                            'xpath':row['xpath'],'caption_node_xpath':path,
                            'action':'refine_kind','old_kind':block['kind'],'new_kind':'caption'})
        kept.append(row)
    after['output']=[copy.deepcopy(case['output'][0])]+kept
    after['output'].append({'id':'inventory','text':json.dumps(after['output'],ensure_ascii=False,sort_keys=True)})
    after['metadata']=metadata
    moved=[c['id'] for c in changes if c['action']=='body_to_metadata']
    kept_ids=[r['id'] for r in kept]
    if kept_ids!=[r['id'] for r in real if r['id'] not in moved]:
        raise ValueError('Retained order changed')
    old_records=[(r.get('xpath'),r['text']) for r in real+case.get('metadata',[])]
    new_records=[(r.get('xpath'),r['text']) for r in kept+metadata]
    if Counter(old_records)!=Counter(new_records):
        raise ValueError('Text lost, duplicated or modified')
    for old in real:
        if old['id'] in kept_ids and next(r for r in kept if r['id']==old['id'])['text']!=old['text']:
            raise ValueError('Text changed during type refinement')
    return {'case_id':case['case_id'],'before':before,'after':after,'changes':changes,
            'checks':{'body_plus_metadata_text_preserved':True,'retained_body_order_preserved':True,
                      'caption_text_unchanged':True},
            'new_semantic_score':None,
            'status':'historical_policy_application_preview_not_new_quality_review'}

def run():
    task=read(NATURAL/'task.json')
    policy=read(ROOT/'config/body_policy_v2.json')
    rows=[]
    for case in task['cases']:
        source=task['sources'][case['source_id']]
        data=(ROOT/source['file']).read_bytes()
        if hashlib.sha256(data).hexdigest()!=source['snapshot_sha256']:
            raise ValueError('Source snapshot changed')
        rows.append(transform(case,html.document_fromstring(data)))
    value={'policy_id':policy['policy_id'],'policy_sha256':digest(policy),
           'input_task_sha256':digest(task),'implementation_sha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
           'cases':rows,'model_api_calls':0,'training_updates':0,
           'scope':'Postprocessing preview on historical exposed candidates. Old v2, source snapshots, reviews and scores are not overwritten. No new accuracy or independent calibration claim.'}
    write_frozen(OUT/'application.json',value)
    confirmed={'policy_id':policy['policy_id'],'policy_sha256':digest(policy),
               'origin':'explicit user reply to D1 and D2 in current conversation',
               'decisions':[{'id':d['id'],'user_status':'confirmed','user_answer':d['user_answer']} for d in policy['decisions']]}
    write_frozen(OUT/'confirmed_decisions.json',confirmed)
    from learning.run_natural_review import source_links
    lines=['<!doctype html><html lang=zh-CN><meta charset=utf-8><title>正文规范v2应用对照</title>',
           '<style>body{font:16px/1.7 system-ui;max-width:1100px;margin:30px auto;padding:12px}table{border-collapse:collapse;width:100%}td,th{border:1px solid #ddd;padding:9px}pre{white-space:pre-wrap;overflow-wrap:anywhere}</style>',
           '<h1>用户反馈 → 规范v2 → 可追溯应用对照</h1>',
           '<p>D1已确认原标题单列元数据；D2已确认图说先保文字和顺序，再细化caption。旧learner_decisions.json保留当时待确认状态，当前确认记录在confirmed_decisions.json。</p>',
           '<p>这只是历史候选的规范应用示例，未生成新的质量分，未修改旧v2抽取器或第三阶段分数。署名和评论引导等既有问题仍在，不能因本次改动就称整页修好。</p>']
    for case,row in zip(task['cases'],rows):
        source=task['sources'][case['source_id']]
        url,display=source_links(source['file'])
        lines+=['<h2>'+case['case_id']+' '+escape(case['output'][0]['text'])+'</h2>',
                '<p><a href="'+escape(url,quote=True)+'">原站</a>'+
                (' / <a href="'+escape(display,quote=True)+'">缓存展示副本</a>' if display else '')+'</p>',
                '<table><tr><th>改动</th><th>原文</th><th>前后类型/位置</th></tr>']
        for c in row['changes']:
            lines.append('<tr><td>'+c['decision_id']+' '+c['action']+'</td><td>'+escape(c['text'])+'</td><td>'+c['old_kind']+' → '+c['new_kind']+'</td></tr>')
        if not row['changes']: lines.append('<tr><td colspan=3>无匹配变更，保留原结果。</td></tr>')
        lines.append('</table><p>文本守恒、保留块顺序、图说文字不变：全部通过。new_semantic_score=null。</p>')
        lines.append('<details><summary>完整前后结果与XPath</summary><pre>'+escape(json.dumps(row,ensure_ascii=False,indent=2))+'</pre></details>')
        print(f"{case['case_id']}: moved={sum(c['action']=='body_to_metadata' for c in row['changes'])}; retyped={sum(c['action']=='refine_kind' for c in row['changes'])}; text/order=PASS; new_score=None")
    lines.append('<p><a href=application.json>完整应用记录</a> · <a href=confirmed_decisions.json>用户确认记录</a> · <a href=../natural_review/index.html>历史复核报告</a></p></html>')
    (OUT/'index.html').write_text('\n'.join(lines),encoding='utf-8',newline='\n')
    print('CONFIRMED: D1/D2; independent calibration=PENDING; no training')
    print(OUT/'index.html')

if __name__=='__main__':
    run()
