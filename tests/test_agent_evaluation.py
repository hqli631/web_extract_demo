import copy
import tempfile
import unittest
from pathlib import Path

from learning.agent_io.evaluate_batch import CONFIG, ROOT, evaluate, execute_case, read, sha, verify_freeze


class EvaluationBoundaryTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.config = read(CONFIG)
        cls.rules = read(ROOT / 'output/agent_io/candidate.json')['rules']

    def test_all_experiments_match_without_claiming_unseen_accuracy(self):
        result = evaluate(self.config)
        self.assertTrue(result['experiment_checks_pass'])
        self.assertEqual(result['unseen_page_count'], 0)
        self.assertIsNone(result['semantic_accuracy'])
        self.assertEqual(result['groups']['synthetic_probe'], 3)

    def test_nested_paragraph_is_missing_despite_nonempty_result(self):
        case = next(c for c in self.config['cases'] if c['id'] == 'nested_one')
        result = execute_case(case, self.rules)
        self.assertEqual(result['container_count'], 1)
        self.assertEqual(result['raw_block_count'], 22)
        self.assertEqual(result['status'], 'raw_count_mismatch')

    def test_wrapping_all_paragraphs_returns_empty_without_changing_source(self):
        case = next(c for c in self.config['cases'] if c['id'] == 'nested_all')
        before = sha(ROOT / case['source'])
        result = execute_case(case, self.rules)
        self.assertEqual(result['container_count'], 1)
        self.assertEqual(result['status'], 'empty_blocks')
        self.assertEqual(before, sha(ROOT / case['source']))

    def test_changed_snapshot_rejected_instead_of_refreezing(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            (root / 'sample.html').write_text('<p>changed</p>', encoding='utf-8')
            config = {'frozen_files': {'sample.html': '0' * 64}, 'cases': []}
            with self.assertRaises(ValueError):
                verify_freeze(config, root)

    def test_real_page_duplicate_rejected(self):
        config = copy.deepcopy(self.config)
        duplicate = copy.deepcopy(config['cases'][0])
        duplicate['id'] = 'pretend-new-page'
        duplicate['role'] = 'known_transfer'
        config['cases'].append(duplicate)
        with self.assertRaises(ValueError):
            verify_freeze(config)

    def test_rule_changes_detected(self):
        config = copy.deepcopy(self.config)
        config['frozen_files']['output/agent_io/candidate.json'] = '0' * 64
        with self.assertRaises(ValueError):
            verify_freeze(config)


if __name__ == '__main__':
    unittest.main()
