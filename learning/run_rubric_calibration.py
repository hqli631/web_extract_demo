"""Replay saved AI judgments; compare expected labels only after validation."""
import copy
import json
import hashlib
import sys
from html import escape
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from learning.prepare_rubric_review import OUT, read
from learning.agent_io.review_pipeline import digest
from learning.agent_io.score_body_quality import score_case

def save(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding='utf-8')

def validate(task, response):
    if response.get('task_id') != task['task_id'] or response.get('task_sha256') != digest(task):
        raise ValueError('Review task identity/hash mismatch')
    if [r.get('case_id') for r in response.get('cases', [])] != [c['case_id'] for c in task['cases']]:
        raise ValueError('Review cases missing, duplicated or reordered')
    return [score_case(task, c, r) for c, r in zip(task['cases'], response['cases'])]

def validate_protocol(task, protocol):
    actual = {'task_sha256': digest(task), 'rubric_sha256': digest(task['rubric']),
              'scorer_sha256': hashlib.sha256((ROOT/'learning/agent_io/score_body_quality.py').read_bytes()).hexdigest(),
              'gate_implementation_sha256': hashlib.sha256(Path(__file__).read_bytes()).hexdigest()}
    if any(protocol.get(k) != v for k,v in actual.items()):
        raise ValueError('Frozen scoring protocol changed; create a new version')

def compare(task, response, original, mapping):
    results = validate(task, response)
    labels = {c['case_id']: c['expected_answers'] for c in original['cases']}
    matrix = {q: {e: {a: 0 for a in ['yes','no','unknown']} for e in ['yes','no','unknown']} for q in ['Q1','Q2','Q3','Q4','Q5']}
    agree = unknown = valid_questions = 0
    rows = []
    for result in results:
        expected = labels[mapping[result['case_id']]]
        if result['response_valid']:
            for a in result['answers']:
                q, actual = a['id'], a['verdict']
                matrix[q][expected[q]][actual] += 1
                agree += actual == expected[q]
                unknown += actual == 'unknown'
                valid_questions += 1
        rows.append(dict(result, expected=expected, fixture=mapping[result['case_id']]))
    summary = {'cases': len(rows), 'valid_cases': sum(r['response_valid'] for r in rows),
               'valid_questions': valid_questions, 'question_agreement_rate': agree / valid_questions if valid_questions else None,
               'unknown_rate': unknown / valid_questions if valid_questions else None,
               'confusion': matrix, 'independent_review_completed': False,
               'repeat_agreement': None, 'independent_human_gold': False,
               'review_origin': 'current conversation AI, aware of prior fixture context',
               'replay_model_api_calls': 0, 'api_cost': None, 'review_wall_time': None, 'training_updates': 0,
               'limit': 'Quote validation proves citation existence, not semantic correctness or sufficient coverage. Agreement is against synthetic expected labels, not accuracy. Separate-context delegation received empty messages and did not review.'}
    return {'task_sha256': digest(task), 'response_sha256': digest(response), 'summary': summary, 'rows': rows}

def gate_checks(task, response):
    # Explicit protocol simulations, not additional AI reviews.
    good_index = next(i for i,c in enumerate(task['cases']) if c['case_id'] == 'item_04')
    c, r = task['cases'][good_index], response['cases'][good_index]
    demos = {}
    for name in ['unknown', 'invalid_quote', 'execution_error', 'stale_task', 'missing_question', 'dishonest_all_yes']:
        cc, rr = copy.deepcopy(c), copy.deepcopy(r)
        if name == 'unknown': rr['answers'][2]['verdict'] = 'unknown'
        if name == 'invalid_quote': rr['answers'][0]['source_evidence'][0]['quote'] = 'FABRICATED QUOTE'
        if name == 'execution_error': cc['execution_status'] = 'error'
        if name == 'stale_task': rr['task_id'] = 'old-task'
        if name == 'missing_question': rr['answers'].pop()
        if name == 'dishonest_all_yes':
            idx = next(i for i,x in enumerate(task['cases']) if x['case_id'] == 'item_05')
            cc, rr = copy.deepcopy(task['cases'][idx]), copy.deepcopy(response['cases'][idx])
            rr['answers'][3].update(verdict='yes', reason='SIMULATED wrong judgment: promotion mistakenly accepted; quotes still exist.')
        demos[name] = score_case(task, cc, rr)
    demos['interpretation'] = 'Unknown/invalid/execution failures are withheld. A semantically wrong but protocol-valid all-yes review still passes: numerical gates alone do not solve judge errors.'
    # Explicit simulated judge for a copy-whole-source candidate, not an AI run.
    cc, rr = copy.deepcopy(c), copy.deepcopy(r)
    records = task['sources'][c['source_id']]['records']
    cc['output'] = [{'id': r['id'], 'text': r['text']} for r in records if r['id'] != 'inventory']
    cc['output'].append({'id': 'inventory', 'text': json.dumps(cc['output'],ensure_ascii=False)})
    for answer in rr['answers']:
        answer['output_evidence'] = [{'id': 'inventory', 'quote': cc['output'][-1]['text']}]
    rr['answers'][3].update(verdict='no', reason='SIMULATION: copying all source includes author, menu, CTA and promotion; more text is not better quality.')
    demos['copy_entire_page_simulated_judge'] = score_case(task, cc, rr)
    return demos

