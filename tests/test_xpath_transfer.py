import json
import tempfile
import unittest
from pathlib import Path

from xpath_transfer import run


ROOT = Path(__file__).resolve().parents[1]


class XPathTransferTests(unittest.TestCase):
    def test_historical_pages_are_marked_retrospective_not_unseen(self):
        baseline_path = ROOT / 'output/xpath_practice/baseline.json'
        baseline_before = baseline_path.read_bytes()
        with tempfile.TemporaryDirectory() as folder:
            page, json_path, html_path = run(
                ROOT / 'samples/collected_4b026cde5c5744c1.html', folder
            )
            self.assertEqual(page['container_count'], 1)
            self.assertEqual(len(page['blocks']), 7)
            self.assertEqual(sum(block['type'] == 'caption' for block in page['blocks']), 1)
            self.assertEqual(page['review_state'], 'not_reviewed')
            self.assertEqual(page['baseline_state'], 'not_compared')
            self.assertEqual(page['transfer_evidence']['status'], 'retrospective_match')
            self.assertEqual(page['transfer_evidence']['reference_kind'], 'historical_development_audit')
            self.assertIn('不是未见页面或盲测', page['transfer_evidence']['note'])
            report = json.loads(json_path.read_text(encoding='utf-8'))
            self.assertEqual(report['source_sha256'], page['source_sha256'])
            self.assertIn('历史审核兼容性检查', html_path.read_text(encoding='utf-8'))
        self.assertEqual(baseline_path.read_bytes(), baseline_before)

    def test_second_historical_page_matches_six_reviewed_paragraphs(self):
        with tempfile.TemporaryDirectory() as folder:
            page, _, _ = run(ROOT / 'samples/collected_4fdd3a7b48c5a575.html', folder)
        evidence = page['transfer_evidence']
        self.assertEqual(evidence['status'], 'retrospective_match')
        self.assertEqual(evidence['expected_paragraphs'], 6)
        self.assertEqual(evidence['actual_paragraphs'], 6)
        self.assertEqual(evidence['ordered_text_match'], True)
        self.assertFalse(any('编辑' in block['text'] for block in page['blocks']))


if __name__ == '__main__':
    unittest.main()

