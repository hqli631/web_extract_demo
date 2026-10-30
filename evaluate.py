"""Evaluate browser predictions against explicitly reviewed regions only."""
import argparse
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent
BODY = {'body', 'missing'}


def metrics(rows, field):
    tp = fp = fn = 0
    for r in rows:
        predicted, actual = r.get(field) in BODY, r.get('label') in BODY
        tp += predicted and actual
        fp += predicted and not actual
        fn += not predicted and actual
    precision = tp / (tp + fp) if tp + fp else None
    recall = tp / (tp + fn) if tp + fn else None
    f1 = 2 * tp / (2 * tp + fp + fn) if 2 * tp + fp + fn else None
    return dict(tp=tp, fp=fp, fn=fn, precision=precision, recall=recall, f1=f1)


def evaluate(data, root=ROOT):
    pages, errors, baseline, predicted = [], [], [], []
    for name, page in data.items():
        sample = root / 'samples' / name
        if not page.get('snapshot') or not sample.is_file() or hashlib.sha256(sample.read_bytes()).hexdigest() != page['snapshot']:
            pages.append(dict(file=name, status='stale_or_missing_snapshot', reviewed=0))
            continue
        all_rows = page.get('regions', [])
        # pending is explicitly unresolved, even if accidentally confirmed.
        reviewed = [r for r in all_rows if r.get('reviewed') is True and r.get('label') != 'pending']
        baseline.extend(reviewed)
        predicted.extend(reviewed)
        pages.append(dict(file=name, status='evaluated', total=len(all_rows), reviewed=len(reviewed),
                          coverage=len(reviewed)/len(all_rows) if all_rows else 0,
                          baseline=metrics(reviewed, 'auto_label'), rules=metrics(reviewed, 'predicted_label')))
        for r in reviewed:
            if (r.get('predicted_label') in BODY) != (r.get('label') in BODY):
                errors.append(dict(file=name, id=r.get('id'), type='false_positive' if r.get('predicted_label') in BODY else 'false_negative',
                                   locator=r.get('locator'), text=r.get('text'), prediction=r.get('predicted_label'), truth=r.get('label')))
    return dict(unit='region', reviewed=len(predicted), baseline=metrics(baseline, 'auto_label'),
                rules=metrics(predicted, 'predicted_label'), pages=pages, errors=errors,
                note='Only explicitly reviewed, non-pending regions of unchanged snapshots are scored. In-sample scores are not held-out accuracy. Undetected DOM regions are outside this metric.')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--annotations', type=Path, default=ROOT/'reports/annotations.json')
    args = parser.parse_args()
    data = json.loads(args.annotations.read_text(encoding='utf-8-sig')) if args.annotations.exists() else {}
    report = evaluate(data)
    folder = ROOT/'reports'
    folder.mkdir(exist_ok=True)
    candidates = [dict(file=e['file'], files=[e['file']], locator=e['locator'],
                       label='body' if e['truth'] in BODY else 'noise',
                       reason=e['type'], expected_text=e['text'])
                  for e in report['errors'] if e.get('locator')]
    (folder/'rule_candidates.json').write_text(json.dumps(candidates, ensure_ascii=False, indent=2), encoding='utf-8')
    (folder/'evaluation.json').write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
    lines = ['# 正文抽取评测', '', f"已评分人工区域：{report['reviewed']}", '', '|预测|Precision|Recall|F1|误提|漏提|', '|---|---|---|---|---|---|']
    for key in ('baseline', 'rules'):
        m = report[key]
        display = lambda x: 'N/A' if x is None else f'{x:.3f}'
        lines.append(f"|{key}|{display(m['precision'])}|{display(m['recall'])}|{display(m['f1'])}|{m['fp']}|{m['fn']}|")
    lines += ['', '仅评分已确认且非待判断区域；未确认区域、过期快照不会作为真值。样本内规则得分不能当成泛化效果。未检测到的区域需另外检查。', '', '详情和 XPath 错例见 evaluation.json。rule_candidates.json 为未启用的修正规则建议，需先在界面测试匹配范围，再保存。']
    (folder/'evaluation.md').write_text('\n'.join(lines), encoding='utf-8')
    print(f"Reviewed regions: {report['reviewed']}; reports/evaluation.md and evaluation.json")


if __name__ == '__main__':
    main()
