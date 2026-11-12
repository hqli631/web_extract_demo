import copy
import unittest

from learning.agent_io.score_body_quality import OUT, build_task, evaluate, read, score_case


class BodyQualityScoreTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.task = build_task()
        cls.responses = read(OUT / 'model_response.json')

    def test_full_frozen_task_and_score_contrasts(self):
        self.assertEqual(read(OUT / 'task.json'), self.task)
        report = evaluate(self.task, self.responses)
        self.assertEqual([c['score'] for c in report['cases']], [1.0, .8, .8, 1.0])
        self.assertEqual(report['cases'][2]['critical_failed'], ['Q3'])
        self.assertEqual(report['cases'][2]['adoption'], 'reject_complete_article')
        self.assertEqual(report['cases'][1]['adoption'], 'below_threshold')
        self.assertEqual(report['training_updates'], 0)

    def test_unknown_has_no_reward_and_does_not_shrink_denominator(self):
        response = copy.deepcopy(self.responses['cases'][0])
        response['answers'][2]['verdict'] = 'unknown'
        result = score_case(self.task, self.task['cases'][0], response)
        self.assertTrue(result['response_valid'])
        self.assertIsNone(result['raw_score'])
        self.assertIsNone(result['score'])
        self.assertIsNone(result['reward_signal'])
        self.assertEqual(result['adoption'], 'needs_evidence')

    def test_fabricated_or_unknown_evidence_prevents_scoring(self):
        for key, value in [('quote', 'not present in source'), ('id', 'not-a-source')]:
            response = copy.deepcopy(self.responses['cases'][0])
            response['answers'][0]['source_evidence'][0][key] = value
            with self.subTest(key=key):
                result = score_case(self.task, self.task['cases'][0], response)
                self.assertFalse(result['response_valid'])
                self.assertIsNone(result['reward_signal'])

    def test_missing_duplicate_or_illegal_verdict_not_a_low_score(self):
        for mode in ['missing', 'duplicate', 'verdict']:
            response = copy.deepcopy(self.responses['cases'][0])
            if mode == 'missing':
                response['answers'].pop()
            elif mode == 'duplicate':
                response['answers'][1] = response['answers'][0]
            else:
                response['answers'][0]['verdict'] = 'probably'
            with self.subTest(mode=mode):
                result = score_case(self.task, self.task['cases'][0], response)
                self.assertFalse(result['response_valid'])
                self.assertIsNone(result['score'])

    def test_stale_task_and_execution_error_not_semantic_failure(self):
        response = copy.deepcopy(self.responses['cases'][0])
        response['task_id'] = 'stale'
        self.assertIsNone(score_case(self.task, self.task['cases'][0], response)['score'])
        case = copy.deepcopy(self.task['cases'][0])
        case['execution_status'] = 'failed'
        self.assertIsNone(score_case(self.task, case, self.responses['cases'][0])['score'])

    def test_empty_reason_and_missing_output_evidence_invalid(self):
        response = copy.deepcopy(self.responses['cases'][0])
        response['answers'][0]['reason'] = ''
        response['answers'][1]['output_evidence'] = []
        result = score_case(self.task, self.task['cases'][0], response)
        self.assertFalse(result['response_valid'])

    def test_restored_table_is_between_section_title_and_note(self):
        case = self.task['cases'][3]
        ids = [r['id'] for r in case['output']]
        position = ids.index('restored_table')
        self.assertEqual(ids[position-1:position+2], ['o011', 'restored_table', 'o012'])
        self.assertEqual(len(case['output'][position]['rows']), 5)

    def test_missing_case_and_reordered_response_rejected(self):
        response = copy.deepcopy(self.responses)
        response['cases'].pop()
        with self.assertRaises(ValueError):
            evaluate(self.task, response)
        response = copy.deepcopy(self.responses)
        response['cases'].reverse()
        with self.assertRaises(ValueError):
            evaluate(self.task, response)


if __name__ == '__main__':
    unittest.main()
