"""Finite repair/adopt/rollback replay of reviewed code, not autonomous RL.

Imports only fixed-hash trusted reference modules, never cloud-model candidates.
"""
from __future__ import annotations
import copy
import difflib
import hashlib
import importlib.util
import json
from html import escape
from pathlib import Path
import time

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'output/stage5/rsi_delivery'
TRUSTED = {
    1: ('learning/generated/chinanews_v1.py', '6cc49ba579af9d3dc85738ccfb5a1a24a7b6958ae32dfc724d98f44639e772ff'),
    2: ('learning/generated/chinanews_v2.py', '9b2f47fd572bbb103b910a01292a43ccabebdc30a7e62bdbc42fa3177aa43ff2'),
}
DEVELOPMENT_PAGES = (
    'samples/xpath_practice.html',
    'samples/xpath_practice_02.html',
    'samples/xpath_practice_03.html',
)

def digest(raw):
    return hashlib.sha256(raw).hexdigest()

def load_trusted(version):
    relative, expected = TRUSTED[version]
    path = ROOT / relative
    if digest(path.read_bytes()) != expected:
        raise ValueError('reviewed reference hash changed: ' + relative)
    spec = importlib.util.spec_from_file_location('trusted_rsi_v' + str(version), path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.extract

def fixture(mode):
    prefix = '<meta charset="utf-8"><h1 class="content_left_title">Synthetic repair control</h1><div class="left_zw">'
    if mode == 'folded_leaf':
        body = '<div style="display:none">Folded <span>article detail</span> remains.</div>'
    elif mode == 'interview':
        body = '<p>中新社记者：您如何评价人工智能合作？</p><p>受访者：应当加强交流。</p>'
    elif mode == 'nested_p':
        body = '<section><p>Nested detail stays.</p></section>'
    else:
        raise ValueError(mode)
    return (prefix + body + '</div>').encode('utf-8')

def gate(candidate, baseline, controls):
    """Quality cannot be traded for fewer rounds: every required check must pass."""
    checks = []
    for name, expected in controls.items():
        actual = candidate[name]
        checks.append(dict(check=name, pass_check=actual == expected,
                           expected=expected, actual=actual))
    for name, expected in baseline.items():
        actual = candidate[name]
        checks.append(dict(check=name, pass_check=actual == expected,
                           expected_sha256=digest(json.dumps(expected, ensure_ascii=False, sort_keys=True).encode()),
                           actual_sha256=digest(json.dumps(actual, ensure_ascii=False, sort_keys=True).encode())))
    return dict(adopt=all(row['pass_check'] for row in checks), checks=checks)

def run():
    start = time.monotonic()
    old, fixed = load_trusted(1), load_trusted(2)
    raw_pages = {path: (ROOT/path).read_bytes() for path in DEVELOPMENT_PAGES}
    old_pages = {path: old(raw) for path, raw in raw_pages.items()}
    fixed_pages = {path: fixed(raw) for path, raw in raw_pages.items()}
    if old_pages != fixed_pages:
        raise ValueError('reference v2 changed exposed generation pages; review required')

    def signals(extractor):
        result = {path: extractor(raw) for path, raw in raw_pages.items()}
        for mode in ('folded_leaf', 'interview', 'nested_p'):
            output = extractor(fixture(mode))
            result[mode] = [block['text'] for block in output['blocks']]
        return result

    baseline = old_pages
    required = {'folded_leaf': ['Folded article detail remains.'],
                'interview': ['中新社记者：您如何评价人工智能合作？', '受访者：应当加强交流。'],
                'nested_p': ['Nested detail stays.']}
    before = signals(old)
    repaired = signals(fixed)
    before_gate = gate(before, baseline, required)
    repair_gate = gate(repaired, baseline, required)
    if before_gate['adopt'] or not repair_gate['adopt']:
        raise ValueError('repair replay expectation failed')
    # Authored destructive output candidate, not unknown generated Python.
    bad = copy.deepcopy(repaired)
    removed = bad['interview'].pop(0)
    first_path = DEVELOPMENT_PAGES[0]
    removed_natural = bad[first_path]['blocks'].pop(0)
    bad_gate = gate(bad, repaired, {})
    if bad_gate['adopt']:
        raise ValueError('destructive candidate unexpectedly passed')
    active = dict(version='chinanews_v2', sha256=TRUSTED[2][1])
    report = dict(
        schema_version=1,status='finite_repair_and_rollback_verified',cluster='chinanews_shell_v2',
        source_scope='three historical exposed generation pages plus synthetic controls; no sealed natural test read',
        candidate_author='current_conversation_coding_agent',
        candidate_generation='reviewed historical v1-to-v2 patch; destructive candidate is an explicit output-mutation control',
        autonomous_new_patch_generation=False,cloud_model_candidates_executed=False,synthetic_quality_controls=True,
        maximum_attempts_per_case=2,
        rounds=[
            dict(case='folded_inline_body_missing',attempt=1,
                 before_version=TRUSTED[1][0],candidate_version=TRUSTED[2][0],
                 before_gate=before_gate,candidate_gate=repair_gate,action='adopt',active_after=active,
                 rationale='Keep meaningful inline-only hidden body wrapper; existing three pages, interview question and nested paragraph must remain unchanged.'),
            dict(case='destructive_deletion_candidate',attempt=1,
                 candidate_kind='deterministic output mutation: remove first natural paragraph and interview question',
                 removed_interview_question=removed,removed_natural_block=removed_natural,
                 candidate_gate=bad_gate,action='reject_and_rollback',active_after=active,
                 rationale='Regression gate detects removed content. Keep the accepted code hash; candidate is never activated.'),
        ],
        sources=[dict(path=path,sha256=digest(raw),exposure='historical_exposed') for path,raw in raw_pages.items()],
        versions=[dict(version=n,path=p,sha256=h) for n,(p,h) in TRUSTED.items()],final_active=active,
        costs=dict(model_api_calls=0,gpu_training_steps=0,attempts=2,reference_extractions=18),
        elapsed_seconds=time.monotonic()-start,
        quality_interpretation='Deterministic regression evidence for this replay, not natural-page semantic accuracy or learned self-improvement.',
        limitations=['Uses existing reviewed patch, does not call an autonomous repair model.',
                     'Rollback is a version/activation decision, not a claim of production deployment.',
                     'Synthetic folded content control cannot establish hidden-node recall on all websites.',
                     'Image pixels and JavaScript-generated content remain unverified.'])
    OUT.mkdir(parents=True,exist_ok=True)
    old_source = (ROOT/TRUSTED[1][0]).read_text(encoding='utf-8')
    fixed_source = (ROOT/TRUSTED[2][0]).read_text(encoding='utf-8')
    patch = ''.join(difflib.unified_diff(old_source.splitlines(True),fixed_source.splitlines(True),
                                      fromfile=TRUSTED[1][0],tofile=TRUSTED[2][0]))
    (OUT/'accepted_patch.diff').write_text(patch,encoding='utf-8',newline='\n')
    report['accepted_patch_sha256'] = digest((OUT/'accepted_patch.diff').read_bytes())
    (OUT/'report.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf-8',newline='\n')
    (OUT/'active_version.json').write_text(json.dumps(active,ensure_ascii=False,indent=2)+'\n',encoding='utf-8',newline='\n')
    page = ['<!doctype html><meta charset="utf-8"><title>有限修复与回滚</title>',
            '<style>body{font:16px/1.8 sans-serif;max-width:1050px;margin:30px auto}pre{white-space:pre-wrap;background:#f4f6f8;padding:18px}strong{color:#08744e}</style>',
            '<h1>RSI 工程演示：接受修复，拒绝退化</h1>',
            '<p>复用已有对话 AI 编写并审核的 v1→v2 补丁，自动重放质量门禁。没有宣称云端模型已自主修复，也没有执行新模型生成代码。</p>',
            '<p><strong>接受：</strong>修复折叠容器中的正文漏提，3 篇历史开发回归不变，访谈问题保留。</p>',
            '<p><strong>拒绝并回滚：</strong>删掉首段和访谈问题的破坏性控制被门禁拒绝，活动版本仍为 v2。</p>',
            '<p>来源是已暴露历史页和明确合成控制；新封存测试页未读取。一次候选尝试一个门禁，不用质量换取更低轮数。</p>',
            '<pre>'+escape(json.dumps(report,ensure_ascii=False,indent=2))+'</pre>']
    (OUT/'index.html').write_text('\n'.join(page),encoding='utf-8',newline='\n')
    print('RSI REPLAY PASS: accepted=1 rejected=1 rollback=verified sealed_tests_read=0')
    print(OUT/'index.html')
    return report

if __name__ == '__main__':
    run()
