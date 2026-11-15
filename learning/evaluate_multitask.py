"""Frozen base/adapter/reference comparison; unknown code only in OS isolation."""
import argparse, ast, hashlib, json, sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'output/stage5/multitask'
def read(path):return json.loads(Path(path).read_text(encoding='utf8'))
def write(path,obj):
    path.parent.mkdir(parents=True,exist_ok=True)
    path.write_text(json.dumps(obj,ensure_ascii=False,indent=2)+'\n',encoding='utf8')
def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()
def source_only(text):
    text=text.strip();fence=chr(96)*3
    if text.startswith(fence):
        lines=text.splitlines()
        if lines[-1].strip()!=fence:raise ValueError('incomplete markdown fence')
        return '\n'.join(lines[1:-1]),True
    return text,False
def gate(code):
    """Policy gate only; bubblewrap remains mandatory."""
    tree=ast.parse(code)
    functions=[n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name=='extract']
    if len(functions)!=1 or len(functions[0].args.args)!=1:raise ValueError('extract(data) missing')
    for n in ast.walk(tree):
        if isinstance(n,ast.Import) and any(a.name not in {'re','lxml','lxml.html','lxml.etree'} for a in n.names):raise ValueError('unsupported import')
        if isinstance(n,ast.ImportFrom) and n.module not in {'re','lxml','lxml.html','lxml.etree'}:raise ValueError('unsupported import')
        if isinstance(n,ast.Name) and n.id in {'exec','eval','open','compile','__import__','breakpoint','input'}:raise ValueError('unsupported builtin')
        if isinstance(n,ast.Attribute) and n.attr.startswith('__'):raise ValueError('dunder attribute')
    return True
def prepare(capacity_file):
    manifest=read(OUT/'natural_tasks.json');jobs=[]
    runs={'base':read(OUT/'before_generation.json'),'lora40':read(OUT/'after_generation.json'),'lora120':read(capacity_file)}
    for name,data in runs.items():
        for row in data['outputs']:
            task=(row.get('task_id') or '').removeprefix('natural-')
            if not task.endswith('_v1'):continue
            dest=OUT/'candidates'/name/(task+'.py')
            info=dict(task_id=task,model=name,raw_sha256=hashlib.sha256(row['text'].encode()).hexdigest(),generation_truncated=row['may_be_truncated'])
            try:
                code,normalized=source_only(row['text']);gate(code)
                dest.parent.mkdir(parents=True,exist_ok=True);dest.write_text(code,encoding='utf8',newline='\n')
                info.update(candidate=dest.relative_to(ROOT).as_posix(),candidate_sha256=sha(dest),format_fence_removed=normalized,static_gate='pass')
            except (ValueError,SyntaxError) as e:info.update(static_gate='reject',error=str(e))
            jobs.append(info)
    for cluster in manifest['clusters']:
        target=cluster['target_code']
        jobs.append(dict(task_id=cluster['task_id'],model='reviewed_reference',candidate=target['path'],candidate_sha256=target['sha256'],static_gate='pass',format_fence_removed=False,generation_truncated=False))
    plan=dict(version=1,selected_model='lora120',selection='Capacity follow-up fixed before opening sealed test DOM; no further tuning.',
              evaluation_protocol='dev: all 4 methods; once-only test: base/lora120/reference; lora40 test excluded',
              jobs=jobs,clusters=manifest['clusters'],test_use='final_only_no_repair_on_test',semantic_gold=False)
    target=OUT/'evaluation_plan.json'
    if target.exists() and read(target)!=plan:raise ValueError('frozen evaluation plan exists')
    write(target,plan);print('PREPARED',len(jobs),'candidate gates; test content not inspected')
