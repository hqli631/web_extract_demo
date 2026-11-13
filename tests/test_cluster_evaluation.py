import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from learning.benchmark_cluster_cpu import benchmark, cost_scenario, _percentile
from learning import run_cluster_evaluation as evaluation


class ClusterEvaluationTests(unittest.TestCase):
    def test_benchmark_keeps_failed_attempts(self):
        code="def extract(data):\n    if data==b'bad': raise ValueError('fixture')\n    return {'blocks': []}\n"
        cases=[dict(cluster_id='x',file=f,data=data,source=code) for f,data in [('ok',b'ok'),('bad',b'bad')]]
        result=benchmark(cases,repeats=2,warmups=1)
        self.assertEqual(result['summary']['attempts'],4)
        self.assertEqual(result['summary']['failures'],2)
        self.assertEqual(result['summary']['execution_failure_rate'],.5)
        self.assertEqual(len(result['warmup_errors']),1)
        self.assertEqual(result['input_bytes_per_batch'],5)

    def test_cost_and_nearest_rank(self):
        result=cost_scenario(100,10,0.36,1,2)
        self.assertAlmostEqual(result['total_cost'],12.01)
        self.assertAlmostEqual(result['amortized_cost_per_page'],.1201)
        self.assertEqual(_percentile([4,1,3,2],.5),2)
        self.assertEqual(_percentile([4,1,3,2],.95),4)
        for n in [0,-1,True,1.5]:
            with self.assertRaises(ValueError):
                cost_scenario(n,1,1,1,1)
        with self.assertRaises(ValueError):
            cost_scenario(1,-1,1,1,1)

    def test_freeze_verifier_rejects_changed_candidate(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder)
            candidate=root/'candidate.py'
            candidate.write_bytes(b'old')
            split=root/'split.json'
            split.write_text('{}',encoding='utf-8')
            protocol=root/'protocol.json'
            protocol.write_text(json.dumps({'split_sha256':evaluation.digest(split.read_bytes()),
                                           'frozen_files':{'candidate.py':evaluation.digest(candidate.read_bytes())}}),encoding='utf-8')
            with patch.object(evaluation,'ROOT',root),patch.object(evaluation,'SPLIT',split),patch.object(evaluation,'PROTOCOL',protocol):
                evaluation.verify()
                candidate.write_bytes(b'new')
                with self.assertRaisesRegex(ValueError,'frozen file changed'):
                    evaluation.verify()


if __name__=='__main__':
    unittest.main()
