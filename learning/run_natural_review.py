"""Replay saved natural-page review, preserving the Stage 3 frozen results."""
import argparse
import hashlib
import json
import sys
from html import escape
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from learning.prepare_natural_review import OUT, read, save
from learning.agent_io.review_pipeline import digest
from learning.agent_io.score_body_quality import score_case

QUESTIONS=['Q1','Q2','Q3','Q4','Q5']

def expand_saved_notes(task,notes):
    """Serialize already-written AI decisions, never infer from historic labels."""
    if set(notes.get('cases',{})) != {c['case_id'] for c in task['cases']}:
        raise ValueError('Notes cases mismatch')
    response={'task_id':task['task_id'],'task_sha256':digest(task),
              'reviewer':notes['reviewer'],'origin':notes['origin'],
              'independent_context':False,'cases':[]}
    for case in task['cases']:
        src={r['id']:r['text'] for r in task['sources'][case['source_id']]['records']}
        dst={r['id']:r['text'] for r in case['output']}
        case_notes=notes['cases'][case['case_id']]
        if len(case_notes)!=5:
            raise ValueError('Five questions required')
        answers=[]
        for qid,entry in zip(QUESTIONS,case_notes):
            verdict,reason,srefs,orefs=entry
            answers.append({'id':qid,'verdict':verdict,'reason':reason,
                            'source_evidence':[{'id':key,'quote':src[key]} for key in srefs],
                            'output_evidence':[{'id':key,'quote':dst[key]} for key in orefs]})
        response['cases'].append({'task_id':task['task_id'],'case_id':case['case_id'],'answers':answers})
    return response

def assess(task,response):
    if response.get('task_id')!=task['task_id'] or response.get('task_sha256')!=digest(task):
        raise ValueError('Response refers to a different task')
    if [c.get('case_id') for c in response.get('cases',[])]!=[c['case_id'] for c in task['cases']]:
        raise ValueError('Missing/duplicate/reordered response case')
    return [score_case(task,c,r) for c,r in zip(task['cases'],response['cases'])]

def source_links(file):
    path=Path(file)
    site=path.parent.name
    name=path.stem
    selection=read(ROOT/path.parent/'selection.json')
    original=selection['urls'][int(name.split('_')[1])-1]
    display=ROOT/'output/stage3/display'/site/name/(name+'.html')
    relative='../../stage3/display/'+site+'/'+name+'/'+name+'.html'
    return original,relative if display.exists() else None

def feedback_cards(task):
    # Two finite semantic decisions for the learner, not bulk reannotation.
    return [
      {'id':'D1','case_id':'natural_01','quote':'原标题：“9月启动开门红，10月已进入考核期”：银行业2027年“开门红”没有统一的“开门”时间，首季战役正变成全年连轴',
       'question':'在主标题已单列的任务中，这条“原标题”保留在正文，还是移入original_title元数据？请说明你的任务规范。',
       'current_proposal':'separate_as_metadata_original_title',
       'why':'Q4已有独立署名污染，旧no不变；该决策补齐下一版分类规范，不能直接静默重写旧分数。',
       'user_status':'pending','user_answer':None},
      {'id':'D2','case_id':'natural_01','quote':'华夏银行太原分行公众号截图',
       'question':'这条图说文字已保留，但kind=paragraph。应说“图说漏提”，还是“信息保留、类型不够精确”？',
       'current_proposal':'information_present_type_inexact',
       'why':'当前Q3主评信息及关系保留，未要求图说kind绝对准确。若增加类型准确率，应版本化新增诊断，不能为此把旧Q3改no。',
       'user_status':'pending','user_answer':None}]