def validate_result(result,raw):
    from lxml import html
    issues=[]
    if not isinstance(result,dict) or set(result)!= {'title','blocks','metadata','excluded','warnings'}:return ['top_level_contract']
    if not isinstance(result['title'],str) or not result['title'].strip():issues.append('empty_or_invalid_title')
    for key in ['blocks','metadata','excluded','warnings']:
        if not isinstance(result[key],list):issues.append(key+'_not_list')
    if issues:return issues
    if not result['blocks']:issues.append('empty_body')
    if any(not isinstance(w,str) for w in result['warnings']):issues.append('warning_not_string')
    tree=html.document_fromstring(raw);order={n:i for i,n in enumerate(tree.iter())};last=-1
    for key in ['blocks','metadata','excluded']:
        for block in result[key]:
            if not isinstance(block,dict) or not all(isinstance(block.get(k),str) and block[k] for k in ['kind','text','xpath']):
                issues.append(key+'_entry_contract');continue
            if key=='blocks' and block['kind'] not in {'paragraph','subheading','caption','table'}:issues.append('unsupported_body_kind')
            try:
                matches=tree.xpath(block['xpath'])
                if len(matches)!=1 or not hasattr(matches[0],'text_content'):issues.append('xpath_not_unique_element');continue
                text=' '.join(matches[0].text_content().replace('¶','').split())
                if ' '.join(block['text'].split()) not in text:issues.append('text_not_in_xpath_source')
                if key=='blocks':
                    current=order[matches[0]]
                    if current<last:issues.append('body_order_changed')
                    last=current
                if block['kind']=='table' and not isinstance(block.get('rows'),list):issues.append('table_rows_missing')
            except Exception as e:issues.append('invalid_xpath:'+type(e).__name__)
    return sorted(set(issues))
def run(deps):
    sys.path.insert(0,str(ROOT));sys.path.insert(0,str(deps))
    from training.isolate_extract import run as isolated
    plan=read(OUT/'evaluation_plan.json');reports=[]
    evidence=OUT/'evaluation';evidence.mkdir(parents=True,exist_ok=True)
    receipt=OUT/'test_exposure.json'
    if receipt.exists():raise ValueError('sealed evaluation already performed; use saved report')
    write(receipt,dict(status='final_evaluation_started',plan_sha256=sha(OUT/'evaluation_plan.json'),pages=[p for c in plan['clusters'] for p in c['pages'] if p['role']=='test'],forbidden_to_reuse_as_unseen=True))
    for cluster in plan['clusters']:
        for page in cluster['pages']:
            if page['role'] not in {'dev','test'}:continue
            source=ROOT/page['path']
            if sha(source)!=page['sha256']:raise ValueError('source snapshot changed')
            for job in plan['jobs']:
                if job['task_id']!=cluster['task_id']:continue
                if page['role']=='test' and job['model']=='lora40':continue
                record=dict(task_id=job['task_id'],model=job['model'],role=page['role'],source=page,static_gate=job['static_gate'])
                if job['static_gate']=='reject':record.update(status='static_reject',error=job['error'],contract_pass=False)
                else:
                    candidate=ROOT/job['candidate']
                    if sha(candidate)!=job['candidate_sha256']:raise ValueError('candidate changed')
                    outcome=isolated(candidate,source,deps);record.update(outcome)
                    if outcome['status']=='success':record.update(contract_pass=not validate_result(outcome['result'],source.read_bytes()),issues=validate_result(outcome['result'],source.read_bytes()))
                    else:record['contract_pass']=False
                reports.append(record);print(job['model'],page['role'],job['task_id'],record['status'],record['contract_pass'],flush=True)
    for record in reports:
        ref=next((r.get('result') for r in reports if r['task_id']==record['task_id'] and r['role']==record['role'] and r['model']=='reviewed_reference' and r['status']=='success'),None)
        if record['contract_pass'] and ref:
            result=record['result'];body=[b['text'] for b in result['blocks']];expected=[b['text'] for b in ref['blocks']]
            record.update(reference_exact=result==ref,title_matches_reference=result['title']==ref['title'],reference_block_text_recall=sum(t in body for t in expected)/len(expected),reference_block_text_precision=sum(t in expected for t in body)/len(body),semantic_quality='unknown_without_independent_natural_gold')
    report=dict(records=reports,protocol=plan['evaluation_protocol'],selected_model=plan['selected_model'],
        sandbox=dict(implementation='Linux bubblewrap+prlimit',network='unshared',uid=65534,inputs='read_only',host_home='not_mounted',limits='8 CPU seconds,15 wall seconds,1GiB address space,2MiB output,64 fds,32 nproc requested',kernel_boundary='not protection against kernel vulnerabilities'),
        interpretation='Reference agreement is not semantic accuracy. Three layouts trained: test is new pages within known layouts only.')
    write(evidence/'results.json',report)
    write(receipt,{**read(receipt),'status':'final_evaluation_complete','results_sha256':sha(evidence/'results.json')})
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('mode',choices=['prepare','run']);p.add_argument('--capacity-file',default=str(OUT/'capacity_after_generation.json'));p.add_argument('--deps')
    a=p.parse_args();prepare(a.capacity_file) if a.mode=='prepare' else run(a.deps)
