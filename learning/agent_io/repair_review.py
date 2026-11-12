"""重放一次有边界的反馈修正；不调用模型、不修改原审核或正式配置。"""
import argparse
import copy
import json
import sys
from html import escape
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from learning.agent_io.review_pipeline import OUT, build_task, digest, read, validate_review

DEST = OUT / 'repair'


def feedback_for(task, audit):
    checked = validate_review(task, audit)
    return {'review_task_id': task['review_task_id'], 'input_audit_sha256': digest(audit),
            'accepted': checked['accepted'], 'issues': checked['issues'],
            'issue_records': checked.get('issue_records', []),
            'instruction': '只修正有证据的审核决定；禁止改写原文、XPath、Rubrics或其他决定。'}


def apply_plan(task, audit, feedback, plan):
    """审核程序给反馈；本轮 AI 写计划；本函数仅执行严格匹配的计划。"""
    if feedback != feedback_for(task, audit):
        raise ValueError('反馈与当前输入不对应')
    if feedback['accepted']:
        raise ValueError('输入已经通过，无需修正')
    if not isinstance(plan, dict) or plan.get('review_task_id') != task['review_task_id']:
        raise ValueError('修正计划任务不对应')
    if plan.get('input_audit_sha256') != digest(audit) or plan.get('feedback_sha256') != digest(feedback):
        raise ValueError('修正计划已过期：审核或反馈发生变化')
    changes = plan.get('changes')
    if not isinstance(changes, list) or not changes:
        raise ValueError('计划没有修正项')
    repaired = copy.deepcopy(audit)
    used = set()
    for change in changes:
        if not isinstance(change, dict):
            raise ValueError('修正项必须是对象')
        name, index = change.get('file'), change.get('index')
        key = (name, index)
        if key in used:
            raise ValueError('重复修改同一决定')
        used.add(key)
        pages = [p for p in repaired['pages'] if p['file'] == name]
        if len(pages) != 1:
            raise ValueError('计划指定了未知网页')
        entries = [d for d in pages[0]['decisions'] if d['index'] == index]
        if len(entries) != 1 or entries[0] != change.get('before'):
            raise ValueError('计划的修改前证据不匹配')
        after = change.get('after')
        if not isinstance(after, dict) or set(after) != {'action', 'criterion', 'reason'}:
            raise ValueError('只允许修改 action、criterion、reason')
        matching = [r for r in feedback['issue_records'] if r.get('code') == 'rubric_conflict'
                    and r.get('file') == name and r.get('index') == index
                    and r.get('xpath') == entries[0]['xpath']]
        if not matching or not any(r['expected'] == {k: after[k] for k in ['action', 'criterion']} for r in matching):
            raise ValueError('修正缺少对应反馈证据，或偏离反馈约束')
        entries[0].update(after)
    checked = validate_review(task, repaired)
    if not checked['accepted']:
        raise ValueError('重新审核仍失败：' + '; '.join(checked['issues']))
    return repaired, checked


