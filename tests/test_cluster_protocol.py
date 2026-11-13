import unittest
from learning.prepare_cluster_protocol import structure, select_urls, near, grams, audit, ROOT, OUT, read, sha, TARGETS


class ClusterProtocolTests(unittest.TestCase):
    def test_shell_ignores_inner_content_but_detects_outer_change(self):
        xpath="//div[@id='body']"
        a=structure(b'<main><div id="body"><p>x</p></div></main>',xpath)
        b=structure(b'<main><div id="body"><table><tr><td>y</td></tr></table></div></main>',xpath)
        c=structure(b'<aside><div id="body"><p>x</p></div></aside>',xpath)
        self.assertEqual(a['shell'],b['shell'])
        self.assertNotEqual(a['shell'],c['shell'])

    def test_selection_order_and_history_exclusion(self):
        base='https://finance.sina.com.cn/roll/'
        first='https://finance.sina.com.cn/a/doc-abc.shtml'
        second='https://finance.sina.com.cn/a/doc-def.shtml'
        data=f'<a href="{first}">a</a><a href="{second}">b</a><a href="{second}">b</a>'.encode()
        self.assertEqual(select_urls(data,base,'sina',{first}),[second])

    def test_dedup_and_historical_shell_audit(self):
        self.assertEqual(near(grams('abcdefgh'),grams('abcdefgh')),1)
        groups=audit()
        self.assertEqual(len(groups),2)
        self.assertTrue(all(g['shell_verified'] and len(g['members'])==6 for g in groups))

    def test_frozen_split_has_unique_sources_and_no_generation_repair_near_duplicate(self):
        split=read(OUT/'split_v2.json')
        self.assertEqual(split['status'],'frozen')
        for group in split['clusters']:
            paths=group['generation']+group['repair']+group['test']
            self.assertEqual(len(paths),12)
            self.assertEqual(len(set(paths)),12)
            for path in paths:
                self.assertEqual(sha((ROOT/path).read_bytes()),group['snapshot_sha256'][path])
            xpath=TARGETS[group['cluster_id'].split('_')[0]][1]
            generation=[grams(structure((ROOT/p).read_bytes(),xpath)['body']) for p in group['generation']]
            for path in group['repair']:
                g=grams(structure((ROOT/path).read_bytes(),xpath)['body'])
                self.assertTrue(all(near(g,old)<.85 for old in generation))

    def test_short_static_pages_remain_in_test_set(self):
        result=read(OUT/'verification.json')
        short=[p for p in result['tests'] if p.get('short_static_text_risk')]
        self.assertEqual(len(short),2)
        self.assertTrue(all(p['eligible'] for p in short))


if __name__=='__main__':
    unittest.main()