def run():
    task=read(OUT/'task.json')
    response=read(OUT/'review_response.json')
    for source in task['sources'].values():
        if hashlib.sha256((ROOT/source['file']).read_bytes()).hexdigest()!=source['snapshot_sha256']:
            raise ValueError('Frozen source changed')
    rows=assess(task,response)
    historic=read(ROOT/'output/stage3/evaluation/reviews.json')
    old={p['file']:p for p in historic['pages']}
    agreements=0
    valid_questions=0
    transitions={q:{a:{b:0 for b in ['yes','no','unknown']} for a in ['yes','no','unknown']} for q in QUESTIONS}
    for case,row in zip(task['cases'],rows):
        file=task['sources'][case['source_id']]['file']
        row['file']=file
        row['historic_verdicts']={q:old[file]['answers'][q]['answer'] for q in QUESTIONS}
        if row['response_valid']:
            for a in row['answers']:
                previous=row['historic_verdicts'][a['id']]
                transitions[a['id']][previous][a['verdict']]+=1
                agreements+=previous==a['verdict']
                valid_questions+=1
    summary={'pages':len(rows),'protocol_valid_pages':sum(r['response_valid'] for r in rows),
             'protocol_invalid_pages':sum(not r['response_valid'] for r in rows),
             'valid_questions':valid_questions,
             'historical_agreement':agreements/valid_questions if valid_questions else None,
             'unknown_answers':sum(a['verdict']=='unknown' for r in rows if r['response_valid'] for a in r['answers']),
             'unknown_rate':sum(a['verdict']=='unknown' for r in rows if r['response_valid'] for a in r['answers'])/valid_questions if valid_questions else None,
             'historic_to_current_transitions':transitions,
             'independent_review_completed':False,'independent_human_accuracy':None,
             'same_context_recheck':True,'new_held_out_pages':0,'model_api_calls_during_replay':0,
             'api_cost':None,'training_updates':0,
             'limits':'Historical purposive re-review with previous conclusions known. Agreement is not accuracy or independent repeatability. Static article text only, image pixels not judged; no general web guarantee.',
             'next_required':'Resolve two small user policy decisions; separate-context or independent-human audit still pending.'}
    result={'task_sha256':digest(task),'response_sha256':digest(response),'summary':summary,'pages':rows}
    save(OUT/'result.json',result)
    cards=feedback_cards(task)
    save(OUT/'learner_decisions.json',cards)
    parts=['<!doctype html><html lang=zh-CN><meta charset=utf-8><title>真实网页质量复核</title>',
           '<style>body{font:16px/1.7 system-ui;max-width:1150px;margin:32px auto;padding:16px}table{border-collapse:collapse;width:100%}td,th{border:1px solid #ddd;padding:9px}pre{white-space:pre-wrap;overflow-wrap:anywhere}.note{background:#fff5d6;padding:12px}details{margin:12px 0}</style>',
           '<h1>四篇真实网页：核对质量判断与证据</h1>',
           '<p class=note>这是同一对话对历史网页的重新核对，不是独立盲评或新测试。隔离子任务收到空消息，没有评审输出；独立校准仍待完成。原快照、抽取器v2和第三阶段分数均未改。</p>',
           '<p>静态正文文字与图片内信息分开。新闻中的普通配图不自动导致unknown；只有导语、主要信息可能在图片中的页面不能确认完整性。源/输出清单是证据视图，原布局请打开“缓存展示副本”。</p>',
           '<table><tr><th>案例与网页</th><th>历史五题</th><th>本次五题</th><th>分数/路由</th></tr>']
    for case,row in zip(task['cases'],rows):
        url,display=source_links(row['file'])
        links='<a href="'+escape(url,quote=True)+'">原站（可能更新）</a>'
        if display: links+=' / <a href="'+escape(display,quote=True)+'">缓存展示副本</a>'
        parts.append('<tr><td>'+case['case_id']+'<br>'+escape(case['output'][0]['text'])+'<br>'+links+'</td><td>'+' / '.join(row['historic_verdicts'].values())+'</td><td>'+' / '.join(a['verdict'] for a in row['answers'])+'</td><td>'+str(row['score'])+'<br>'+row['adoption']+'</td></tr>')
    confirmed_path=ROOT/'output/stage4/policy_v2/confirmed_decisions.json'
    confirmed=read(confirmed_path) if confirmed_path.exists() else None
    if confirmed:
        parts.append('</table><h2>D1/D2已收到用户确认</h2><p>以下卡片保留确认前的历史问题。当前已确认：原标题单列元数据，图说先保文字和顺序，再细化caption。<a href="../policy_v2/index.html">查看规范应用前后对照</a> / <a href="../policy_v2/confirmed_decisions.json">用户确认原话</a>。旧评审分数保持不变。</p>')
    else:
        parts.append('</table><h2>两个待你判断的规范点</h2><p>只需在对话回复D1/D2及理由，不用手改JSON。未收到反馈前，文件中的user_answer保持null，提议不冒充你的确认。</p>')
    for card in cards:
        parts.append('<div class=note><b>'+card['id']+'</b><p>'+escape(card['quote'])+'</p><p>'+escape(card['question'])+'</p><p>'+escape(card['why'])+'</p></div>')
    parts.append('<h2>逐题理由和证据</h2>')
    for row in rows:
        parts.append('<details><summary>'+row['case_id']+'</summary>')
        for a in row['answers']:
            parts.append('<details><summary>'+a['id']+' '+a['verdict']+'</summary><p>'+escape(a['reason'])+'</p><pre>'+escape(json.dumps({'source_evidence':a['source_evidence'],'output_evidence':a['output_evidence']},ensure_ascii=False,indent=2))+'</pre></details>')
        parts.append('</details>')
    parts.append('<h2>统计及边界</h2><pre>'+escape(json.dumps(summary,ensure_ascii=False,indent=2))+'</pre>')
    parts.append('<p><a href=task.json>完整源/候选证据</a> · <a href=review_response.json>保存的AI判断</a> · <a href=result.json>核验与比较</a> · <a href=learner_decisions.json>待确认规范</a></p></html>')
    (OUT/'index.html').write_text('\n'.join(parts),encoding='utf-8',newline='\n')
    for row in rows:
        print(f"{row['case_id']}: valid={row['response_valid']} score={row['score']}; {row['adoption']}")
    print('REVIEW: historical current-context recheck; independent calibration=PENDING; user decisions='+('2 confirmed (see policy_v2)' if confirmed else '2 pending'))
    print(OUT/'index.html')
    if not all(r['response_valid'] for r in rows): raise SystemExit(1)

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--serialize-saved-notes',action='store_true')
    args=p.parse_args()
    if args.serialize_saved_notes:
        save(OUT/'review_response.json',expand_saved_notes(read(OUT/'task.json'),read(OUT/'review_notes.json')))
        print('Serialized existing AI judgments; no inference or expected-label lookup')
    else:
        run()
