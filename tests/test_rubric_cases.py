import unittest
from learning.run_rubric_cases import build


class RubricCaseTests(unittest.TestCase):
    def test_single_mutations_keep_source_and_unrelated_blocks(self):
        task=build()
        cases={c['case_id']:c for c in task['cases']}
        self.assertEqual(len(cases),14)
        base=cases['correct']['output']
        removed=cases['missing_table']['output']
        self.assertEqual(removed['blocks'],[r for r in base['blocks'] if r['id']!='table'])
        self.assertEqual(removed['metadata'],base['metadata'])
        injected=cases['promotion_in_body']['output']
        self.assertEqual([r for r in injected['blocks'] if r['id']!='promotion'],base['blocks'])
        self.assertTrue(all(c['synthetic'] for c in cases.values()))

    def test_context_and_visibility_are_not_deletion_keywords(self):
        task=build()
        base=task['cases'][0]['output']
        kept={r['id'] for r in base['blocks']}
        self.assertTrue({'question','folded','analysis','intro'}<=kept)
        self.assertTrue({'menu','cta','promotion'}.isdisjoint(kept))
        for row in base['blocks']:
            self.assertEqual(row,task['source_records'][row['id']])
        image=next(c for c in task['cases'] if c['case_id']=='image_unknown')
        self.assertEqual(image['expected_answers']['Q2'],'unknown')
        self.assertEqual(image['expected_answers']['Q3'],'unknown')


if __name__=='__main__':
    unittest.main()