def run():
    task = read(OUT/'task.json')
    validate_protocol(task, read(OUT/'scoring_protocol.json'))
    response = read(OUT/'reviewer_current.json')
    original = read(ROOT/'output/stage4/specification/cases.json')
    comparison = compare(task, response, original, read(OUT/'private_mapping.json'))
    save(OUT/'comparison.json', comparison)
    gates = gate_checks(task, response)
    save(OUT/'gate_checks.json', gates)
    parts = ['<!doctype html><meta charset=utf-8><title>4.2修正与4.3门槛检查</title>',
             '<style>body{font:16px/1.7 sans-serif;max-width:1150px;margin:30px auto}table{border-collapse:collapse}td,th{border:1px solid #ccc;padding:8px}pre{white-space:pre-wrap;overflow-wrap:anywhere}</style>',
             '<h1>已保存评审 → 引用校验 → 标签比较 → 计分与门槛</h1>',
             '<p>旧版复制expected作为actual，已作废；历史文件保留。当前为本对话AI逐案审核并保存的回答，不是程序从expected生成回答。评审者已知案例背景，独立上下文任务未成功；独立复核和自然页校准待完成。</p>',
             '<p>回放不调用AI。引文真实不代表判断必然正确。五题等权时总分只有0、0.2、0.4、0.6、0.8、1.0；0.9门槛实际要求全yes，Q2/Q3关键门槛在当前配置下数值上冗余，保留其业务解释。unknown不计分。</p>',
             '<pre>'+escape(json.dumps(comparison['summary'],ensure_ascii=False,indent=2))+'</pre>',
             '<table><tr><th>案例</th><th>实际Q1—Q5</th><th>score</th><th>采用</th></tr>']
    for row in comparison['rows']:
        parts.append('<tr><td>'+escape(row['case_id']+' '+row['fixture'])+'</td><td>'+escape(' / '.join(a['verdict'] for a in row['answers']))+'</td><td>'+str(row['score'])+'</td><td>'+row['adoption']+'</td></tr>')
    parts.append('</table><h2>拒绝计分与投机检查</h2>')
    for name, result in gates.items():
        parts.append('<details><summary>'+name+'</summary><pre>'+escape(json.dumps(result,ensure_ascii=False,indent=2))+'</pre></details>')
    parts.append('<h2>每题理由与证据</h2>')
    for row in comparison['rows']:
        parts.append('<details><summary>'+escape(row['case_id']+' '+row['fixture'])+'</summary><pre>'+escape(json.dumps(row,ensure_ascii=False,indent=2))+'</pre></details>')
    parts.append('<p><a href=task.json>源和候选</a> · <a href=reviewer_current.json>保存的AI判断</a> · <a href=comparison.json>比较结果</a> · <a href=gate_checks.json>门槛实验</a></p>')
    (OUT/'index.html').write_text('\n'.join(parts),encoding='utf-8')
    for row in comparison['rows']:
        print(f"{row['case_id']}: valid={row['response_valid']} score={row['score']} {row['adoption']}")
    print('REVIEW: saved current-conversation AI; independent calibration=PENDING')
    print('GATES: unknown/invalid/execution unscored; dishonest valid judgment can still pass')
    print(OUT/'index.html')
    if not all(r['response_valid'] for r in comparison['rows']):
        raise SystemExit(1)

if __name__ == '__main__':
    run()
