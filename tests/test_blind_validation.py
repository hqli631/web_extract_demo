import unittest
import json
import tempfile
from pathlib import Path

from run_blind_validation import audit_page, development_overlap, run
from collect_pages import exclusion_reason


class BlindValidationTests(unittest.TestCase):
    def test_image_inventory_preserves_order_and_unverified_state(self):
        root = Path(__file__).resolve().parents[1]
        with tempfile.TemporaryDirectory(dir=root) as folder:
            batch = Path(folder)
            (batch / 'reports').mkdir()
            (batch / 'samples').mkdir()
            (batch / 'evaluation_context.json').write_text(json.dumps({
                'frozen_code_sha256': __import__('run_blind_validation').code_hashes(),
                'urls': [seed for target in json.loads((root / 'config/collection_blind.json').read_text(encoding='utf-8'))['targets'] for seed in target['seeds']],
            }), encoding='utf-8')
            (batch / 'reports/collection_manifest.json').write_text('[]', encoding='utf-8')
            (batch / 'reports/ai_review.json').write_text('{"pages":[]}', encoding='utf-8')
            (batch / 'samples/sample.html').write_text('<article><p>' + '正文内容。' * 20 + '</p><img src="one.jpg"><img src="two.jpg"></article>', encoding='utf-8')
            (batch / 'reports/collection_manifest.json').write_text(json.dumps([{
                'file': 'sample.html', 'url': 'https://new.example/article',
                'snapshot': __import__('hashlib').sha256((batch / 'samples/sample.html').read_bytes()).hexdigest(),
            }]), encoding='utf-8')
            run(batch=batch)
            inventory = json.loads((batch / 'reports/image_inventory.json').read_text(encoding='utf-8'))
            self.assertEqual([item['image_order'] for item in inventory['images']], [1, 2])
            self.assertTrue(all(item['ocr_status'] == 'not_run' for item in inventory['images']))


    def test_image_article_cannot_pass_as_complete_text(self):
        status, _ = audit_page({'content': 'intro'}, 'same',
                               {'snapshot': 'same', 'requires_ocr': True})
        self.assertEqual(status, 'needs_ocr')

    def test_collector_excludes_known_url_before_fetch(self):
        self.assertEqual(exclusion_reason('https://example.com/story?new=1', None,
                         [{'url': 'https://example.com/story?old=1'}]), 'excluded_development_url')

    def test_collector_excludes_duplicate_text_from_different_url(self):
        self.assertEqual(exclusion_reason('https://example.com/other', 'same',
                         [{'content_hash': 'same'}]), 'excluded_development_content')

    def test_collector_allows_new_article(self):
        self.assertEqual(exclusion_reason('https://example.com/new', 'new',
                         [{'url': 'https://example.com/old', 'content_hash': 'old'}]), '')

    def test_tracking_parameters_do_not_hide_development_url(self):
        reason = development_overlap({'url': 'https://example.com/story?tracking=new'}, 'new',
                                     [{'url': 'https://example.com/story?tracking=old'}])
        self.assertIn('URL', reason)

    def test_content_duplicate_with_different_url_is_excluded(self):
        self.assertTrue(development_overlap({'content_hash': 'same'}, 'new',
                                            [{'content_hash': 'same'}]))

    def test_snapshot_duplicate_is_excluded(self):
        self.assertTrue(development_overlap({}, 'same', [{'snapshot': 'same'}]))

    def test_unseen_page_remains_pending(self):
        self.assertEqual(development_overlap({'url': 'https://example.com/new'}, 'new',
                                             [{'url': 'https://example.com/old', 'snapshot': 'old'}]), '')
        self.assertEqual(audit_page({'content': 'text'}, 'new', None)[0], 'pending_ai_review')

    def setUp(self):
        self.snapshot = 'snapshot-a'
        self.audit = {
            'snapshot': self.snapshot,
            'body_blocks': ['paragraph one', 'paragraph two'],
            'excluded_blocks': ['comments'],
        }

    def test_exact_body_and_order_passes(self):
        status, result = audit_page({'content': 'paragraph one\nparagraph two'}, self.snapshot, self.audit)
        self.assertEqual(status, 'pass')
        self.assertTrue(result['exact_body_and_order_match'])

    def test_missing_or_reordered_paragraph_fails(self):
        status, result = audit_page({'content': 'paragraph two'}, self.snapshot, self.audit)
        self.assertEqual(status, 'fail')
        self.assertEqual(result['missing'], ['paragraph one'])

    def test_changed_snapshot_cannot_reuse_audit(self):
        status, result = audit_page({'content': 'paragraph one\nparagraph two'}, 'snapshot-b', self.audit)
        self.assertEqual(status, 'stale')
        self.assertIn('不能复用', result['reason'])

    def test_excluded_text_leaking_into_body_fails(self):
        status, result = audit_page({'content': 'paragraph one\ncomments'}, self.snapshot, self.audit)
        self.assertEqual(status, 'fail')
        self.assertEqual(result['excluded_content_leaked'], ['comments'])


if __name__ == '__main__':
    unittest.main()
