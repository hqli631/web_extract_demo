import unittest
from learning.run_cluster_repair import source, controlled, load, OUT, ROOT
from learning.run_cluster_generation import execute, validate, digest


class ClusterRepairTests(unittest.TestCase):
    def test_saved_natural_changes_are_only_eight_metadata_moves(self):
        result=load(OUT/'results.json')
        generation=[p for p in result['pages'] if p['role']=='generation']
        self.assertEqual(len(generation),6)
        self.assertTrue(all(p['exactly_unchanged'] for p in generation))
        moves=[m for p in result['pages'] for m in p['moved']]
        self.assertEqual(len(moves),8)
        self.assertEqual(sum(m['after']=='metadata.author' for m in moves),1)
        self.assertEqual(sum(m['after']=='metadata.production_credit' for m in moves),7)

    def test_v2_really_retains_folded_inline_text(self):
        for name in ['sina','chinanews']:
            data=controlled(name,'folded_leaf')
            self.assertEqual(execute(source(name,1),data)['blocks'],[])
            result=execute(source(name,2),data)
            validate(result,data,allow_production_credit=True)
            self.assertEqual(result['blocks'][0]['text'],'Folded article detail remains.')

    def test_middle_credit_and_narrative_not_removed(self):
        data=controlled('chinanews','middle_credit')
        result=execute(source('chinanews',2),data)
        self.assertEqual(len(result['blocks']),2)
        self.assertEqual(result['metadata'],[])
        data='<meta charset="utf-8"><h1 class="main-title">T</h1><div id="artibody"><p>据某报记者 张三报道，会议举行。</p></div>'.encode()
        result=execute(source('sina',2),data)
        self.assertEqual(len(result['blocks']),1)
        self.assertEqual(result['metadata'],[])

    def test_table_is_unchanged_and_repair_hashes_match(self):
        result=load(OUT/'results.json')
        page=next(p for p in result['pages'] if p['file']=='output/agent_io/final/snapshots/new_2.html')
        tables=[b for b in page['after']['blocks'] if b['kind']=='table']
        self.assertEqual(len(tables),1)
        self.assertEqual((len(tables[0]['rows']),len(tables[0]['rows'][0])),(5,3))
        record=load(OUT/'repair_record.json')
        self.assertEqual(record['test_pages_executed'],0)
        self.assertEqual(record['rounds_used'],1)
        for p in record['patches']:
            name=p['cluster_id'].split('_')[0]
            self.assertEqual(digest((ROOT/f'learning/generated/{name}_v2.py').read_bytes()),p['after_sha256'])


if __name__=='__main__':
    unittest.main()
