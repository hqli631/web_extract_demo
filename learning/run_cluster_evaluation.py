"""3.4: freeze before opening held-out inputs; execute without repairing candidates."""
import argparse
import json
import sys
from datetime import datetime, timezone
from html import escape
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from learning.run_cluster_generation import SPLIT, digest, execute, validate

OUT=ROOT/'output/stage3/evaluation'
PROTOCOL=OUT/'evaluation_protocol.json'


def read(path):
    return json.loads(path.read_text(encoding='utf-8'))


def write(path,value):
    path.write_text(json.dumps(value,ensure_ascii=False,indent=2),encoding='utf-8')


def freeze():
    """Only source code/config and split manifest are read, never held-out HTML."""
    split=read(SPLIT)
    repair=read(ROOT/'output/stage3/repair/repair_record.json')
    if digest(SPLIT.read_bytes())!=repair['split_sha256']:
        raise ValueError('split changed')
    files=['learning/generated/sina_v2.py','learning/generated/chinanews_v2.py',
           'config/body_quality_rubric.json','learning/run_cluster_generation.py']
    value={'unit':'3.4','version':1,'split_sha256':digest(SPLIT.read_bytes()),
           'frozen_files':{f:digest((ROOT/f).read_bytes()) for f in files},
           'candidates':{c['cluster_id']:f"learning/generated/{c['cluster_id'].split('_')[0]}_v2.py" for c in split['clusters']},
           'test_files':[f for c in split['clusters'] for f in c['test']],
           'quality_scope':'static saved article DOM only; unknown for unsupported or ambiguous source evidence; not live rendered completeness or OCR',
           'body_policy':'retain narrative, interview questions, subheadings, informative lists/tables/captions in document order; author/source/editor/production credits separate; page navigation/promotions excluded; do not drop static folded body solely due to visibility',
           'review_method':'current conversation AI full static article DOM inventory versus candidate; cite XPath and text per question; no independent human gold, no API, no calibrated judge',
           'review_fields':['Q1','Q2','Q3','Q4','Q5'],
           'answers':['yes','no','unknown'],
           'scoring':{'yes':1,'no':-1,'normalization':'(raw+5)/10','unknown_score':None,'threshold':0.9,'critical':['Q2','Q3']},
           'execution_failure':'separate execution/contract error, never silently drop failed page or treat as judge no',
           'no_retuning':'do not modify v2 after first held-out execution; findings remain final-test evidence; further tuning requires a new development version and new test set',
           'benchmark':{'repeats':7,'warmups':2,'workers':1,'mode':'in-process trusted extractor CPU body, code loaded once; disk download/model/audit/startup excluded','p95':'nearest rank','quality_not_inferred_from_speed':True},
           'cost':'generation+repair+CPU+audit; API0 does not imply conversation reasoning free; unavailable costs null; scenarios explicitly assumed, no measured GPU savings'}
    OUT.mkdir(parents=True,exist_ok=True)
    if PROTOCOL.exists():
        old=read(PROTOCOL)
        if {k:v for k,v in old.items() if k!='frozen_at_utc'}!=value:
            raise ValueError('frozen evaluation protocol changed')
    else:
        value['frozen_at_utc']=datetime.now(timezone.utc).isoformat()
        write(PROTOCOL,value)
    print('FROZEN: v2 candidates + rubric + test assignments; held-out HTML not read')
    print(PROTOCOL)


def verify():
    p=read(PROTOCOL)
    if digest(SPLIT.read_bytes())!=p['split_sha256']:
        raise ValueError('split changed')
    for file,sha in p['frozen_files'].items():
        if digest((ROOT/file).read_bytes())!=sha:
            raise ValueError('frozen file changed: '+file)
    return p,read(SPLIT)


def run():
    p,split=verify()
    pages=[]
    cases=[]
    for c in split['clusters']:
        source=(ROOT/p['candidates'][c['cluster_id']]).read_text(encoding='utf-8')
        for file in c['test']:
            data=(ROOT/file).read_bytes()
            if digest(data)!=c['snapshot_sha256'][file]:
                raise ValueError('held-out snapshot changed: '+file)
            page={'cluster_id':c['cluster_id'],'file':file,'source_sha256':digest(data),
                  'candidate_sha256':p['frozen_files'][p['candidates'][c['cluster_id']]],
                  'input_bytes':len(data),'quality':'pending'}
            try:
                output=execute(source,data)
                page['output']=output
                validate(output,data,allow_production_credit=True)
                page['execution']='pass'
            except Exception as exc:
                page['execution']='error'
                page['error']=str(exc)
            pages.append(page)
            cases.append(dict(cluster_id=c['cluster_id'],file=file,data=data,source=source))
            print(f"{c['cluster_id']} {Path(file).name}: execution={page['execution']}; blocks={len(page.get('output',{}).get('blocks',[]))}; semantic review pending")
    value={'protocol_sha256':digest(PROTOCOL.read_bytes()),'pages':pages,
           'limits':'held-out relative to current frozen split; same dialogue context, not independent reviewer or broad-web accuracy'}
    path=OUT/'results.json'
    if path.exists() and read(path)!=value:
        raise ValueError('held-out replay changed; do not overwrite')
    write(path,value)
    from learning.benchmark_cluster_cpu import benchmark
    # Runtime measurements vary; retain first run rather than replacing it on replay.
    if (OUT/'benchmark.json').exists() and read(OUT/'benchmark.json')['cases_per_batch']!=len(cases):
        previous=OUT/'benchmark_success_subset.json'
        if previous.exists():
            raise ValueError('benchmark case set changed again')
        (OUT/'benchmark.json').rename(previous)
    if not (OUT/'benchmark.json').exists():
        write(OUT/'benchmark.json',benchmark(cases,repeats=p['benchmark']['repeats'],warmups=p['benchmark']['warmups']))
    write_cost()
    render()


