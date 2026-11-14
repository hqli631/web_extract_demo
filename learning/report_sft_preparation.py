"""Build a readable preparation report; optionally record real tokenizer evidence."""
import argparse
import hashlib
import importlib.metadata
import json
from html import escape
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from learning.prepare_sft_data import check_existing
from training.minimal_sft import load_materials, prepare_tokens, material_fingerprint

OUT = ROOT / 'output/stage5/unit2/sft_prep'


def run(record=False):
    check_existing()
    cfg = json.loads((ROOT / 'training/minimal_sft.json').read_text(encoding='utf-8'))
    paths, rows = load_materials(cfg)
    fingerprint = material_fingerprint(cfg, paths)
    evidence_path = OUT / 'tokenizer_evidence.json'
    if record:
        tokenizer, encoded, lengths = prepare_tokens(cfg, rows)
        for entry in lengths:
            item = encoded[entry['split']][entry['row']]
            n = entry['prompt_tokens']
            assert item['labels'][:n] == [-100] * n
            assert item['labels'][n:] == item['input_ids'][n:]
            entry['prompt_mask_verified'] = True
            entry['full_assistant_retained'] = True
        evidence = dict(fingerprint=fingerprint, model_id=cfg['model_id'], revision=cfg['model_revision'],
                        revision_source='https://huggingface.co/api/models/' + cfg['model_id'],
                        observed_date='2026-11-14', tokenizer_class=type(tokenizer).__name__,
                        packages={p: importlib.metadata.version(p) for p in ('transformers','tokenizers','jinja2')},
                        lengths=lengths, max_seq_length=cfg['max_seq_length'],
                        model_weights_downloaded=False, optimizer_steps=0, gpu_tested=False)
        evidence_path.write_text(json.dumps(evidence, ensure_ascii=False, indent=2), encoding='utf-8')
    evidence = json.loads(evidence_path.read_text(encoding='utf-8'))
    if evidence['fingerprint'] != fingerprint:
        raise ValueError('Tokenizer evidence is stale: data/config changed; rerun --record-tokenizer')
    refs = json.loads((OUT / 'reference_checks.json').read_text(encoding='utf-8'))
    for page in refs['pages']:
        for field, digest_field in [('file','source_sha256'),('reference','reference_sha256')]:
            if hashlib.sha256((ROOT / page[field]).read_bytes()).hexdigest() != page[digest_field]:
                raise ValueError('Reference evidence is stale')
    status = dict(materials='ready_for_rental_decision', train_tasks=1, dev_tasks=1,
                  independent_test=False, historical_pages=6, reference_checks=len(refs['pages']),
                  tokenizer_preflight='passed_real_tokenizer', max_seq_length=cfg['max_seq_length'],
                  gpu_training='not_started', quality_improvement='not_proven',
                  independent_reward_calibration='unfinished', paid_instances_started=0,
                  next_action='Confirm actual rental specification, image, trial budget and shutdown rules')
    (OUT / 'readiness.json').write_text(json.dumps(status, ensure_ascii=False, indent=2), encoding='utf-8')
    values = [('状态与边界', status), ('真实分词与loss屏蔽证据', evidence), ('可信历史参考复验', refs)]
    page = ['<!doctype html><html lang="zh"><meta charset="utf-8"><title>5.2 SFT训练准备</title>',
            '<style>body{font:16px/1.8 sans-serif;max-width:1050px;margin:32px auto;padding:0 22px;color:#223}pre{white-space:pre-wrap;background:#f2f5f8;padding:18px}a{color:#1759ad}td,th{padding:8px;border:1px solid #ccc}table{border-collapse:collapse}</style>',
            '<h1>5.2：SFT训练材料已准备，等待租赁决策</h1>',
            '<p>岗位任务：同簇少量DOM → Actor生成Python/XPath → CPU复用。训练目标是代码生成模型的LoRA参数。</p>',
            '<p><strong>1条train＋1条dev、6篇历史页，只用于训练管线冒烟。没有未见测试，没有训练更新，也没有质量提升结论。</strong></p>',
            '<p><a href="../../../../docs/STAGE5_SFT_PREPARATION.md">操作与知识说明</a> · <a href="train.jsonl">train.jsonl</a> · <a href="dev.jsonl">dev.jsonl</a> · <a href="manifest.json">来源与数据分工</a></p>',
            '<table><tr><th>集合</th><th>提示token</th><th>监督token</th><th>总token</th></tr>']
    for item in evidence['lengths']:
        page.append('<tr>' + ''.join('<td>'+escape(str(item[k]))+'</td>' for k in ('split','prompt_tokens','supervised_tokens','total_tokens')) + '</tr>')
    page += ['</table><p>8192窗口保留完整输入与目标；prompt labels=-100，assistant和结束标记参与loss。字符数不是token数。</p>',
             '<p>下一步才确定短租机器、实际空闲显存、CUDA镜像、费用上限和停止规则。未购买、未创建实例。GPU路径尚待实测。</p>']
    for label, value in values:
        page += ['<details><summary>'+label+'</summary><pre>'+escape(json.dumps(value, ensure_ascii=False, indent=2))+'</pre></details>']
    page += ['</html>']
    (OUT / 'index.html').write_text('\n'.join(page), encoding='utf-8')
    print('PREPARATION PASS: 2 historical tasks; 6 reference pages; real-tokenizer masking/length verified.')
    print('STOP: rental configuration decision; GPU training not started.')
    print(OUT / 'index.html')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--record-tokenizer', action='store_true')
    run(parser.parse_args().record_tokenizer)
