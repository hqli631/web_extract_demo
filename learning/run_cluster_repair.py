"""3.3: one saved AI repair round, generation regression, no sealed tests."""
import difflib
import json
import sys
from html import escape
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from lxml import html
from learning.run_cluster_generation import execute, validate, digest, SPLIT

OUT=ROOT/'output/stage3/repair'


def load(path):
    return json.loads(path.read_text(encoding='utf-8'))


def source(name,version):
    return (ROOT/f'learning/generated/{name}_v{version}.py').read_text(encoding='utf-8')


def controlled(name, mode):
    """Explicit synthetic fixtures, unrelated to sealed page content."""
    title='main-title' if name=='sina' else 'content_left_title'
    body='id="artibody"' if name=='sina' else 'class="left_zw"'
    if mode=='folded_leaf':
        inner='<div style="display:none">Folded <span>article detail</span> remains.</div>'
    elif mode=='nested_p':
        inner='<section><p>Nested article detail.</p></section>'
    elif mode=='middle_credit':
        inner='<p>｜策划：张三</p><p>正文解释策划过程，不能截断。</p>'
    else:
        raise ValueError(mode)
    return f'<meta charset="utf-8"><h1 class="{title}">Synthetic control</h1><div {body}>{inner}</div>'.encode()


def run():
    split=load(SPLIT)
    generation=load(ROOT/'output/stage3/generation/generation_record.json')
    if split['status']!='frozen' or digest(SPLIT.read_bytes())!=load(ROOT/'output/stage3/generation/task.json')['split_sha256']:
        raise ValueError('split changed')
    if digest((ROOT/'output/stage3/protocol/protocol.json').read_bytes())!=split['protocol_sha256']:
        raise ValueError('protocol changed')
    results=[]
    patches=[]
    for cluster in split['clusters']:
        name=cluster['cluster_id'].split('_')[0]
        old=next(c for c in generation['clusters'] if c['cluster_id']==cluster['cluster_id'])
        if digest((ROOT/old['candidate_file']).read_bytes())!=old['candidate_sha256']:
            raise ValueError('v1 no longer matches generation record')
        before,after=source(name,1),source(name,2)
        patches.append({'cluster_id':cluster['cluster_id'],'before_sha256':old['candidate_sha256'],
                        'after_sha256':digest((ROOT/f'learning/generated/{name}_v2.py').read_bytes()),
                        'diff':''.join(difflib.unified_diff(before.splitlines(True),after.splitlines(True),fromfile=name+'_v1.py',tofile=name+'_v2.py'))})
        for role in ['generation','repair']:
            for file in cluster[role]:
                data=(ROOT/file).read_bytes()
                if digest(data)!=cluster['snapshot_sha256'][file]:
                    raise ValueError('snapshot changed: '+file)
                outputs=[]
                for code in [before,after]:
                    output=execute(code,data)
                    validate(output,data,allow_production_credit=True)
                    outputs.append(output)
                a,b=outputs
                changes=[]
                for record in a['blocks']:
                    matching=[r for r in b['metadata'] if r['xpath']==record['xpath']]
                    if matching:
                        changes.append({'xpath':record['xpath'],'text':record['text'],
                                        'before':'blocks.'+record['kind'],'after':'metadata.'+matching[0]['kind']})
                unchanged=(a==b)
                if role=='generation' and not unchanged:
                    raise ValueError('generation regression: '+file)
                if role=='repair':
                    old_records={r['xpath']:r for r in a['blocks']}
                    moved={r['xpath'] for r in changes}
                    if b['blocks']!=[r for r in a['blocks'] if r['xpath'] not in moved]:
                        raise ValueError('unexpected natural body changes')
                    for moved_record in changes:
                        new_record=next(r for r in b['metadata'] if r['xpath']==moved_record['xpath'])
                        if new_record['text']!=old_records[moved_record['xpath']]['text']:
                            raise ValueError('moved record changed')
                results.append({'file':file,'role':role,'source_sha256':digest(data),
                                'before':a,'after':b,'moved':changes,'exactly_unchanged':unchanged,
                                'contract':'pass','scope':'known development/repair pages, not independent evaluation'})
                print(f"{role} {Path(file).name}: blocks {len(a['blocks'])}->{len(b['blocks'])}; moved={len(changes)}; regression PASS")
    controls=[]
    for name in ['sina','chinanews']:
        for mode in ['folded_leaf','nested_p'] + (['middle_credit'] if name=='chinanews' else []):
            data=controlled(name,mode)
            runs=[]
            for version in [1,2]:
                output=execute(source(name,version),data)
                try:
                    validate(output,data,allow_production_credit=True)
                    status='pass'
                except ValueError as exc:
                    status=str(exc)
                runs.append({'version':version,'output':output,'contract':status})
            if mode=='folded_leaf':
                assert runs[0]['output']['blocks']==[]
                assert [r['text'] for r in runs[1]['output']['blocks']]==['Folded article detail remains.']
            elif mode=='nested_p':
                assert runs[0]['output']==runs[1]['output']
                assert runs[1]['output']['blocks'][0]['text']=='Nested article detail.'
            else:
                assert len(runs[1]['output']['blocks'])==2 and not runs[1]['output']['metadata']
            controls.append({'cluster':name,'mode':mode,'synthetic':True,'data_utf8':data.decode(),'runs':runs})
    feedback={'reviewer':'current_conversation_ai','review_scope':'full static article DOM and v1 outputs of six fixed repair pages; not independent gold labels',
              'findings':[{'code':'standalone_byline_in_body','file':'samples/collected_c5d4b9cdcf5b4c91.html',
                           'evidence':next(r['moved'] for r in results if Path(r['file']).name=='collected_c5d4b9cdcf5b4c91.html'),
                           'requested':'first direct p, full-line media-reporter-name signature only; narrative mentions kept'},
                          {'code':'production_credits_in_body','file':'validation_blind/samples/collected_5029464d5612ed80.html',
                           'evidence':next(r['moved'] for r in results if Path(r['file']).name=='collected_5029464d5612ed80.html'),
                           'requested':'contiguous suffix of explicit pipe-prefixed production-credit lines -> production_credit metadata; do not equate production staff with author'},
                          {'code':'wrapper_inline_text_omitted','evidence_scope':'synthetic folded_leaf controls only',
                           'requested':'preserve inline-only text-bearing wrapper as one paragraph, regardless of display:none; not blanket keep hidden navigation'}],
              'no_change_needed':['v1 already retains repair-page 5x3 table','nested p already supported; retain as control'],
              'remaining_limits':['DOM/image content completeness not independently verified','new wrapper text heuristic could capture unfamiliar noise','mixed text/tail plus nested blocks not fully handled','production-credit schema new; downstream must support it']}
    record={'unit':'3.3','rounds_used':1,'maximum_rounds':2,'split_sha256':digest(SPLIT.read_bytes()),
            'model_api_calls':0,'training_updates':0,'test_pages_executed':0,
            'repair_pages':6,'generation_regressions':6,'patches':patches,
            'process':'current conversation examined saved v1 evidence, wrote v2 patch; default command replays both versions, does not call a repair agent anew',
            'contract_revision':'metadata adds production_credit; v1 default contract unchanged',
            'not_claimed':'overall accuracy, independent judge calibration, autonomous API agent, or RL'}
    OUT.mkdir(parents=True,exist_ok=True)
    for name,value in [('feedback.json',feedback),('repair_record.json',record),('results.json',{'pages':results,'controls':controls})]:
        path=OUT/name
        if path.exists() and load(path)!=value:
            raise ValueError('frozen repair replay changed; do not overwrite: '+name)
        path.write_text(json.dumps(value,ensure_ascii=False,indent=2),encoding='utf-8')
    sections=['<!doctype html><meta charset="utf-8"><title>3.3 代码修复</title><style>body{font:16px/1.8 sans-serif;max-width:1100px;margin:30px auto}pre{white-space:pre-wrap}td,th{padding:8px;border:1px solid #ccc}table{border-collapse:collapse}</style>',
              '<h1>3.3 代码反馈修复：1轮/最多2轮</h1><p>固定修复组6页，生成组回归6页；封存测试未执行。当前对话AI给出反馈及补丁，离线命令仅重放。</p>',
              '<h2>自然页面变化</h2><table><tr><th>页面/分组</th><th>正文块</th><th>移至元数据</th></tr>']
    for r in results:
        sections+=['<tr><td>'+escape(r['file']+' ['+r['role']+']')+'</td><td>'+str(len(r['before']['blocks']))+' → '+str(len(r['after']['blocks']))+'</td><td>'+str(len(r['moved']))+'</td></tr>']
    sections+=['</table><h2>反馈与原文证据</h2><pre>'+escape(json.dumps(feedback,ensure_ascii=False,indent=2))+'</pre>']
    for r in results:
        if r['role']=='repair':
            sections+=['<details><summary>'+escape(r['file'])+'：完整修改前后</summary><pre>'+escape(json.dumps(r,ensure_ascii=False,indent=2))+'</pre></details>']
    sections+=['<h2>受控反例（合成，不计自然泛化）</h2><pre>'+escape(json.dumps(controls,ensure_ascii=False,indent=2))+'</pre>',
               '<h2>代码补丁与版本证据</h2><pre>'+escape(json.dumps(record,ensure_ascii=False,indent=2))+'</pre>']
    (OUT/'index.html').write_text('\n'.join(sections),encoding='utf-8')
    print('UNIT 3.3: one repair round; natural moves=8; generation unchanged=6/6; sealed test executions=0')
    print(OUT/'index.html')


if __name__=='__main__':
    run()
