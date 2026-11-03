import unittest

from author_candidates import find_author_candidates


class AuthorCandidateTests(unittest.TestCase):
    def test_only_independent_short_byline_is_candidate(self):
        page = {'blocks': [
            {'type': 'paragraph', 'text': '中新网记者 薄雯雯', 'xpath': '/p[1]'},
            {'type': 'paragraph', 'text': '中新社记者：您如何看待？', 'xpath': '/p[2]'},
            {'type': 'caption', 'text': '图为记者现场采访。', 'xpath': '/div[1]'},
            {'type': 'paragraph', 'text': '记者在报道中提到这项工作很重要。', 'xpath': '/p[3]'},
        ]}
        result = find_author_candidates(page)
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]['text'], '中新网记者 薄雯雯')
        self.assertEqual(result[0]['raw_block_index'], 1)

    def test_empty_and_long_sentence_are_ignored(self):
        page = {'blocks': [
            {'type': 'paragraph', 'text': '', 'xpath': '/p[1]'},
            {'type': 'paragraph', 'text': '作者：这是一个带冒号的正文问题', 'xpath': '/p[2]'},
            {'type': 'paragraph', 'text': '记者' + '很长' * 30, 'xpath': '/p[3]'},
        ]}
        self.assertEqual(find_author_candidates(page), [])


if __name__ == '__main__':
    unittest.main()
