"""Reuse frozen model-generated rules on local HTML without another API call."""
import argparse
import json
from pathlib import Path
from project2_agent import evaluate

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('pages', nargs='+', help='HTML paths or quoted glob patterns')
    parser.add_argument('--rules', default='output/project2/live_flash_final/rules.json')
    parser.add_argument('--output', default='output/project2/my_batch')
    args=parser.parse_args()
    from glob import glob
    paths=[]
    for pattern in args.pages:
        matches=glob(pattern)
        if not matches:
            parser.error('No matching HTML: '+pattern)
        paths.extend(Path(x).resolve() for x in matches)
    if len(set(paths)) != len(paths):
        parser.error('Duplicate input paths')
    out=Path(args.output).resolve()
    out.mkdir(parents=True,exist_ok=True)
    if any(out.iterdir()):
        parser.error('Use an empty output directory to preserve prior evidence')
    rules=json.loads(Path(args.rules).read_text(encoding='utf8'))
    rows=[]
    for index,path in enumerate(paths,1):
        row=evaluate({'id':f'page_{index}', 'role':'batch_reuse', 'path':str(path),'url':''}, rules,out,'extract')
        row['input']=str(path)
        rows.append(row)
        print(f'{path.name}: {row["status"]}; blocks={row.get("blocks",0)}')
    (out/'summary.json').write_text(json.dumps(rows,ensure_ascii=False,indent=2),encoding='utf8')
    return 0 if all(row['status']=='pass' for row in rows) else 1

if __name__=='__main__':
    raise SystemExit(main())
