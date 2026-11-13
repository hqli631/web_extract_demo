import copy
import unittest
from learning.prepare_rubric_review import OUT, read
from learning.run_rubric_calibration import validate, compare, gate_checks, validate_protocol

class RubricCalibrationTests(unittest.TestCase):
    def setUp(self):
        self.task = read(OUT/'task.json')
        self.response = read(OUT/'reviewer_current.json')

    def test_packets_do_not_include_expected_labels(self):
        import json
        text=json.dumps(self.task)
        for key in ['expected_answers','missing_table','promotion_in_body']:
            self.assertNotIn(key,text)

    def test_quotes_validate_against_their_own_side(self):
        results=validate(self.task,self.response)
        self.assertEqual(len(results),14)
        self.assertTrue(all(r['response_valid'] for r in results))
        wrong=self.response['cases'][2]['answers'][0]
        self.assertNotEqual(wrong['source_evidence'][0]['quote'],wrong['output_evidence'][0]['quote'])

    def test_changing_expected_does_not_change_answers_or_scores(self):
        original=read(OUT.parent/'specification/cases.json')
        mapping=read(OUT/'private_mapping.json')
        before=compare(self.task,self.response,original,mapping)
        for c in original['cases']:
            c['expected_answers']=dict.fromkeys(['Q1','Q2','Q3','Q4','Q5'],'no')
        after=compare(self.task,self.response,original,mapping)
        self.assertEqual([r['answers'] for r in before['rows']],[r['answers'] for r in after['rows']])
        self.assertEqual([r['score'] for r in before['rows']],[r['score'] for r in after['rows']])
        self.assertNotEqual(before['summary']['confusion'],after['summary']['confusion'])

    def test_unknown_invalid_execution_stale_missing_unscored(self):
        gates=gate_checks(self.task,self.response)
        for name in ['unknown','invalid_quote','execution_error','stale_task','missing_question']:
            self.assertIsNone(gates[name]['score'])
            self.assertIsNone(gates[name]['reward_signal'])
        self.assertTrue(gates['unknown']['response_valid'])
        self.assertFalse(gates['invalid_quote']['response_valid'])

    def test_numeric_gate_cannot_detect_wrong_judge(self):
        gates=gate_checks(self.task,self.response)
        self.assertEqual(gates['dishonest_all_yes']['score'],1)
        self.assertEqual(gates['dishonest_all_yes']['adoption'],'candidate_within_static_scope')
        self.assertEqual(gates['copy_entire_page_simulated_judge']['score'],0.8)

    def test_stale_hash_or_missing_case_rejected(self):
        r=copy.deepcopy(self.response)
        r['task_sha256']='stale'
        with self.assertRaises(ValueError): validate(self.task,r)
        r=copy.deepcopy(self.response)
        r['cases'].pop()
        with self.assertRaises(ValueError): validate(self.task,r)

    def test_protocol_rejects_rubric_change(self):
        protocol=read(OUT/'scoring_protocol.json')
        validate_protocol(self.task,protocol)
        t=copy.deepcopy(self.task)
        t['rubric']['adoption']['minimum_score']=0.7
        with self.assertRaises(ValueError): validate_protocol(t,protocol)

if __name__=='__main__':
    unittest.main()