def write_cost():
    from learning.benchmark_cluster_cpu import cost_scenario
    b=read(OUT/'benchmark.json')
    cpu=b['summary']['batch_cpu_seconds_total']/b['summary']['attempts']
    value={'measured':{'model_api_calls':0,'conversation_generation_repair_cost':None,
                       'conversation_audit_cost':None,'reason':'No recorded chat bill/token accounting; zero API calls does not mean total cost zero',
                       'cpu_seconds_per_attempt':cpu,'benchmark_cases':b['cases_per_batch']},
           'formula':'(G + N*c + J)/N',
           'assumptions':{'currency':'illustrative units, not a quote','G_generation_repair':10,
                          'CPU_process_hour_price':1,'J_fixed_audit_total':2,
                          'important':'Fixed J is assumed. If each page needs review at cost j, J=N*j; that term does not amortize away.'},
           'scenarios':[cost_scenario(n,10,cpu,1,2) for n in [12,1000,100000]],
           'limits':['No measured GPU/per-page model baseline or empirical savings multiple',
                     'Windows process CPU timer is coarse; batch totals preferable to per-page CPU timing',
                     'Small warm-memory single-worker batch, no trillion-page extrapolation',
                     'Exploratory 11-page benchmark retained as benchmark_success_subset.json; benchmark.json includes all 12 attempts. Returning a dict does not mean contract/quality pass.']}
    write(OUT/'cost.json',value)


def render():
    result=read(OUT/'results.json')
    review_path=OUT/'reviews.json'
    reviews=read(review_path) if review_path.exists() else {'pages':[]}
    lookup={r['file']:r for r in reviews['pages']}
    scored=[]
    for page in result['pages']:
        review=lookup.get(page['file'])
        score=None
        status='pending'
        if page['execution']!='pass':
            status='execution_error'
        elif review:
            if review['source_sha256']!=page['source_sha256'] or review['candidate_sha256']!=page['candidate_sha256']:
                raise ValueError('stale review')
            answers=review['answers']
            if set(answers)!={'Q1','Q2','Q3','Q4','Q5'}:
                raise ValueError('missing rubric answer')
            if any(a['answer'] not in {'yes','no','unknown'} or not a['evidence'] for a in answers.values()):
                raise ValueError('invalid review answer/evidence')
            if any(a['answer']=='unknown' for a in answers.values()):
                status='unknown'
            else:
                score=(sum(1 if a['answer']=='yes' else -1 for a in answers.values())+5)/10
                status='candidate_pass' if score>=0.9 and all(answers[q]['answer']=='yes' for q in ['Q2','Q3']) else 'quality_fail'
        scored.append({'file':page['file'],'execution':page['execution'],'status':status,'score':score})
    summary={'protocol_sha256':result['protocol_sha256'],'pages':scored,
             'counts':{k:sum(r['status']==k for r in scored) for k in ['candidate_pass','quality_fail','unknown','pending','execution_error']},
             'interpretation':'current-chat static task judgments, not human-calibrated accuracy; live/image gaps separate'}
    write(OUT/'summary.json',summary)
    parts=['<!doctype html><meta charset="utf-8"><title>3.4 封存评估与CPU成本</title>',
           '<style>body{font:16px/1.8 sans-serif;max-width:1150px;margin:30px auto}pre{white-space:pre-wrap}table{border-collapse:collapse}td,th{border:1px solid #ccc;padding:8px}details{margin:15px 0}</style>',
           '<h1>3.4 封存评估与CPU成本</h1><p>先冻结，再首次执行12篇封存页。静态DOM范围；当前对话AI评审，不是独立人工准确率。候选代码未根据测试页修改。</p>',
           '<h2>汇总</h2><pre>'+escape(json.dumps(summary,ensure_ascii=False,indent=2))+'</pre>']
    for page in result['pages']:
        parts+=['<details><summary>'+escape(page['cluster_id']+' / '+Path(page['file']).name+' / '+page.get('output',{}).get('title','执行失败'))+'</summary>',
                '<p><a href="../../../'+escape(page['file'],quote=True)+'">源快照（资源未必完整）</a>；原始执行记录quality=pending表示当时尚未语义评审，最终结论以汇总及下方评审为准。</p>',
                '<h3>评审理由</h3><pre>'+escape(json.dumps(lookup.get(page['file'],{'status':'pending'}),ensure_ascii=False,indent=2))+'</pre>',
                '<h3>完整抽取输出</h3><pre>'+escape(json.dumps(page,ensure_ascii=False,indent=2))+'</pre></details>']
    parts+=['<h2>CPU主体计时</h2><pre>'+escape((OUT/'benchmark.json').read_text(encoding='utf-8'))+'</pre>']
    if (OUT/'cost.json').exists():
        parts+=['<h2>成本口径与假设</h2><pre>'+escape((OUT/'cost.json').read_text(encoding='utf-8'))+'</pre>']
    (OUT/'index.html').write_text('\n'.join(parts),encoding='utf-8')
    print(json.dumps(summary['counts'],ensure_ascii=False))
    print(OUT/'index.html')


if __name__=='__main__':
    parser=argparse.ArgumentParser()
    parser.add_argument('--freeze',action='store_true')
    parser.add_argument('--render',action='store_true')
    args=parser.parse_args()
    if args.freeze:
        freeze()
    elif args.render:
        verify()
        render()
    else:
        run()
