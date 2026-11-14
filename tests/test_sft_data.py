import ast
from copy import deepcopy
import unittest

from learning.prepare_sft_data import compact_dom, make_records, validate_records


class SFTDataTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.records = make_records()

    def test_two_historical_tasks_not_augmented_or_test_claimed(self):
        self.assertEqual(validate_records(self.records), [])
        self.assertEqual(len(self.records), 2)
        self.assertEqual({r['split'] for r in self.records}, {'train', 'dev'})
        self.assertTrue(all(r['historical_exposure'] for r in self.records))
        self.assertTrue(all(len(r['sources']) == 3 for r in self.records))

    def test_cross_split_cluster_is_rejected(self):
        rows = deepcopy(self.records)
        rows[1]['group_id'] = rows[0]['group_id']
        self.assertTrue(any('cross-split group' in e for e in validate_records(rows)))

    def test_same_task_prompt_variant_does_not_inflate_task_count(self):
        rows = deepcopy(self.records)
        variant = deepcopy(rows[0])
        variant['id'] += '-variant'
        variant['messages'][1]['content'] += ' Please comply.'
        rows.append(variant)
        self.assertTrue(any('prompt variants are not independent' in e for e in validate_records(rows)))

    def test_cross_split_source_is_rejected_even_with_different_path(self):
        rows = deepcopy(self.records)
        rows[1]['sources'][0] = deepcopy(rows[0]['sources'][0])
        self.assertTrue(any('cross-split source' in e for e in validate_records(rows)))

    def test_duplicate_target_and_prompt_are_rejected(self):
        rows = deepcopy(self.records)
        rows[1]['messages'] = deepcopy(rows[0]['messages'])
        errors = validate_records(rows)
        self.assertTrue(any('duplicate target across' in e for e in errors))
        self.assertTrue(any('duplicate prompt across' in e for e in errors))

    def test_wrong_roles_missing_sources_and_exposure_are_rejected(self):
        rows = deepcopy(self.records)
        rows[0]['historical_exposure'] = False
        rows[0]['sources'] = []
        rows[1]['messages'][0]['role'] = 'assistant'
        errors = validate_records(rows)
        self.assertTrue(any('exposure' in e for e in errors))
        self.assertTrue(any('three source' in e for e in errors))
        self.assertTrue(any('system/user/assistant' in e for e in errors))

    def test_compile_interface_and_reference_mismatch_are_rejected(self):
        for bad in ['def extract(:', 'def something_else(data): return {}', 'import os\ndef extract(data): return {}']:
            rows = deepcopy(self.records)
            rows[0]['messages'][-1]['content'] = bad
            self.assertTrue(validate_records(rows))

    def test_hash_tampering_and_path_escape_are_rejected(self):
        rows = deepcopy(self.records)
        rows[0]['sources'][0]['sha256'] = '0' * 64
        self.assertTrue(any('hash mismatch' in e for e in validate_records(rows)))
        rows[0]['sources'][0]['path'] = '../outside.html'
        self.assertTrue(any('escapes repository' in e for e in validate_records(rows)))

    def test_dom_preserves_structure_and_declares_clipping(self):
        from lxml import html
        value, stats = compact_dom('<div id="body"><p class="x">123456789<strong>abc</strong>tail</p><script>bad()</script><table><tr><td>cell</td></tr></table></div>', text_limit=4)
        tree = html.fromstring(value)
        self.assertEqual(tree.xpath('./p/@class'), ['x'])
        self.assertEqual(tree.xpath('./p/strong/text()'), ['abc'])
        self.assertEqual(len(tree.xpath('./table/tr/td')), 1)
        self.assertFalse(tree.xpath('.//script'))
        self.assertIn('[TEXT_CLIPPED]', value)
        self.assertEqual(stats['text_slots_clipped'], 1)
        self.assertEqual(stats['executable_nodes_removed'], 1)

    def test_prompt_does_not_embed_reference_source(self):
        for row in self.records:
            self.assertNotIn(row['messages'][-1]['content'], row['messages'][1]['content'])
            self.assertNotIn('expected_cleaned', row['messages'][1]['content'])
            ast.parse(row['messages'][-1]['content'])


if __name__ == '__main__':
    unittest.main()
