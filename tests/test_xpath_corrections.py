import copy
import unittest

from xpath_corrections import compose_cleaned


class BylineCorrectionTests(unittest.TestCase):
    def setUp(self):
        self.page = {'blocks': [
            {'xpath': '/p[1]', 'text': '中新社记者 孙翔', 'type': 'paragraph'},
            {'xpath': '/p[2]', 'text': '中新社记者：您如何看待？', 'type': 'paragraph'},
            {'xpath': '/div', 'text': '图为记者采访。', 'type': 'caption'}],
            'semantic_review': {'status': 'current', 'record': {'fingerprint': 'snapshot',
                'rubrics': [{'id': 'non_content', 'status': 'needs_review', 'evidence': [
                    {'xpath': '/p[1]', 'quote': '中新社记者 孙翔'}]}],
                'corrections': [{'operation': 'move_to_author', 'xpath': '/p[1]',
                    'expected_text': '中新社记者 孙翔', 'author_name': '孙翔'}]}}}

    def test_preserves_questions_captions_raw_blocks_and_order(self):
        before = copy.deepcopy(self.page)
        result = compose_cleaned(self.page)
        self.assertEqual(result['status'], 'applied')
        self.assertEqual(result['authors'][0]['name'], '孙翔')
        self.assertEqual(result['blocks'], before['blocks'][1:])
        self.assertTrue(result['conservation_check'])
        self.assertEqual(self.page, before)

    def test_stale_review_does_not_apply(self):
        self.page['semantic_review']['status'] = 'stale'
        result = compose_cleaned(self.page)
        self.assertEqual(result['status'], 'not_applied')
        self.assertEqual(result['blocks'], self.page['blocks'])

    def test_wrong_text_duplicate_action_and_unknown_operation_rejected(self):
        action = self.page['semantic_review']['record']['corrections'][0]
        for changes in ({'expected_text': 'different'}, {'operation': 'delete'}, {'author_name': 'absent'}):
            page = copy.deepcopy(self.page)
            page['semantic_review']['record']['corrections'][0].update(changes)
            self.assertEqual(compose_cleaned(page)['status'], 'rejected')
        self.page['semantic_review']['record']['corrections'].append(copy.deepcopy(action))
        result = compose_cleaned(self.page)
        self.assertEqual(result['status'], 'rejected')
        self.assertEqual(result['blocks'], self.page['blocks'])

    def test_no_actions_leaves_all_blocks(self):
        self.page['semantic_review']['record']['corrections'] = []
        self.assertEqual(compose_cleaned(self.page)['blocks'], self.page['blocks'])


if __name__ == '__main__':
    unittest.main()
