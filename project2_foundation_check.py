"""Compare the trusted engine against exposed Project 1 references; no API calls."""
import argparse
from collections import Counter
import json
from pathlib import Path
from project2_engine import digest, extract, structural_feedback

ROOT = Path(__file__).resolve().parent

def compact(text):
    return ''.join(text.split())

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',default='output/project2/foundation_v2')
    args=parser.parse_args()
    out=ROOT/args.output
    out.mkdir(parents=True,exist_ok=True)
    if any(out.iterdir()):
        parser.error('Use an empty output directory')
    config=json.loads((ROOT/'config/project2_foundation_reference.json').read_text(encoding='utf8'))
    rows=[]
    for page in config['pages']:
        raw=(ROOT/page['path']).read_bytes()
        if digest(raw)!=page['sha256']:
            raise ValueError('Reference snapshot changed')
        reference=json.loads((ROOT/page['reference']).read_text(encoding='utf8'))
        result=extract(page['rules'],raw)
        (out/(page['id']+'.json')).write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf8')
        # Keep order comparison separate from classification changes.
        expected=[compact(b['text']) for b in reference['blocks']]
        actual=[compact(b['text']) for b in result['blocks']]
        missing=list((Counter(expected)-Counter(actual)).elements())
        added=list((Counter(actual)-Counter(expected)).elements())
        row=dict(id=page['id'],layout=page['layout'],reference_blocks=len(expected),current_blocks=len(actual),
                 body_sequence_equal=expected==actual,missing=missing,added=added,
                 metadata=result['metadata'],issues=structural_feedback(result,raw,page['evaluation_scope_xpath']))
        rows.append(row)
        print(f'{page["id"]}: reference={len(expected)} current={len(actual)} sequence_equal={expected==actual}; pending={len(row["issues"])}')
    report=dict(scope=config['scope'],api_calls=0,semantic_accuracy='unknown',pages=rows)
    (out/'report.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf8')
    from project2_report import render_reference
    render_reference(out)
    return 0 if all(row['body_sequence_equal'] for row in rows) else 1

if __name__=='__main__':
    raise SystemExit(main())
