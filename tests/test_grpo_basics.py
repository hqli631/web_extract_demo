import math
import unittest
from learning.grpo_basics import group_advantages,clipped_surrogate,historical_trajectory

class GrpoBasicsTests(unittest.TestCase):
    def test_group_centering_and_population_variance(self):
        g=group_advantages([0.2,0.4,0.8,1.0])
        self.assertAlmostEqual(g['mean'],0.6)
        self.assertAlmostEqual(g['population_variance'],0.1)
        self.assertAlmostEqual(sum(g['advantages']),0)
        for actual,expected in zip(g['advantages'],[-1.264911,-0.632456,0.632456,1.264911]):
            self.assertAlmostEqual(actual,expected,places=5)

    def test_shift_invariance_and_ties(self):
        a=group_advantages([0,1,2,3])['advantages']
        b=group_advantages([10,11,12,13])['advantages']
        self.assertEqual(a,b)
        same=group_advantages([0.8]*4)
        self.assertEqual(same['advantages'],[0]*4)
        self.assertFalse(same['reward_ranking_signal'])

    def test_unknown_and_nonfinite_are_not_silently_zero_rewards(self):
        for values in [[None,1],[math.nan,1],[math.inf,1],[True,1],[1],[]]:
            with self.assertRaises(ValueError): group_advantages(values)
        with self.assertRaises(ValueError): group_advantages([1,2],epsilon=0)

    def test_clipping_signs(self):
        for ratio,a,expected in [(1.5,1,1.2),(0.5,-1,-0.8),(1.5,-1,-1.5),(0.5,1,0.5)]:
            self.assertAlmostEqual(clipped_surrogate(ratio,a)['surrogate'],expected)
        with self.assertRaises(ValueError): clipped_surrogate(0,1)

    def test_historical_evidence_has_no_invented_reward(self):
        t=historical_trajectory()
        self.assertIsNone(t['numeric_reward'])
        last=t['events'][-1]['evidence']
        self.assertEqual(last['body_before']-last['body_after'],1)
        self.assertEqual(last['author_record']['kind'],'author')
        self.assertEqual(last['generation_unchanged'],6)

if __name__=='__main__':
    unittest.main()
