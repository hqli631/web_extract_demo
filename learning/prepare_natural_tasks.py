"""Prepare reviewed natural-layout targets; never parse frozen test pages."""
from __future__ import annotations
import importlib.util
import json
from pathlib import Path
from lxml import html
from learning.expand_natural_data import ROOT, sha
from learning.prepare_sft_data import SYSTEM, CONTRACT

SELECTORS = {
    'python_sphinx_v1': "//div[@role='main' and contains(concat(' ',normalize-space(@class),' '),' body ')]",
    'sqlite_document_v1': "//div[contains(concat(' ',normalize-space(@class),' '),' fancy ')]",
    'pg_essay_v1': "//td[@width='435']/font[@size='2' and @face='verdana']",
}

def structure(body, max_nodes=70):
    """Bounded ordered prefix, with declared omissions; not a complete DOM."""
    nodes=[]; total=0
    for node in body.iter():
        if not isinstance(node.tag,str) or node.tag in {'script','style'}:
            continue
        total+=1
        if len(nodes)>=max_nodes:
            continue
        path=[]; cursor=node
        while cursor is not None and cursor is not body:
            path.append(cursor.tag);cursor=cursor.getparent()
        own=' '.join((node.text or '').split())
        tail=' '.join((node.tail or '').split())
        nodes.append([len(path),node.tag,{k:v[:80] for k,v in node.attrib.items() if k in {'id','class','role','width','face','size'}},own[:32],tail[:32]])
    return dict(columns=['depth','tag','attributes','text_prefix','tail_prefix'],nodes=nodes,total_nodes=total,nodes_omitted=total-len(nodes),max_nodes=max_nodes,text_limit=32)

def prepare():
    manifest_path=ROOT/'output/stage5/multitask/natural_manifest.json'
    manifest=json.loads(manifest_path.read_text(encoding='utf8'))
    out=ROOT/'output/stage5/multitask';records=[];checks=[]
    for cluster in manifest['clusters']:
        task=cluster['task_id'];code_path=ROOT/'learning/generated'/(task+'.py')
        code=code_path.read_bytes()
        # Only hand-written, reviewed reference source is imported here, never model output.
        spec=importlib.util.spec_from_file_location('reference_'+task,code_path)
        module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
        samples=[];sources=[]
        for page in cluster['pages']:
            if page['role']=='test':
                continue
            raw=(ROOT/page['path']).read_bytes()
            if sha(raw)!=page['sha256']: raise ValueError('source hash mismatch')
            result=module.extract(raw);tree=html.document_fromstring(raw)
            assert set(result)=={'title','blocks','metadata','excluded','warnings'}
            assert result['title'] and result['blocks']
            for block in result['blocks']+result['metadata']+result['excluded']:
                matched=tree.xpath(block['xpath']);assert len(matched)==1
                expected=' '.join(matched[0].text_content().replace('¶','').split())
                assert block['text'] in expected, (task,block)
            checks.append(dict(task_id=task,path=page['path'],role=page['role'],title=result['title'],blocks=len(result['blocks']),metadata=len(result['metadata']),excluded=len(result['excluded']),contract_and_source_evidence_pass=True))
            (out/(task+'_'+page['role']+'_'+Path(page['path']).stem+'_reference.json')).write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n',encoding='utf8')
            if page['role']=='train':
                body=tree.xpath(SELECTORS[task])[0]
                samples.append(dict(title_dom=[html.tostring(n,encoding='unicode') for n in tree.xpath('//title|//h1')[:4]],article_structure=structure(body)))
                sources.append(dict(path=page['path'],sha256=page['sha256']))
        prompt=CONTRACT+'\nTwo natural same-layout training-page structural excerpts follow. The main container was preselected by a reviewed reference; this is a bounded structure prefix, not the complete DOM. Node order/depth and selected attributes are retained; after 70 nodes omitted; text/tails capped at 32 characters. Test and development HTML never enter this prompt.\n'+json.dumps(samples,ensure_ascii=False,separators=(',',':'))
        records.append(dict(id='natural-'+task,split='train',group_id=task,historical_exposure=False,sources=sources,target=dict(path=str(code_path.relative_to(ROOT)).replace('\\','/'),sha256=sha(code)),
                            messages=[dict(role='system',content=SYSTEM),dict(role='user',content=prompt),dict(role='assistant',content=code.decode('utf8'))],
                            compression=dict(method='ordered_structure_prefix',max_nodes_per_page=70,text_slot_limit=32),
                            scope='reviewed teaching reference; static text; not independently certified gold'))
        cluster['target_code']=dict(path=str(code_path.relative_to(ROOT)).replace('\\','/'),sha256=sha(code),reviewed_by='current_conversation_subagent',review_scope='train/dev source evidence and contract; no test inspection')
    (out/'natural_train.jsonl').write_text(''.join(json.dumps(r,ensure_ascii=False)+'\n' for r in records),encoding='utf8',newline='\n')
    (out/'natural_reference_checks.json').write_text(json.dumps(dict(checks=checks,test_dom_inspected=False,semantic_gold_certified=False),ensure_ascii=False,indent=2)+'\n',encoding='utf8')
    manifest['clusters_with_reviewed_targets']=manifest['clusters'];manifest['test_dom_inspected']=False
    (out/'natural_tasks.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2)+'\n',encoding='utf8')
    protocol=dict(format_version=1,status='registered',purpose='Preregistered natural same-layout page holdouts; not whole-layout holdouts',
                  known_exposed_task_ids=['sina_shell_v2','chinanews_shell_v2'],clusters=[])
    for cluster in manifest['clusters']:
        protocol['clusters'].append(dict(task_id=cluster['task_id'],layout_family=cluster['layout_family'],status='ready',
            pages=[dict(path=p['path'],url=p['url'],sha256=p['sha256'],role=p['role'],exposure='new',development_inspected=p['role']!='test') for p in cluster['pages']],
            target_code=cluster['target_code'],notes='2 training pages are one code-generation task; development inspected, test bytes stored but DOM not inspected. Not a cross-layout test.'))
    (ROOT/'config/next_layout_tasks.json').write_text(json.dumps(protocol,ensure_ascii=False,indent=2)+'\n',encoding='utf8')
    print(json.dumps(dict(training_tasks=len(records),natural_pages=12,development_reference_checks=len(checks),frozen_unread_tests=3,prompt_characters=[len(r['messages'][1]['content']) for r in records])))
    return records,checks

if __name__=='__main__':
    prepare()
