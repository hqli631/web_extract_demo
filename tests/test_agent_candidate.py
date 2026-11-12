"""候选规则的协议、快照和选择范围边界。"""
import copy
import json
import tempfile
import unittest
from pathlib import Path

from learning.agent_io.check_candidate import ROOT, validate


class CandidateContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.task = json.loads((ROOT / 'output/agent_io/task.json').read_text(encoding='utf-8'))
        cls.candidate = json.loads((ROOT / 'output/agent_io/candidate.json').read_text(encoding='utf-8'))

    def run_candidate(self, change=None):
        candidate = copy.deepcopy(self.candidate)
        if change:
            change(candidate)
        return validate(self.task, candidate, ROOT / 'samples')

    def test_valid_and_pending(self):
        report = self.run_candidate()
        self.assertTrue(report['accepted'])
        self.assertEqual([p['actual_count'] for p in report['pages']], [45, 23])
        self.assertEqual(report['semantic_review'], 'pending')
        self.assertFalse(report['published'])

    def test_old_task(self):
        self.assertFalse(self.run_candidate(lambda c: c.update(task_id='old-task'))['accepted'])

    def test_missing_explanation(self):
        self.assertFalse(self.run_candidate(lambda c: c['explanations'].pop('block_xpath'))['accepted'])

    def test_wrong_snapshot_map(self):
        report = self.run_candidate(lambda c: c['source_sha256'].update({'blog_01.html': '0' * 64}))
        self.assertFalse(report['accepted'])

    def test_local_snapshot_changed(self):
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp)
            for p in self.task['samples']:
                data = (ROOT / 'samples' / p['file']).read_bytes()
                (target / p['file']).write_bytes(data + b'<!-- changed -->')
            self.assertFalse(validate(self.task, self.candidate, target)['accepted'])

    def test_invalid_xpath_and_scalar_title(self):
        for expression in ['//*[', 'count(//h1)']:
            with self.subTest(expression=expression):
                self.assertFalse(self.run_candidate(lambda c: c['rules'].update(title_xpath=expression))['accepted'])

    def test_scope_escape_and_text_result(self):
        for expression in ['//p', './p | //h1', './p/text()']:
            with self.subTest(expression=expression):
                self.assertFalse(self.run_candidate(lambda c: c['rules'].update(block_xpath=expression))['accepted'])

    def test_early_cleaning(self):
        expression = "./p[not(contains(concat(' ', normalize-space(@class), ' '), ' article-editor '))]"
        report = self.run_candidate(lambda c: c['rules'].update(block_xpath=expression))
        self.assertFalse(report['accepted'])
        self.assertEqual(report['pages'][0]['actual_count'], 44)
        self.assertEqual(report['pages'][0]['expected_count'], 45)
        self.assertEqual(len(report['pages'][0]['missing_xpaths']), 1)


if __name__ == '__main__':
    unittest.main()
