"""Project 2: single-agent code generation loop (offline mock or DashScope adapter).

The offline mode is deterministic and proves the information flow; it does not
claim to be a Qwen call. Generated candidates are checked before execution.
"""
from __future__ import annotations
import argparse, hashlib, json, os, time, urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent

def sha(path): return hashlib.sha256(Path(path).read_bytes()).hexdigest()

def load_task(path):
    task=json.loads(Path(path).read_text(encoding='utf8'))
    for item in task['pages']:
        p=ROOT/item['path']; item['sha256_actual']=sha(p)
        if item['sha256'] != item['sha256_actual']: raise ValueError(f"snapshot changed: {p}")
    return task

def mock_generate(task):
    # The model adapter returns code, as a real provider would. It intentionally
    # starts with the reviewed v1 candidate so the repair step is observable.
    return (ROOT/'learning/generated/sina_v1.py').read_text(encoding='utf8')

def mock_repair(source, feedback):
    if feedback.get('kind') == 'quality_feedback':
        return (ROOT/'learning/generated/sina_v2.py').read_text(encoding='utf8')
    return source

def dashscope_generate(prompt, repair=False, previous_code=''):
    key=os.environ.get('DASHSCOPE_API_KEY')
    if not key: raise RuntimeError('DASHSCOPE_API_KEY is required for --provider dashscope')
    model=os.environ.get('PROJECT2_MODEL','qwen-plus')
    if repair:
        prompt = prompt + '\n\nPrevious candidate source:\n' + previous_code
    endpoint=os.environ.get('QWEN_BASE_URL','https://dashscope.aliyuncs.com/compatible-mode/v1/chat/completions')
    body={'model':model,'temperature':0,'messages':[{'role':'system','content':'Return only Python source defining extract(bytes). Use lxml only; do not perform I/O.'},{'role':'user','content':prompt}]}
    req=urllib.request.Request(endpoint,data=json.dumps(body,ensure_ascii=False).encode('utf8'),headers={'Authorization':'Bearer '+key,'Content-Type':'application/json'})
    with urllib.request.urlopen(req,timeout=60) as response:
        payload=json.loads(response.read().decode('utf8'))
    # DashScope may return fenced Markdown even when source was requested.
    content=payload['choices'][0]['message']['content']
    fence=chr(96)*3
    if fence in content:
        parts=content.split(fence)
        content=parts[1]
        if content.lstrip().startswith('python'):
            content=content.lstrip()[6:]
    if getattr(response,'status_code',200) != 200: raise RuntimeError(str(response))
    return content.strip(), payload.get('usage', {})

