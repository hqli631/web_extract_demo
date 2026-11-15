"""Static audit for generated extraction code; never executes candidates."""
import ast
import json
from html import escape
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
RUN=ROOT/'output/stage5/unit2/cloud_run_20261115'
KEYS={'title','blocks','metadata','excluded','warnings'}

def audit_text(text, split):
    issues=[]
    code=text.strip()
    fence=chr(96)*3
    if code.startswith(fence):
        issues.append('markdown_fence')
        code='\n'.join(code.splitlines()[1:])
        code=code.rsplit(fence,1)[0] if fence in code else code
    try:
        tree=ast.parse(code)
    except SyntaxError as e:
        return dict(split=split,python_parse=False,issues=issues+['syntax_error:'+str(e)],executed=False,accepted=False)
    funcs=[n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name=='extract']
    if len(funcs)!=1 or len(funcs[0].args.args)!=1:
        issues.append('extract_must_accept_one_data_argument')
    imports=[]
    return_keys=[]
    for n in ast.walk(tree):
        if isinstance(n,ast.Import):
            imports.extend(a.name.split('.')[0] for a in n.names)
        elif isinstance(n,ast.ImportFrom):
            imports.append(n.module or '')
        elif isinstance(n,ast.Return) and isinstance(n.value,ast.Dict):
            return_keys.extend(k.value for k in n.value.keys if isinstance(k,ast.Constant) and isinstance(k.value,str))
        elif isinstance(n,ast.Assign) and isinstance(n.value,ast.Dict):
            for t in n.targets:
                if isinstance(t,ast.Name) and t.id in {'metadata','excluded','warnings'}:
                    issues.append(t.id+'_dict_assignment')
    if set(imports)-{'re','lxml'}:
        issues.append('unsupported_import')
    if set(return_keys)!=KEYS:
        issues.append('return_keys_not_contract')
    if split=='train' and 'artibody' not in code:
        issues.append('missing_sina_artibody_container')
    if split=='dev' and 'left_zw' not in code:
        issues.append('missing_chinanews_left_zw_container')
    if 'xpath' not in code:
        issues.append('no_xpath_evidence_field')
    if 'etree.fromstring' in code:
        issues.append('xml_parser_for_html_not_robust')
    if '<article>' in code:
        issues.append('wrong_article_container')
    for n in ast.walk(tree):
        if not isinstance(n,ast.Call) or not isinstance(n.func,ast.Attribute):
            continue
        if n.func.attr=='get' and n.args and isinstance(n.args[0],ast.Constant) and n.args[0].value=='xpath':
            issues.append('reads_xpath_attribute_instead_of_computing_dom_path')
        if n.func.attr in {'find','findall'} and n.args and isinstance(n.args[0],ast.Constant) and isinstance(n.args[0].value,str) and '/text()' in n.args[0].value:
            issues.append('element_find_does_not_support_xpath_text_function')
        if n.func.attr=='search' and len(n.args)>1 and isinstance(n.args[0],ast.Constant) and isinstance(n.args[0].value,str) and isinstance(n.args[1],ast.Name) and n.args[1].id=='data':
            issues.append('string_regex_pattern_used_on_bytes_input')
    if 'title_candidates' in code or 'article_dom' in code:
        issues.append('returns_input_summary_fields')
    issues=sorted(set(issues))
    return dict(split=split,python_parse=True,imports=sorted(set(imports)),issues=issues,executed=False,accepted=not issues,quality_evaluation='not_run')

def run():
    results=[]
    for fn in ('before_generation.json','after_generation.json'):
        data=json.loads((RUN/fn).read_text(encoding='utf-8'))
        for out in data['outputs']:
            results.append(dict(stage=fn.removesuffix('_generation.json'),**audit_text(out['text'],out['split'])))
    report=dict(purpose='static audit only; never imported/executed',contract_keys=sorted(KEYS),accepted_count=sum(r['accepted'] for r in results),total_count=len(results),results=results,limits=['static findings are not semantic scores','no candidate executed','reference outputs are separate evidence','this finite pattern audit is not a safety sandbox or proof of successful execution'])
    (RUN/'model_audit.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    page=['<!doctype html><meta charset="utf-8"><title>模型输出审计</title>','<style>body{font:16px/1.7 sans-serif;max-width:1000px;margin:30px auto}pre{white-space:pre-wrap;background:#f4f6f8;padding:14px}</style>','<h1>模型生成抽取代码：静态契约审计</h1>','<p><b>没有导入或执行模型生成代码。</b>只检查接口和明显结构问题，不是正文质量评估。</p>']
    for item in results:
        page.append('<h2>'+escape(item['stage']+' / '+item['split'])+'</h2><pre>'+escape(json.dumps(item,ensure_ascii=False,indent=2))+'</pre>')
    (RUN/'model_audit.html').write_text('\n'.join(page),encoding='utf-8')
    print('STATIC AUDIT:',len(results),'outputs; accepted=',report['accepted_count'],'; executed=0')

if __name__=='__main__':
    run()
