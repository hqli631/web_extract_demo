import copy
import unittest

from xpath_semantic import find_review, review_fingerprint, RUBRIC_IDS


class SemanticReviewTests(unittest.TestCase):
    def setUp(self):
        self.page = {'file': 'a.html', 'source_sha256': 'source', 'title': 'T',
                     'container_count': 1, 'blocks': [{'type': 'paragraph', 'text': 'A', 'xpath': '/p'}]}
        self.rules = {'version': 1}
        self.document = {'reviews': [{'file': 'a.html',
            'fingerprint': review_fingerprint(self.page, self.rules),
            'rubrics': [{'id': key, 'status': 'pass', 'reason': 'reason',
                         'evidence': [{'xpath': '/p', 'quote': 'A'}]} for key in RUBRIC_IDS]}]}

    def test_current_and_missing(self):
        self.assertEqual(find_review(self.page, self.rules, self.document)['status'], 'current')
        self.assertEqual(find_review(self.page, self.rules, {})['status'], 'missing')

    def test_source_rule_text_and_order_changes_expire_review(self):
        changed = copy.deepcopy(self.page)
        changed['source_sha256'] = 'different'
        self.assertEqual(find_review(changed, self.rules, self.document)['status'], 'stale')
        self.assertEqual(find_review(self.page, {'version': 2}, self.document)['status'], 'stale')
        changed = copy.deepcopy(self.page)
        changed['blocks'][0]['text'] = 'B'
        self.assertEqual(find_review(changed, self.rules, self.document)['status'], 'stale')

    def test_false_evidence_rejected(self):
        self.document['reviews'][0]['rubrics'][0]['evidence'][0]['quote'] = 'absent'
        self.assertEqual(find_review(self.page, self.rules, self.document)['status'], 'invalid')

    def test_duplicate_and_incomplete_reviews_rejected(self):
        document = copy.deepcopy(self.document)
        document['reviews'].append(document['reviews'][0])
        self.assertEqual(find_review(self.page, self.rules, document)['status'], 'invalid')
        self.document['reviews'][0]['rubrics'].pop()
        self.assertEqual(find_review(self.page, self.rules, self.document)['status'], 'invalid')


if __name__ == '__main__':
    unittest.main()
