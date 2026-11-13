import copy
import unittest
from learning.grpo_update_signals import probability_example,categorical_kl,metrics,build

class GrpoUpdateSignalTests(unittest.TestCase):
    def test_clip_plateau_and_direction(self):
        high=probability_example(.2,.3,1)
        self.assertAlmostEqual(high['ratio'],1.5)
        self.assertAlmostEqual(high['surrogate'],1.2)
        self.assertEqual(high['local_slope_wrt_ratio'],0)
        self.assertEqual(probability_example(.2,.1,-1)['local_slope_wrt_ratio'],0)
        self.assertEqual(probability_example(.2,.3,-1)['local_slope_wrt_ratio'],-1)
        self.assertEqual(probability_example(.2,.1,1)['local_slope_wrt_ratio'],1)
        self.assertIsNone(probability_example(.2,.24,1)['local_slope_wrt_ratio'])

    def test_kl_normalization_and_identity(self):
        self.assertAlmostEqual(categorical_kl([.5,.5],[.5,.5]),0)
        self.assertAlmostEqual(categorical_kl([.75,.25],[.5,.5]),.1308120359)
        with self.assertRaises(ValueError): categorical_kl([.5,.7],[.5,.5])

    def test_failed_and_unknown_costs_and_denominators_remain(self):
        pair=build()['paired_experiment']
        for name,total in [('baseline',330),('efficient',240)]:
            m=pair[name]['metrics']
            self.assertEqual(m['total_tasks'],4)
            self.assertEqual(m['pass'],2)
            self.assertEqual(m['unknown'],1)
            self.assertEqual(m['confirmed_pass_rate_all_tasks'],.5)
            self.assertEqual(m['total_cost_units'],total)
            self.assertEqual(m['cost_units_per_confirmed_pass'],total/2)
        self.assertEqual(pair['baseline']['metrics']['mean_rounds_all_tasks'],2.75)
        self.assertEqual(pair['efficient']['metrics']['mean_rounds_pass_tasks'],1)

    def test_no_confirmed_pass_does_not_divide_by_zero(self):
        m=metrics([{'task_id':'T1','outcome':'unknown','rounds':2,'cost_units':10}])
        self.assertIsNone(m['mean_rounds_pass_tasks'])
        self.assertIsNone(m['cost_units_per_confirmed_pass'])
        with self.assertRaises(ValueError): metrics([])

if __name__=='__main__':
    unittest.main()