def run(plan_path):
    task = build_task()
    bad = read(OUT / 'review_bad_link.json')
    feedback = feedback_for(task, bad)
    DEST.mkdir(parents=True, exist_ok=True)
    (DEST / 'feedback.json').write_text(json.dumps(feedback, ensure_ascii=False, indent=2), encoding='utf-8')
    plan = read(plan_path)
    repaired, checked = apply_plan(task, bad, feedback, plan)
    changed = []
    for old_page, new_page in zip(bad['pages'], repaired['pages']):
        for old, new in zip(old_page['decisions'], new_page['decisions']):
            if old != new:
                changed.append({'file': old_page['file'], 'index': old['index'], 'before': old, 'after': new})
    reference = validate_review(task, read(OUT / 'review_ai.json'))
    if not reference['accepted']:
        raise ValueError('历史正确审核不再通过，不能用于本次回归比较')
    fields = ['raw_blocks', 'content_blocks', 'editor_blocks', 'excluded_blocks']
    # 比较原始证据及去向，理由措辞可以不同。
    def core(pages):
        return [{k: [{f: b[f] for f in ['index', 'xpath', 'text']} for b in p[k]] for k in fields} for p in pages]
    regression = core(checked['pages']) == core(reference['pages'])
    if not regression:
        raise ValueError('修正结果与已确认去向不一致，需要复核')
    report = {'accepted': True, 'input_rejected': not feedback['accepted'],
              'review_task_id': task['review_task_id'], 'feedback_sha256': digest(feedback),
              'plan_sha256': digest(plan), 'changed_count': len(changed), 'changes': changed,
              'unchanged_count': sum(len(p['decisions']) for p in bad['pages']) - len(changed),
              'regression_matches_known_reference': regression, 'sample_role': 'known_development_samples',
              'ai_calls': 0, 'published': False, 'pages': checked['pages']}
    for filename, data in [('repaired_audit.json', repaired), ('repair_result.json', report)]:
        (DEST / filename).write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding='utf-8')
    lines = ['<!doctype html><html lang=zh-CN><meta charset=utf-8><title>反馈修正实验</title>',
             '<style>body{font:16px/1.7 system-ui;max-width:1100px;margin:30px auto;padding:16px}',
             'td,th{border:1px solid #ddd;padding:12px;vertical-align:top}table{border-collapse:collapse;width:100%}',
             'code{overflow-wrap:anywhere}</style><h1>反馈修正：REJECT → PASS</h1>',
             '<p>当前对话 AI 已提供修正计划；程序只重放计划，不调用模型。已知开发页回归，不是盲测，不是训练。</p>',
             f"<p>修改 {len(changed)} / {len(changed) + report['unchanged_count']} 个决定；其他 {report['unchanged_count']} 个不变；原文、XPath、顺序及标准不变。</p>",
             '<h2>1. 程序反馈</h2><ul>']
    lines += ['<li>' + escape(s) + '</li>' for s in feedback['issues']]
    lines += ['</ul><h2>2. 当前对话 AI 的修正</h2><table><tr><th>段落</th><th>修正前</th><th>修正后</th></tr>']
    for c in changed:
        lines.append('<tr><td>' + escape(c['file']) + f" #{c['index']}<br>" + escape(c['before']['text'])
                     + '</td><td>' + escape(json.dumps({k:c['before'][k] for k in ['action','criterion','reason']}, ensure_ascii=False))
                     + '</td><td>' + escape(json.dumps({k:c['after'][k] for k in ['action','criterion','reason']}, ensure_ascii=False)) + '</td></tr>')
    lines += ['</table><h2>3. 重新审核与回归</h2><ul>',
              '<li>Rubrics 列明检查通过；每段恰好一个决定，原始证据完整。</li>',
              '<li>正文、编辑、排除去向与历史正确审核一致；这是回归证据，不是跨页准确率。</li></ul>']
    for p in checked['pages']:
        lines.append(f"<p>{escape(p['file'])}：原始 {len(p['raw_blocks'])}，正文 {len(p['content_blocks'])}，编辑 {len(p['editor_blocks'])}，排除 {len(p['excluded_blocks'])}。</p>")
        lines.append('<details><summary>展开修正后正文</summary>' + ''.join('<p>' + escape(b['text']) + '</p>' for b in p['content_blocks']) + '</details>')
    lines.append('</html>')
    (DEST / 'index.html').write_text('\n'.join(lines), encoding='utf-8')
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--plan', type=Path, default=OUT / 'repair_plan.json')
    parser.add_argument('--prepare', action='store_true')
    args = parser.parse_args()
    try:
        if args.prepare:
            task = build_task()
            feedback = feedback_for(task, read(OUT / 'review_bad_link.json'))
            DEST.mkdir(parents=True, exist_ok=True)
            (DEST / 'feedback.json').write_text(json.dumps(feedback, ensure_ascii=False, indent=2), encoding='utf-8')
            print('Feedback ready; AI calls=0; no repair applied.')
            return 0
        # 清除本实验上一轮成功产物的有效状态，避免失败时误读旧报告。
        DEST.mkdir(parents=True, exist_ok=True)
        (DEST / 'repair_result.json').write_text('{"accepted": false, "status": "running"}', encoding='utf-8')
        report = run(args.plan)
    except (OSError, ValueError, KeyError, TypeError) as exc:
        result = {'accepted': False, 'error': str(exc), 'pages': []}
        DEST.mkdir(parents=True, exist_ok=True)
        (DEST / 'repair_result.json').write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding='utf-8')
        (DEST / 'index.html').write_text('<meta charset=utf-8><h1>REJECT：未生成有效修正结果</h1><p>' + escape(str(exc)) + '</p>', encoding='utf-8')
        (DEST / 'repaired_audit.json').write_text('null', encoding='utf-8')
        print('REPAIR REJECTED: ' + str(exc))
        return 1
    print('BEFORE: REJECTED; AFTER: PASS')
    print(f"CHANGED: {report['changed_count']}; UNCHANGED: {report['unchanged_count']}")
    print('KNOWN-CASE REGRESSION: PASS; AI calls=0; NOT PUBLISHED.')
    print('REPORT: ' + str(DEST / 'index.html'))
    return 0


if __name__ == '__main__':
    sys.exit(main())
