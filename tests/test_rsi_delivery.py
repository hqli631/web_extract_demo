import unittest
from learning.run_rsi_delivery import fixture, gate, load_trusted, run

class RsiDeliveryTests(unittest.TestCase):
    def test_real_reference_patch_fixes_inline_fold_without_deleting_question(self):
        old, fixed = load_trusted(1), load_trusted(2)
        self.assertEqual(old(fixture('folded_leaf'))['blocks'], [])
        self.assertEqual([b['text'] for b in fixed(fixture('folded_leaf'))['blocks']], ['Folded article detail remains.'])
        self.assertEqual(old(fixture('interview')), fixed(fixture('interview')))

    def test_gate_rejects_missing_or_reordered_content(self):
        baseline = {'body':['one','two']}
        self.assertFalse(gate({'body':['two','one']}, baseline, {})['adopt'])
        self.assertFalse(gate({'body':['one']}, baseline, {})['adopt'])

    def test_replay_adopts_one_rejects_one_and_keeps_accepted_version(self):
        report=run()
        self.assertEqual([r['action'] for r in report['rounds']], ['adopt','reject_and_rollback'])
        self.assertEqual(report['rounds'][0]['active_after'], report['rounds'][1]['active_after'])
        self.assertFalse(report['cloud_model_candidates_executed'])
        self.assertEqual(len(report['sources']),3)
        self.assertTrue(all('test_4' not in p['path'] for p in report['sources']))

if __name__ == '__main__':
    unittest.main()
