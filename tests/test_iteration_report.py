import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from build_iteration_report import reconcile, verify_transfer


class IterationReportTests(unittest.TestCase):
    def test_only_same_snapshot_and_same_content_inherit_audit(self):
        prior = dict(file='a.html', snapshot='original', kind='possible_missing',
                     text='- 完整条目', category='format_only', reason='序列化前缀')
        current = dict(prior, text='完整条目')
        self.assertEqual(reconcile([current], [prior])[0]['status'], 'reviewed')
        for changed in [dict(current, snapshot='new'), dict(current, text='完整条目与新增内容')]:
            self.assertEqual(reconcile([changed], [prior])[0]['status'], 'unreviewed')

    def test_transfer_check_rejects_changes_to_frozen_extractor(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            (root/'extract.py').write_text('changed code', encoding='utf-8')
            (root/'evaluation_context.json').write_text(json.dumps({
                'frozen_code_sha256': {'extract.py':'old digest'}}), encoding='utf-8')
            with patch('build_iteration_report.ROOT', root):
                with self.assertRaisesRegex(ValueError, 'changed after'):
                    verify_transfer(root)
