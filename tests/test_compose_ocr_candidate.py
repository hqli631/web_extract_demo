import copy
import hashlib
import tempfile
import unittest
from pathlib import Path

from bs4 import BeautifulSoup
from compose_ocr_candidate import compose


class ComposeTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.batch = Path(self.temporary.name)
        (self.batch / 'samples').mkdir()
        (self.batch / 'images').mkdir()
        self.sample = self.batch / 'samples/page.html'
        self.sample.write_text('snapshot', encoding='utf-8')
        self.image = self.batch / 'images/a.jpg'
        self.image.write_bytes(b'image')
        digest = hashlib.sha256(b'image').hexdigest()
        snapshot = hashlib.sha256(b'snapshot').hexdigest()
        self.soup = BeautifulSoup('<p data-review-node="1">before</p><img data-review-node="2" src="https://example.com/a.jpg"><p data-review-node="3">after</p>', 'lxml')
        self.extracted = {'regions': [dict(source_node=str(index), auto_label='正文候选', text=text)
                                     for index, text in [(1, 'before'), (3, 'after')]],
                          'body_images': [{'src': 'https://example.com/a.jpg'}]}
        self.ocr = {'sample': 'page.html', 'snapshot': snapshot, 'images': [
            dict(image_order=1, status='ok', image_sha256=digest, layout_status='applied', body_candidate='image text')]}
        self.fetched = {'sample': 'page.html', 'snapshot': snapshot, 'images': [
            dict(image_order=1, file='images/a.jpg', status='downloaded', sha256=digest, url='https://example.com/a.jpg')]}

    def compose(self):
        return compose(self.sample, self.extracted, self.soup, self.ocr, self.fetched)

    def test_dom_and_image_are_interleaved_without_mutating_extraction(self):
        original = copy.deepcopy(self.extracted)
        result = self.compose()
        self.assertEqual([item['text'] for item in result['blocks']], ['before', 'image text', 'after'])
        self.assertEqual(result['status'], 'candidate_unverified')
        self.assertEqual(self.extracted, original)

    def test_unmatched_layout_and_modified_image_block_completion(self):
        self.ocr['images'][0]['layout_status'] = 'anchors_not_matched'
        self.assertEqual(self.compose()['status'], 'blocked')
        self.ocr['images'][0]['layout_status'] = 'applied'
        self.image.write_bytes(b'changed')
        result = self.compose()
        self.assertEqual(result['status'], 'blocked')
        self.assertEqual([item['source'] for item in result['blocks']], ['dom', 'dom'])

    def test_changed_snapshot_and_image_url_are_rejected(self):
        self.fetched['images'][0]['url'] = 'https://example.com/other.jpg'
        with self.assertRaisesRegex(ValueError, 'URL/order'):
            self.compose()
        self.sample.write_text('changed', encoding='utf-8')
        with self.assertRaisesRegex(ValueError, 'snapshot'):
            self.compose()

    def test_missing_ocr_coverage_is_rejected(self):
        self.ocr['images'] = []
        with self.assertRaisesRegex(ValueError, 'coverage'):
            self.compose()
