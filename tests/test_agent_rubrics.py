import copy
import json
import unittest

from learning.agent_io.review_pipeline import OUT, build_task, validate_review


class RubricsReviewTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.task = build_task()
        cls.audit = json.loads((OUT / 'review_ai.json').read_text(encoding='utf-8'))

    def altered(self, mutate):
        audit = copy.deepcopy(self.audit)
        mutate(audit)
        return validate_review(self.task, audit)

    def test_valid_preserves_evidence_and_separates_editor(self):
        result = validate_review(self.task, self.audit)
        self.assertTrue(result['accepted'])
        first, second = result['pages']
        self.assertEqual([b['index'] for b in first['content_blocks']], list(range(2, 45)))
        self.assertEqual([b['index'] for b in first['editor_blocks']], [45])
        self.assertEqual([b['index'] for b in first['excluded_blocks']], [1])
        self.assertEqual(first['raw_blocks'], self.task['pages'][0]['blocks'])
        self.assertEqual(len(second['content_blocks']), 23)
        self.assertFalse(result['published'])

    def test_link_deletion_rejected_without_partial_output(self):
        audit = json.loads((OUT / 'review_bad_link.json').read_text(encoding='utf-8'))
        result = validate_review(self.task, audit)
        self.assertFalse(result['accepted'])
        self.assertEqual(result['pages'], [])
        self.assertTrue(any('#2' in x and 'keep/R4' in x for x in result['issues']))

    def test_wrong_task_rejected(self):
        self.assertFalse(self.altered(lambda a: a.update(review_task_id='old'))['accepted'])

    def test_missing_duplicate_and_reordered_decisions_rejected(self):
        for mode in ['missing', 'duplicate', 'reorder']:
            def change(a):
                entries = a['pages'][0]['decisions']
                if mode == 'missing':
                    entries.pop()
                elif mode == 'duplicate':
                    entries[2] = entries[1]
                else:
                    entries[1], entries[2] = entries[2], entries[1]
            with self.subTest(mode=mode):
                self.assertFalse(self.altered(change)['accepted'])

    def test_rewritten_text_rejected(self):
        def change(a):
            a['pages'][0]['decisions'][1]['text'] += ' changed'
        self.assertFalse(self.altered(change)['accepted'])

    def test_disclosure_deletion_rejected(self):
        def change(a):
            a['pages'][0]['decisions'][43].update(action='exclude', criterion='R2')
        self.assertFalse(self.altered(change)['accepted'])

    def test_uncertain_blocks_cleanup(self):
        def change(a):
            a['pages'][1]['decisions'][0].update(action='uncertain', criterion='R6')
        self.assertFalse(self.altered(change)['accepted'])

    def test_editor_as_author_is_not_allowed(self):
        def change(a):
            a['pages'][0]['decisions'][44].update(action='author')
        self.assertFalse(self.altered(change)['accepted'])

    def test_rubric_change_invalidates_old_audit(self):
        task = copy.deepcopy(self.task)
        task['review_task_id'] = 'new-task-for-new-rubric'
        self.assertFalse(validate_review(task, self.audit)['accepted'])


if __name__ == '__main__':
    unittest.main()