def execute_candidate(source, data):
    # Reuse the existing reviewed AST and subprocess boundary. This is a
    # capability check plus timeout boundary, not an OS sandbox for attackers.
    from learning.run_cluster_generation import execute, validate
    result=execute(source, data, timeout=8)
    validate(result, data, allow_production_credit=True)
    return result

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument('--task',default='config/project2_task.json')
    ap.add_argument('--provider',choices=['mock','dashscope'],default='mock')
    ap.add_argument('--output',default='output/project2/run')
    ap.add_argument('--max-rounds',type=int,default=2)
    args=ap.parse_args()
    if args.max_rounds < 0 or args.max_rounds > 5: raise SystemExit('--max-rounds must be 0..5')
    task=load_task(ROOT/args.task); out=ROOT/args.output; out.mkdir(parents=True,exist_ok=True)
    trace={'schema_version':1,'provider':args.provider,'model':os.environ.get('PROJECT2_MODEL','mock-sina-v1'),
           'task_id':task['task_id'],'max_rounds':args.max_rounds,'api_calls':0,'rounds':[],
           'input_pages':[dict(id=x['id'],role=x['role'],path=x['path'],sha256=x['sha256']) for x in task['pages']],
           'semantic_accuracy':'unknown','unseen_evaluation':False,
           'holdout_policy':'final_holdout is executed only after the repair loop; its result is never fed back.'}
    prompt=task['prompt']; started=time.perf_counter()
    if args.provider=='mock': source=mock_generate(task); usage={}
    else:
        page_context='\n\n'.join(f"SOURCE {x['id']} ({x['path']}):\n{(ROOT/x['path']).read_text(encoding='utf8',errors='replace')[:120000]}" for x in task['pages'] if x['role'] != 'final_holdout')
        source, usage=dashscope_generate(prompt+'\n\n'+page_context)
    trace['api_calls'] += args.provider=='dashscope'; trace['usage']=[usage]
    for round_no in range(args.max_rounds+1):
        candidate_path=out/f'candidate_round_{round_no}.py'; candidate_path.write_text(source,encoding='utf8')
        page_results=[]; errors=[]
        # Only generation and development pages may influence repairs.
        for item in task['pages']:
            if item['role'] == 'final_holdout':
                continue
            try:
                result=execute_candidate(source,(ROOT/item['path']).read_bytes())
                page_results.append({'id':item['id'],'status':'pass','blocks':len(result['blocks']),'metadata':len(result['metadata']),'excluded':len(result['excluded'])})
            except Exception as exc: errors.append({'id':item['id'],'error':type(exc).__name__+': '+str(exc)})
        trace['rounds'].append({'round':round_no,'candidate':candidate_path.name,'candidate_sha256':sha(candidate_path),'pages':page_results,'errors':errors})
        if not errors and round_no == 0:
            # A quality issue can still trigger a repair; this is deliberately
            # explicit rather than pretending contract success proves semantics.
            feedback={'kind':'quality_feedback','message':'Review the first direct byline and preserve all narrative blocks.'}
            if args.max_rounds and args.provider=='mock': source=mock_repair(source,feedback); trace['feedback']=feedback; continue
            break
        if not errors: break
        if round_no >= args.max_rounds: break
        feedback={'kind':'execution_feedback','errors':errors}; trace['feedback']=feedback
        if args.provider=='mock': source=mock_repair(source,feedback); usage={}
        else: source, usage=dashscope_generate(json.dumps(feedback,ensure_ascii=False),repair=True,previous_code=source)
        trace['api_calls'] += args.provider=='dashscope'; trace['usage'].append(usage)
    # Freeze the final candidate, then execute holdout once without feedback.
    holdout=[]
    for item in task['pages']:
        if item['role'] != 'final_holdout': continue
        try:
            result=execute_candidate(source,(ROOT/item['path']).read_bytes())
            holdout.append({'id':item['id'],'status':'pass','blocks':len(result['blocks']),'metadata':len(result['metadata']),'excluded':len(result['excluded'])})
        except Exception as exc:
            holdout.append({'id':item['id'],'status':'failed','error':type(exc).__name__+': '+str(exc)})
    trace['holdout']=holdout; trace['elapsed_seconds']=round(time.perf_counter()-started,4); trace['final_candidate']=trace['rounds'][-1]['candidate']
    trace['final_status']='pass' if not trace['rounds'][-1]['errors'] and all(x.get('status')=='pass' for x in holdout) else 'failed'
    (out/'trace.json').write_text(json.dumps(trace,ensure_ascii=False,indent=2),encoding='utf8')
    lines=['<!doctype html><meta charset="utf-8"><title>Project 2 Agent run</title><style>body{font:16px/1.6 sans-serif;max-width:1000px;margin:30px auto}pre{white-space:pre-wrap}table{border-collapse:collapse}td,th{border:1px solid #ccc;padding:6px}</style>',
           '<h1>Project 2: single-agent extraction run</h1>',f"<p>provider={args.provider}; rounds={len(trace['rounds'])}; API calls={trace['api_calls']}; final={trace['final_status']}</p>",
           '<p>Contract and source-evidence checks are not semantic accuracy. Mock results prove the loop only.</p>']
    lines.append('<pre>'+json.dumps(trace,ensure_ascii=False,indent=2)+'</pre>'); (out/'index.html').write_text('\n'.join(lines),encoding='utf8')
    print(f"provider={args.provider} rounds={len(trace['rounds'])} api_calls={trace['api_calls']} final={trace['final_status']}")
    print(out/'index.html'); return 0 if trace['final_status']=='pass' else 1

if __name__=='__main__': raise SystemExit(main())
