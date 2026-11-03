import json
import unittest
from pathlib import Path

from xpath_batch import extract_page, signature
from xpath_corrections import compose_cleaned
from xpath_semantic import find_review


ROOT = Path(__file__).resolve().parents[1]


class RealSampleCorrectionIntegrationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.rules = json.loads((ROOT / 'xpath_rules.json').read_text(encoding='utf-8-sig'))
        cls.reviews = json.loads((ROOT / 'xpath_semantic_reviews.json').read_text(encoding='utf-8'))
        baseline = json.loads((ROOT / 'output/xpath_practice/baseline.json').read_text(encoding='utf-8'))
        cls.baseline = {page['file']: page for page in baseline['pages']}

    def load_page(self, filename):
        page = extract_page(ROOT / 'samples' / filename, self.rules)
        page['semantic_review'] = find_review(page, self.rules, self.reviews)
        return page

    def test_raw_extraction_remains_equal_to_frozen_baseline(self):
        for filename, baseline in self.baseline.items():
            with self.subTest(filename=filename):
                raw = self.load_page(filename)
                self.assertEqual(signature(raw), signature(baseline))
                self.assertEqual(raw['source_sha256'], baseline['source_sha256'])

    def test_confirmed_bylines_move_to_author_fields_only(self):
        expected = {
            'xpath_practice_02.html': ('薄雯雯', '中新网记者 薄雯雯'),
            'xpath_practice_03.html': ('孙翔', '中新社记者 孙翔'),
        }
        for filename, (name, byline) in expected.items():
            with self.subTest(filename=filename):
                page = self.load_page(filename)
                raw_snapshot = json.dumps(page['blocks'], ensure_ascii=False, sort_keys=True)
                cleaned = compose_cleaned(page)
                self.assertEqual(cleaned['status'], 'applied')
                self.assertEqual([(a['name'], a['byline']) for a in cleaned['authors']], [(name, byline)])
                self.assertTrue(cleaned['conservation_check'])
                self.assertEqual(json.dumps(page['blocks'], ensure_ascii=False, sort_keys=True), raw_snapshot)
                self.assertNotIn(byline, [block['text'] for block in cleaned['blocks']])

    def test_interview_questions_and_captions_remain_after_cleaning(self):
        page = self.load_page('xpath_practice_03.html')
        raw_questions = [block['text'] for block in page['blocks']
                         if block['type'] == 'paragraph' and block['text'].startswith('中新社记者：')]
        cleaned = compose_cleaned(page)
        clean_questions = [block['text'] for block in cleaned['blocks']
                           if block['type'] == 'paragraph' and block['text'].startswith('中新社记者：')]
        self.assertEqual(len(raw_questions), 3)
        self.assertEqual(clean_questions, raw_questions)
        self.assertEqual(sum(block['type'] == 'caption' for block in cleaned['blocks']), 4)

    def test_page_without_confirmed_byline_has_neutral_note(self):
        cleaned = compose_cleaned(self.load_page('xpath_practice.html'))
        self.assertEqual(cleaned['status'], 'unchanged')
        self.assertEqual(cleaned['authors'], [])
        self.assertIn('没有需要执行', cleaned['note'])


if __name__ == '__main__':
    unittest.main()

