import tempfile
import unittest
from pathlib import Path

from xpath_batch import extract_page
from xpath_quality import inspect_page


class XPathQualityTests(unittest.TestCase):
    def audit(self, source, block_xpath):
        rules = {'title_xpath': '//h1', 'container_xpath': '//article',
                 'block_xpath': block_xpath}
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / 'sample.html'
            path.write_text(source, encoding='utf-8')
            result = extract_page(path, rules)
            return {c['id']: c for c in inspect_page(path, rules, result)['checks']}

    def test_finds_nested_paragraph_and_caption_without_editor(self):
        checks = self.audit('<h1>T</h1><article><p>A</p><div><p>B</p></div>'
            '<div class="pictext">C</div><div class="adEditor"><p>E</p></div></article>', './p')
        self.assertEqual([e['text'] for e in checks['candidate_coverage']['evidence']], ['B', 'C'])

    def test_detects_editor_in_selected_parent(self):
        checks = self.audit('<h1>T</h1><article><p>A</p><div class="adEditor">E</div></article>', '.')
        self.assertEqual(checks['known_exclusions']['status'], 'needs_review')

    def test_detects_overlapping_parent_and_child(self):
        checks = self.audit('<h1>T</h1><article><div><p>A</p></div></article>', './div | .//p')
        self.assertEqual(checks['order_overlap']['status'], 'needs_review')

    def test_keeps_semantic_and_image_judgment_unknown(self):
        checks = self.audit('<h1>T</h1><article><p>A</p><img src="a.png"></article>', './p')
        self.assertEqual(checks['candidate_coverage']['status'], 'structural_pass')
        self.assertEqual(checks['semantic_quality']['status'], 'unknown')
        self.assertEqual(checks['image_text']['status'], 'unknown')


if __name__ == '__main__':
    unittest.main()
