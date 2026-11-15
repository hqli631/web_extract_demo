"""Replay only reviewed fixed-hash model-generated extractors; never arbitrary code."""
import argparse,hashlib,importlib.util,json,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from learning.evaluate_multitask import validate_result
def replay(cluster,source):
    registry=json.loads((ROOT/'output/stage5/multitask/approved_candidates.json').read_text(encoding='utf8'))
    row=registry['candidates'][cluster];path=ROOT/row['path']
    if hashlib.sha256(path.read_bytes()).hexdigest()!=row['sha256']:raise ValueError('reviewed code hash changed; refuse local execution')
    spec=importlib.util.spec_from_file_location('reviewed_model_'+cluster,path)
    mod=importlib.util.module_from_spec(spec);spec.loader.exec_module(mod)
    raw=Path(source).read_bytes();result=mod.extract(raw)
    issues=validate_result(result,raw)
    if issues:raise ValueError('output validation failed: '+str(issues))
    return result
def main():
    p=argparse.ArgumentParser();p.add_argument('--cluster',required=True,choices=['python_sphinx_v1','sqlite_document_v1','pg_essay_v1']);p.add_argument('--input',required=True);p.add_argument('--output',required=True)
    a=p.parse_args();out=Path(a.output)
    if out.exists():raise ValueError('output exists; choose a new file rather than overwrite evidence')
    result=replay(a.cluster,a.input);out.parent.mkdir(parents=True,exist_ok=True)
    out.write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf8')
    print('TITLE:',result['title']);print('BLOCKS:',len(result['blocks']));print('SAVED:',out)
if __name__=='__main__':main()
