"""Recheck repository-reviewed historical references, never model-generated files."""
import hashlib
import importlib.util
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from learning.run_cluster_generation import check_code, validate


def run():
    task_path = ROOT / 'output/stage3/generation/task.json'
    task = json.loads(task_path.read_text(encoding='utf-8'))
    report = {'purpose': 'historical reference engineering checks; NOT independent semantic gold',
              'model_calls': 0, 'optimizer_steps': 0, 'pages': [],
              'limits': ['Only reviewed repository references execute in this command.',
                         'AST checks are not an OS sandbox; never pass generated candidates here.',
                         'All six source pages are historical/exposed, not unseen evaluation.',
                         'Original-title/caption policy v2 was a later postprocessor, not these targets.',
                         'Contract/quote/order success does not prove complete or pure body extraction.',
                         'Image pixels, JavaScript-loaded content and OCR are outside this contract.']}
    for cluster in task['clusters']:
        name = cluster['cluster_id'].split('_')[0]
        path = ROOT / 'learning/generated' / (name + '_v2.py')
        source = path.read_text(encoding='utf-8')
        check_code(source)
        spec = importlib.util.spec_from_file_location('trusted_' + name, path)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        for page in cluster['inputs']:
            raw = (ROOT / page['file']).read_bytes()
            digest = hashlib.sha256(raw).hexdigest()
            if digest != page['sha256']:
                raise ValueError('historical source changed: ' + page['file'])
            output = module.extract(raw)
            validate(output, raw, allow_production_credit=True)
            item = {'cluster_id': cluster['cluster_id'], 'file': page['file'],
                    'source_sha256': digest, 'reference': path.relative_to(ROOT).as_posix(),
                    'reference_sha256': hashlib.sha256(path.read_bytes()).hexdigest(),
                    'contract_quote_order': 'pass', 'semantic_gold': False,
                    'blocks': len(output['blocks']), 'metadata': len(output['metadata']),
                    'excluded': len(output['excluded']),
                    'output_sha256': hashlib.sha256(json.dumps(output, ensure_ascii=False, sort_keys=True).encode()).hexdigest()}
            report['pages'].append(item)
            print(f"REFERENCE PASS: {Path(page['file']).name}; blocks={item['blocks']}, metadata={item['metadata']}, excluded={item['excluded']}")
    out = ROOT / 'output/stage5/unit2/sft_prep'
    out.mkdir(parents=True, exist_ok=True)
    (out / 'reference_checks.json').write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
    print('No model generation or training performed; semantic quality remains separately gated.')


if __name__ == '__main__':
    run()
