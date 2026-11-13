import copy
import unittest
from learning.prepare_natural_review import OUT,read
from learning.run_natural_review import assess,expand_saved_notes,feedback_cards,source_links

class NaturalReviewTests(unittest.TestCase):
    def setUp(self):
        self.task=read(OUT/'task.json')
        self.response=read(OUT/'review_response.json')

    def test_citations_valid_and_no_independent_claim(self):
        results=assess(self.task,self.response)
        self.assertTrue(all(r['response_valid'] for r in results))
        self.assertFalse(self.response['independent_context'])
        self.assertEqual(self.response,expand_saved_notes(self.task,read(OUT/'review_notes.json')))

    def test_source_quote_cannot_be_fabricated(self):
        r=copy.deepcopy(self.response)
        r['cases'][0]['answers'][0]['source_evidence'][0]['quote']='NOT IN THIS SOURCE'
        first=assess(self.task,r)[0]
        self.assertFalse(first['response_valid'])
        self.assertIsNone(first['score'])

    def test_wrong_task_missing_or_reordered_cases_rejected(self):
        for mutate in ['hash','missing','order']:
            r=copy.deepcopy(self.response)
            if mutate=='hash': r['task_sha256']='stale'
            if mutate=='missing': r['cases'].pop()
            if mutate=='order': r['cases'].reverse()
            with self.assertRaises(ValueError): assess(self.task,r)

    def test_unknown_is_not_an_automatic_low_score(self):
        image=assess(self.task,self.response)[2]
        self.assertTrue(image['response_valid'])
        self.assertIsNone(image['score'])
        self.assertIsNone(image['reward_signal'])
        self.assertEqual(image['adoption'],'needs_evidence')

    def test_learner_feedback_not_fabricated(self):
        for card in feedback_cards(self.task):
            self.assertEqual(card['user_status'],'pending')
            self.assertIsNone(card['user_answer'])

    def test_caption_quotes_point_to_caption_text_not_neighbor_paragraph(self):
        answer=self.response['cases'][0]['answers'][2]
        for ref in answer['output_evidence']:
            self.assertIn('截图',ref['quote'])
        for case in self.task['cases']:
            url,display=source_links(self.task['sources'][case['source_id']]['file'])
            self.assertTrue(url.startswith('https://'))
            self.assertIsNotNone(display)

if __name__=='__main__':
    unittest.main()
