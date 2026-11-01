import tempfile
import unittest
from pathlib import Path
from bs4 import BeautifulSoup
from extract import extract_file
from review_source import marked_source
from serve_review import snapshot


class ReviewSourceTests(unittest.TestCase):
    def test_static_regions_match_snapshot_identities_without_mutating_source(self):
        source = '<html><head><script>bad()</script></head><body><article><p>重复</p><p>重复</p><div><template shadowrootmode="open"><p>影子正文</p></template></div><p hidden>隐藏正文</p></article></body></html>'
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / 'page.html'
            path.write_text(source, encoding='utf-8')
            result = extract_file(path)
            frozen = BeautifulSoup(snapshot(path), 'html.parser')
            ids = []
            for region in result['regions']:
                node = frozen.find(attrs={'data-review-node': region['source_node']})
                self.assertIsNotNone(node)
                self.assertEqual(node.get_text(' ', strip=True) or node.string, region['text'])
                ids.append(region['source_node'])
            self.assertEqual(len(ids), len(set(ids)))
            self.assertEqual(result['content'].splitlines(), ['重复', '重复', '影子正文', '隐藏正文'])
            self.assertEqual(path.read_text(encoding='utf-8'), source)

    def test_untrusted_node_ids_are_replaced_deterministically(self):
        source = '<p data-review-node="spoof">甲</p><p data-review-node="spoof">乙</p>'
        first = marked_source(source)
        second = marked_source(source)
        self.assertEqual(str(first), str(second))
        self.assertEqual([p['data-review-node'] for p in first.find_all('p')], ['0', '1'])
