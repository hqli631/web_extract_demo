import hashlib
import tempfile
import unittest
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from ai_review import prepare, validate, corrected_candidates, render
from dom_evidence import make_queue


class AIReviewTests(unittest.TestCase):
    def fixture(self, root, target='课程推荐'):
        (root / 'samples').mkdir()
        path = root / 'samples' / 'a.html'
        path.write_text('<html><body><article><p>' + '正文论述内容。' * 25 + '</p><div><h2>课程推荐</h2></div></article></body></html>', encoding='utf-8')
        source = path.read_text(encoding='utf-8')
        result = dict(file='a.html', snapshot=hashlib.sha256(path.read_bytes()).hexdigest(),
                      current_chars=200, baseline_chars=150, current_only=[target], baseline_only=[])
        return prepare(make_queue(result, source))

    def test_valid_noise_decision_produces_candidate_without_changing_source(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            pack = self.fixture(root)
            response = {'decisions':[dict(id=pack['tasks'][0]['id'], decision='noise', reason='课程推广模块')]}
            report = validate(pack, response, root)
            candidates = corrected_candidates(report, root)
            self.assertNotIn('课程推荐', candidates[0]['content'])
            self.assertIn('正文论述', candidates[0]['content'])
            self.assertIn('课程推荐', (root / 'samples/a.html').read_text(encoding='utf-8'))
            self.assertFalse(report['records'][0]['reviewed'])
            with self.assertRaises(ValueError):
                validate(pack, {'decisions':response['decisions'] * 2}, root)
            (root / 'samples/a.html').write_text('changed', encoding='utf-8')
            with self.assertRaises(ValueError):
                validate(pack, response, root)

    def test_partial_text_and_uncertain_decisions_do_not_change_whole_block(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            pack = self.fixture(root, '课程')
            response = {'decisions':[dict(id=pack['tasks'][0]['id'], decision='noise', reason='仅匹配局部')]}
            report = validate(pack, response, root)
            self.assertFalse(report['records'][0]['applicable'])
            candidates = corrected_candidates(report, root)
            self.assertIn('课程推荐', candidates[0]['content'])
            self.assertEqual(candidates[0]['applied_region_count'], 0)
            self.assertEqual(candidates[0]['pending'][0]['reason'], 'uncertain_or_partial_block')
            response['decisions'][0]['decision'] = 'uncertain'
            self.assertFalse(validate(pack, response, root)['records'][0]['applicable'])

    def test_unknown_or_invented_decision_rejected(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            pack = self.fixture(root)
            with self.assertRaises(ValueError):
                validate(pack, {'decisions':[dict(id='invented', decision='body', reason='x')]}, root)
            with self.assertRaises(ValueError):
                validate(pack, {'decisions':[dict(id=pack['tasks'][0]['id'], decision='execute', reason='x')]}, root)

    def test_report_distinguishes_applied_from_changed_and_escapes_notes(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            pack = self.fixture(root)
            report = validate(pack, {'decisions':[dict(id=pack['tasks'][0]['id'], decision='body', reason='保留')]}, root)
            candidates = corrected_candidates(report, root)
            self.assertEqual(candidates[0]['applied_region_count'], 1)
            self.assertEqual(candidates[0]['changed_region_count'], 0)
            report['page_notes'] = {'a.html':'<script>alert(1)</script>'}
            result = render(report, candidates)
            self.assertNotIn('<script>', result)
            self.assertIn('&lt;script&gt;', result)


if __name__ == '__main__':
    unittest.main()
