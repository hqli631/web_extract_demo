import hashlib
import json
import tempfile
import unittest
from pathlib import Path

from ocr_validation_images import compare, run


class OcrValidationTests(unittest.TestCase):
    def test_hash_failure_is_reported_and_other_images_remain_ordered(self):
        with tempfile.TemporaryDirectory() as directory:
            batch = Path(directory)
            (batch / 'reports').mkdir()
            (batch / 'samples').mkdir()
            (batch / 'images').mkdir()
            (batch / 'samples/page.html').write_text('sample', encoding='utf-8')
            (batch / 'images/one.jpg').write_bytes(b'one')
            (batch / 'images/two.jpg').write_bytes(b'tampered')
            digest = hashlib.sha256(b'sample').hexdigest()
            fetch = {'sample': 'page.html', 'snapshot': digest, 'images': [
                {'image_order': 2, 'file': 'images/two.jpg', 'status': 'downloaded', 'sha256': 'wrong'},
                {'image_order': 1, 'file': 'images/one.jpg', 'status': 'downloaded',
                 'sha256': hashlib.sha256(b'one').hexdigest()}]}
            (batch / 'reports/page_image_fetch.json').write_text(json.dumps(fetch), encoding='utf-8')
            result, report = run(batch, 'page.html', lambda _: ([([0, 0], '正文', 0.9)], None))
            self.assertEqual([x['status'] for x in result['images']], ['ok', 'failed'])
            self.assertEqual(result['images'][0]['text'], '正文')
            self.assertIn('hash changed', result['images'][1]['reason'])
            self.assertTrue(report.exists())

    def test_similarity_ignores_line_breaks(self):
        self.assertEqual(compare('第一行第二行', '第一行\n第二行'), 1.0)
        self.assertIsNone(compare('', '正文'))


if __name__ == '__main__':
    unittest.main()
