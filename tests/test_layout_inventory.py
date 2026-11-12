import unittest
from lxml import html
from learning.cluster_layouts import assign_clusters, features, inspect, ROOT, similarity


class LayoutInventoryTests(unittest.TestCase):
    def test_text_and_sibling_multiplicity_do_not_change_features(self):
        a = html.fromstring('<div id="body"><p>first</p></div>')
        b = html.fromstring('<div id="body"><p>other topic</p><p>more</p></div>')
        self.assertEqual(features(a), features(b))
        self.assertEqual(similarity(features(a), features(b)), 1)

    def test_nested_and_tabular_structure_remains_observable(self):
        a = features(html.fromstring('<div><p>text</p></div>'))
        b = features(html.fromstring('<div><section><p>text</p></section><table><tr><td>data</td></tr></table></div>'))
        self.assertLess(similarity(a, b), 1)
        self.assertTrue(any('table' in path for path in b))

    def test_complete_link_prevents_similarity_chaining(self):
        pages = [{'features': x} for x in [['a','b','c'], ['a','b','c','d'], ['b','c','d']]]
        groups = assign_clusters(pages)
        self.assertEqual([len(g) for g in groups], [2, 1])

    def test_old_page_cannot_become_fresh_test(self):
        record = inspect(ROOT/'samples/blog_01.html', {})
        self.assertEqual(record['exposure'], 'historical_exposed')
        self.assertEqual(record['role'], 'development_pool_only')
        self.assertEqual(len(record['sha256']), 64)


if __name__ == '__main__':
    unittest.main()
