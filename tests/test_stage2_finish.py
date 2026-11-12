import copy
import unittest
from unittest.mock import patch

from learning.agent_io.finish_stage2 import (
    OUT, article_url, canonical, duplicate_check, extraction_task, frozen, read,
)
from learning.agent_io.review_pipeline import validate_review


class Stage2FinishTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.task, cls.evidence = extraction_task()

    def test_wrapped_url_is_decoded_without_tracking_query(self):
        wrapped = ('https://cj.sina.cn/article/norm_detail?url='
                   'https%3A%2F%2Ffinance.sina.com.cn%2Froll%2F2026-11-12%2Fdoc-abc123.shtml%3Ffrom%3Dtest')
        self.assertEqual(article_url(wrapped), 'https://finance.sina.com.cn/roll/2026-11-12/doc-abc123.shtml')
        self.assertIsNone(article_url('https://example.org/doc-abc123.shtml'))

    def test_frozen_rules_unchanged(self):
        self.assertEqual(read(OUT / 'protocol.json')['frozen'], frozen())

    def test_frozen_change_is_rejected(self):
        with patch('learning.agent_io.finish_stage2.frozen', return_value={}):
            with self.assertRaises(ValueError):
                extraction_task()

    def test_fixed_selection_has_no_known_url_and_two_snapshots(self):
        selection = read(OUT / 'selection.json')
        self.assertEqual(len(selection['pages']), 2)
        self.assertTrue(all(canonical(p['url']) not in selection['known_urls'] for p in selection['pages']))
        self.assertEqual([len(p['blocks']) for p in self.task['pages']], [104, 20])

    def test_source_table_is_not_silently_included_in_paragraph_output(self):
        table = self.evidence[1]['tables'][0]
        self.assertEqual(len(table['rows']), 5)
        self.assertTrue(all(len(row) == 3 for row in table['rows']))
        self.assertNotIn(table['xpath'], [b['xpath'] for b in self.task['pages'][1]['blocks']])
        self.assertFalse(self.evidence[0]['tables'])

    def test_saved_audit_preserves_raw_and_separates_editors(self):
        report = validate_review(self.task, read(OUT / 'new_ai_review.json'))
        self.assertTrue(report['accepted'])
        self.assertEqual([len(p['content_blocks']) for p in report['pages']], [103, 19])
        self.assertEqual([len(p['editor_blocks']) for p in report['pages']], [1, 1])
        for source, reviewed in zip(self.task['pages'], report['pages']):
            self.assertEqual(source['blocks'], reviewed['raw_blocks'])

    def test_audit_cannot_be_reused_for_another_batch(self):
        audit = copy.deepcopy(read(OUT / 'new_ai_review.json'))
        audit['review_task_id'] = 'other-batch'
        self.assertFalse(validate_review(self.task, audit)['accepted'])

    def test_new_content_not_duplicate_under_declared_check(self):
        result = duplicate_check(self.evidence)
        self.assertGreater(result['scanned_article_snapshots'], 0)
        self.assertFalse(any(p['exact_body_duplicate'] or p['near_duplicate'] for p in result['pages']))


if __name__ == '__main__':
    unittest.main()
