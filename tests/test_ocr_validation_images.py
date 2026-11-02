import hashlib
import json
import tempfile
import unittest
from pathlib import Path

from ocr_validation_images import compare, run
from ocr_layout import select_card_body


class OcrValidationTests(unittest.TestCase):
    def test_hash_failure_is_reported_and_other_images_remain_ordered(self):
        with tempfile.TemporaryDirectory() as directory:
            batch = Path(directory)
            (batch / 'reports').mkdir()
            (batch / 'samples').mkdir()
            (batch / 'images').mkdir()
            (batch / 'samples/page.html').write_text('sample', encoding='utf-8')
            from PIL import Image
            Image.new('RGB', (40, 40), 'white').save(batch / 'images/one.jpg')
            image_hash = hashlib.sha256((batch / 'images/one.jpg').read_bytes()).hexdigest()
            (batch / 'images/two.jpg').write_bytes(b'tampered')
            digest = hashlib.sha256(b'sample').hexdigest()
            fetch = {'sample': 'page.html', 'snapshot': digest, 'images': [
                {'image_order': 2, 'file': 'images/two.jpg', 'status': 'downloaded', 'sha256': 'wrong'},
                {'image_order': 1, 'file': 'images/one.jpg', 'status': 'downloaded',
                 'sha256': image_hash}]}
            (batch / 'reports/page_image_fetch.json').write_text(json.dumps(fetch), encoding='utf-8')
            result, report = run(batch, 'page.html', lambda _: ([([[0, 0], [30, 0], [30, 20], [0, 20]], '正文', 0.9)], None))
            self.assertEqual([x['status'] for x in result['images']], ['ok', 'failed'])
            self.assertEqual(result['images'][0]['text'], '正文')
            self.assertIn('hash changed', result['images'][1]['reason'])
            self.assertTrue(report.exists())

    def test_similarity_ignores_line_breaks(self):
        self.assertEqual(compare('第一行第二行', '第一行\n第二行'), 1.0)
        self.assertIsNone(compare('', '正文'))

    def test_card_profile_requires_anchors_and_preserves_uncertain_text(self):
        def line(text, y):
            return {'text': text, 'box': [[10, y], [100, y], [100, y+10], [10, y+10]], 'confidence': .95}
        lines = [line('言道', 50), line('正文提到习近平，保留该句。', 250),
                 line('习近平', 730), line('在党外人士座谈会上说', 760),
                 line('2026年8月21日', 800), line('WWW.CHINANEWS.COM.CN', 950)]
        decisions, status = select_card_body(lines, 1000, 'chinanews_quote_card_v1')
        self.assertEqual(status, 'applied')
        self.assertEqual([x['text'] for x in decisions if x['label'] == '正文候选'], ['正文提到习近平，保留该句。'])
        decisions, status = select_card_body(lines[:-1], 1000, 'chinanews_quote_card_v1')
        self.assertEqual(status, 'anchors_not_matched')
        self.assertTrue(all(x['label'] == '待判断' for x in decisions))
        decisions, status = select_card_body(lines, 1000)
        self.assertEqual(status, 'not_applied')


if __name__ == '__main__':
    unittest.main()
