import hashlib
import json
from pathlib import Path
import unittest
from learning.prepare_natural_tasks import ROOT, structure
from learning.prepare_next_layout_tasks import validate
from lxml import html

class NaturalTaskTests(unittest.TestCase):
    def test_registered_data_roles_hashes_and_no_test_in_prompts(self):
        protocol=json.loads((ROOT/'config/next_layout_tasks.json').read_text(encoding='utf8'))
        self.assertEqual(validate(protocol),[])
        rows=[json.loads(line) for line in (ROOT/'output/stage5/multitask/natural_train.jsonl').read_text(encoding='utf8').splitlines()]
        self.assertEqual(len(rows),3)
        tests={p['path'] for c in protocol['clusters'] for p in c['pages'] if p['role']=='test'}
        for row in rows:
            self.assertEqual(len(row['sources']),2)
            self.assertFalse(tests.intersection(s['path'] for s in row['sources']))
            for test in tests:
                self.assertNotIn(test,row['messages'][1]['content'])
            self.assertEqual(hashlib.sha256((ROOT/row['target']['path']).read_bytes()).hexdigest(),row['target']['sha256'])
        checks=json.loads((ROOT/'output/stage5/multitask/natural_reference_checks.json').read_text(encoding='utf8'))
        self.assertEqual(len(checks['checks']),9)
        self.assertFalse(checks['test_dom_inspected'])
        self.assertTrue(all(c['contract_and_source_evidence_pass'] for c in checks['checks']))
    def test_structure_bound_and_order_with_disclosed_omission(self):
        node=html.fromstring('<div id="body"><p>first</p><p>second</p><p>third</p></div>')
        result=structure(node,max_nodes=3)
        self.assertEqual(result['total_nodes'],4)
        self.assertEqual(result['nodes_omitted'],1)
        self.assertEqual([r[3] for r in result['nodes']],['','first','second'])

if __name__=='__main__':
    unittest.main()
