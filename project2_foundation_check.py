"""Compare the trusted engine against exposed Project 1 references; no API calls."""
import argparse
from collections import Counter
import html
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
    esc=html.escape
    lines=['<!doctype html><meta charset="utf-8"><title>项目一基础迁移对照</title><style>body{font:16px/1.6 system-ui;max-width:1050px;margin:30px auto}pre{white-space:pre-wrap}section{border:1px solid #ccd;padding:18px;margin:18px 0}</style><h1>项目一 → 项目二：固定执行层回归对照</h1><p>已曝光样例、人工参考规则、0次API。不代表模型生成成绩或独立准确率。分类/排除仍有待语义审核的项目会明确保留。</p>']
    for row in rows:
        lines.append('<section><h2>'+esc(row['id'])+'</h2><a href="'+row['id']+'.json">完整提取结果</a><pre>'+esc(json.dumps(row,ensure_ascii=False,indent=2))+'</pre></section>')
    (out/'index.html').write_text('\n'.join(lines),encoding='utf8')
    return 0 if all(row['body_sequence_equal'] for row in rows) else 1

if __name__=='__main__':
    raise SystemExit(main())
