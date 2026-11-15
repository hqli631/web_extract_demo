"""Verify real-run receipt; never execute generated code."""
import ast
import hashlib
from html import escape
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'output/stage5/unit2/cloud_run_20261115'
ARCHIVE_SHA = '961f00e0226320ac43b23b1549043681771fe77ab738f8bca89bbc1359f2cfc0'


def inspect_text(text):
    issues = []
    code = text.strip()
    fence = chr(96) * 3
    if code.startswith(fence):
        issues.append('Markdown fence violates Python-source-only instruction')
        code = code.split('\n', 1)[1].split(fence, 1)[0]
    try:
        tree = ast.parse(code)
    except SyntaxError as exc:
        return dict(python_parse=False, issues=issues + [str(exc)], executed=False)
    keys = {'title', 'blocks', 'metadata', 'excluded', 'warnings'}
    returns = [n.value for n in ast.walk(tree) if isinstance(n, ast.Return) and isinstance(n.value, ast.Dict)]
    if returns and {k.value for k in returns[-1].keys if isinstance(k, ast.Constant)} != keys:
        issues.append('literal return keys differ from output contract')
    for node in ast.walk(tree):
        if isinstance(node, ast.Assign) and isinstance(node.value, ast.Dict):
            for name in node.targets:
                if isinstance(name, ast.Name) and name.id in {'metadata', 'excluded', 'warnings'}:
                    issues.append(name.id + ' is dict; contract requires list')
    return dict(python_parse=True, issues=sorted(set(issues)), executed=False,
                quality='not_accepted_static_contract_defects', semantic_evaluation=False)


def run():
    archive = OUT / 'training_receipt.tar.gz'
    if hashlib.sha256(archive.read_bytes()).hexdigest() != ARCHIVE_SHA:
        raise ValueError('archive differs from server sha256 receipt')
    receipt = OUT / 'receipt'
    cloud = receipt / 'output/stage5/unit2/cloud_sft'
    read = lambda p: json.loads(p.read_text(encoding='utf-8'))
    proof = read(cloud / 'update_proof.json')
    assert proof['optimizer_steps'] == 1 and proof['trainable_parameters'] > 0
    assert proof['adapter_reload_verified'] and proof['adapter_serialization_verified']
    assert max(proof['parameter_max_abs_delta'].values()) > 0
    for name, digest in proof['data_sha256'].items():
        local = ROOT / ('output/stage5/unit2/sft_prep/' + name + '.jsonl')
        assert hashlib.sha256(local.read_bytes()).hexdigest() == digest
    before, after = [read(cloud / (name + '_generation.json')) for name in ('before', 'after')]
    assert before['config_sha256'] == after['config_sha256']
    assert before['model_revision'] == after['model_revision'] == proof['model_revision']
    comparison = []
    for a, b in zip(before['outputs'], after['outputs'], strict=True):
        assert a['input_sha256'] == b['input_sha256']
        comparison.append(dict(split=a['split'], same_text=a['text'] == b['text'],
                               before_tokens=a['new_tokens'], after_tokens=b['new_tokens'],
                               before_static=inspect_text(a['text']), after_static=inspect_text(b['text'])))
    values = {'date': '2026-11-15', 'scope': 'single-step historical SFT pipeline smoke',
              'archive_sha256': ARCHIVE_SHA, 'environment': read(receipt / 'evidence/environment.json'),
              'proof': proof, 'comparison': comparison, 'quality_improvement_proven': False,
              'known_result': 'Generated code has static output-contract defects before and after; not accepted.',
              'processes_finished': True, 'rental_instance_stopped': False,
              'billing': 'unknown; ending SSH/GPU processes does not stop platform billing',
              'limits': ['one historical train task and one historical dev task; no unseen test',
                         'No generated candidate executed; SFT with LoRA, not GRPO',
                         '1.6268 is one-step loss, not a measured loss-decrease curve',
                         'Independent reward calibration unfinished',
                         'Remote executed script retained; differs only in dev finite-loss error wording']}
    (OUT / 'summary.json').write_text(json.dumps(values, ensure_ascii=False, indent=2), encoding='utf-8')
    for source, dest in [(cloud/'update_proof.json', 'update_proof.json'),
                         (cloud/'before_generation.json','before_generation.json'),
                         (cloud/'after_generation.json','after_generation.json'),
                         (receipt/'evidence/environment.json','environment.json')]:
        (OUT/dest).write_bytes(source.read_bytes())
    page = ['<!doctype html><meta charset="utf-8"><title>首次真实LoRA更新</title>',
            '<style>body{font:16px/1.8 sans-serif;max-width:1000px;margin:30px auto;padding:20px}pre{white-space:pre-wrap;background:#f3f5f8;padding:18px}</style>',
            '<h1>首次真实 LoRA SFT：参数更新及重载通过</h1>',
            '<p>Ubuntu22.04、RTX3090 24GB、torch2.8.0+cu128；1 optimizer step，540672可训练参数。训练loss 1.626846，历史dev loss 1.830495。</p>',
            '<p>峰值allocated约14.47GiB、reserved约17.02GiB。保存校验和新进程重载通过；资料包已下载并核对SHA256。</p>',
            '<p><strong>生成代码仍有输出契约错误，尚不可采用。一次更新成功不等于正文抽取质量提高；本轮没有GRPO或未见测试。</strong></p>',
            '<p>GPU任务已结束；服务器实例未关闭，仍可能计费。平台停机与存储计费需要单独处理。</p>',
            '<p><a href="../../../../docs/STAGE5_CLOUD_SMOKE.md">本次操作与学习回顾</a></p>']
    for name in ('environment','proof','comparison','limits'):
        page += ['<details><summary>'+escape(name)+'</summary><pre>'+escape(json.dumps(values[name], ensure_ascii=False, indent=2))+'</pre></details>']
    (OUT/'index.html').write_text('\n'.join(page), encoding='utf-8')
    print('REAL SFT PASS: optimizer_step=1, adapter changed, serialization and reload verified.')
    print('QUALITY: not improved/proven; static contract defects; outputs not executed.')
    print('Archive SHA256 matches remote receipt. GPU processes ended; rental instance not stopped.')


if __name__ == '__main__':
    run()
