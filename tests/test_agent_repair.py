import copy
import unittest

from learning.agent_io.repair_review import apply_plan, feedback_for
from learning.agent_io.review_pipeline import OUT, build_task, read


class FeedbackRepairTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.task = build_task()
        cls.audit = read(OUT / 'review_bad_link.json')
        cls.feedback = feedback_for(cls.task, cls.audit)
        cls.plan = read(OUT / 'repair_plan.json')

    def test_repair_changes_only_one_decision_and_not_inputs(self):
        original = copy.deepcopy(self.audit)
        fixed, result = apply_plan(self.task, self.audit, self.feedback, self.plan)
        self.assertTrue(result['accepted'])
        self.assertEqual(self.audit, original)
        diffs = [(p['file'], a['index']) for p, q in zip(original['pages'], fixed['pages'])
                 for a, b in zip(p['decisions'], q['decisions']) if a != b]
        self.assertEqual(diffs, [('blog_01.html', 2)])
        for p, q in zip(original['pages'], fixed['pages']):
            for a, b in zip(p['decisions'], q['decisions']):
                self.assertEqual({k:a[k] for k in ['text','xpath','index']},
                                 {k:b[k] for k in ['text','xpath','index']})

    def test_feedback_has_machine_readable_evidence(self):
        issue = self.feedback['issue_records'][0]
        self.assertEqual(issue['code'], 'rubric_conflict')
        self.assertEqual(issue['expected'], {'action':'keep','criterion':'R4'})
        self.assertEqual(issue['text'], self.audit['pages'][0]['decisions'][1]['text'])

    def test_stale_plan_and_feedback_rejected(self):
        for field in ['input_audit_sha256', 'feedback_sha256', 'review_task_id']:
            plan = copy.deepcopy(self.plan)
            plan[field] = 'old'
            with self.subTest(field=field), self.assertRaises(ValueError):
                apply_plan(self.task, self.audit, self.feedback, plan)
        feedback = copy.deepcopy(self.feedback)
        feedback['issues'] = []
        with self.assertRaises(ValueError):
            apply_plan(self.task, self.audit, feedback, self.plan)

    def test_rewritten_text_or_wrong_before_rejected(self):
        for mode in ['text', 'before']:
            plan = copy.deepcopy(self.plan)
            if mode == 'text':
                plan['changes'][0]['after']['text'] = 'rewritten'
            else:
                plan['changes'][0]['before']['reason'] = 'not current'
            with self.subTest(mode=mode), self.assertRaises(ValueError):
                apply_plan(self.task, self.audit, self.feedback, plan)

    def test_deviation_and_duplicate_rejected(self):
        for mode in ['wrong_action', 'duplicate']:
            plan = copy.deepcopy(self.plan)
            if mode == 'wrong_action':
                plan['changes'][0]['after'].update(action='exclude', criterion='R2')
            else:
                plan['changes'].append(copy.deepcopy(plan['changes'][0]))
            with self.subTest(mode=mode), self.assertRaises(ValueError):
                apply_plan(self.task, self.audit, self.feedback, plan)

    def test_unrelated_change_is_rejected(self):
        plan = copy.deepcopy(self.plan)
        change = copy.deepcopy(plan['changes'][0])
        change['index'] = 3
        change['before'] = copy.deepcopy(self.audit['pages'][0]['decisions'][2])
        plan['changes'].append(change)
        with self.assertRaises(ValueError):
            apply_plan(self.task, self.audit, self.feedback, plan)


if __name__ == '__main__':
    unittest.main()
