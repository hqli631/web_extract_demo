"""Project-one-inspired controls: evidence, types, legacy text and independent scope."""
import copy
import json
import unittest
from pathlib import Path
from project2_engine import extract, structural_feedback, summarize, validate_result

def rules(**updates):
    result=dict(title_xpath='//h1',container_xpath='//*[@id="body"]',block_xpath='./p',exclude_xpath='',metadata_xpath='')
    result.update(updates)
    return result

def encoded(markup):
    return ('<meta charset="utf-8">'+markup).encode('utf8')

class FoundationControls(unittest.TestCase):
    def test_raw_xpath_survives_removed_div_script_and_tail(self):
        data=encoded('<h1>T</h1><div><script>noise</script></div><div id="body"><p>Keep<script>bad()</script> tail</p></div>')
        result=extract(rules(),data)
        self.assertEqual(result['blocks'][0]['text'],'Keep tail')
        self.assertEqual(result['blocks'][0]['xpath'],'/html/body/div[2]/p')
        self.assertEqual(validate_result(result,data),[])

    def test_typed_metadata_attributes_and_interview_question(self):
        data=encoded('<meta property="article:author" content="张三"><h1>T</h1><div id="body"><p class="byline">中新社记者 张三</p><p>中新社记者：为什么？</p><p class="adEditor">编辑：李四</p></div>')
        result=extract(rules(metadata_fields={'author':'//meta[@property="article:author"] | //p[@class="byline"]','editor':'//p[@class="adEditor"]'}),data)
        self.assertEqual([b['text'] for b in result['blocks']],['中新社记者：为什么？'])
        self.assertEqual({b['type'] for b in result['metadata']},{'author','editor'})
        self.assertTrue(any(b.get('attribute')=='content' for b in result['metadata']))
        self.assertTrue(all(b['kind']==b['type'] for b in result['blocks']+result['metadata']))

    def test_code_whitespace_lists_definitions_and_image_warning(self):
        data=encoded('<h1>T</h1><div id="body"><pre>if True:\n    print(1)\n</pre><ul><li>One</li></ul><dl><dt>Term</dt><dd>Definition</dd></dl><img src="x"></div>')
        result=extract(rules(block_xpath='.//pre|.//li|.//dt|.//dd'),data)
        self.assertEqual([b['type'] for b in result['blocks']],['code_block','list_item','definition_term','definition_description'])
        self.assertIn('\n    print(1)',result['blocks'][0]['text'])
        self.assertTrue(any('images_present' in x for x in result['warnings']))

    def test_legacy_br_inline_tail_segment_evidence(self):
        data=encoded('<h1>T</h1><div id="body"><font>First <b>bold</b> tail.<br><br>Second.<p>Third.</p>Fourth tail.</font></div>')
        result=extract(rules(block_xpath='./font',block_mode='br_segments'),data)
        self.assertEqual([b['text'] for b in result['blocks']],['First bold tail.','Second.','Third.','Fourth tail.'])
        self.assertEqual(validate_result(result,data),[])
        reordered=copy.deepcopy(result)
        reordered['blocks'][0],reordered['blocks'][1]=reordered['blocks'][1],reordered['blocks'][0]
        self.assertIn('segment_order_changed',validate_result(reordered,data))
        result['blocks'][0]['text']='fabricated'
        self.assertIn('segment_missing_in_source',validate_result(result,data))

    def test_independent_scope_catches_narrow_container_and_pre(self):
        data=encoded('<h1>T</h1><div id="body"><section><p>First.</p></section><pre>Missing code</pre></div>')
        result=extract(rules(container_xpath='//section',block_xpath='./p'),data)
        issues=structural_feedback(result,data,'//*[@id="body"]')
        self.assertEqual(issues[0]['kind'],'uncovered_article_node')
        self.assertEqual(issues[0]['preview'],'Missing code')

    def test_selected_descendant_does_not_hide_parent_own_text(self):
        data=encoded('<h1>T</h1><div id="body"><ul><li>Missing lead <p>Selected detail</p></li></ul></div>')
        result=extract(rules(block_xpath='.//p'),data)
        self.assertTrue(structural_feedback(result,data,'//*[@id="body"]'))

    def test_metadata_cannot_bypass_body_check(self):
        data=encoded('<h1>T</h1><div id="body"><p>Real story</p><p>Other</p></div>')
        result=extract(rules(metadata_fields={'author':'//p[1]'}),data)
        self.assertIn('metadata_requires_review',[i['kind'] for i in structural_feedback(result,data,'//*[@id="body"]')])

    def test_scope_summary_for_news_and_unknown_ambiguity(self):
        data=encoded('<h1>News title</h1><div id="body"><p>Story</p></div>')
        summary=json.loads(summarize(data,'//*[@id="body"]'))
        self.assertTrue(any(r['tag']=='h1' for r in summary))
        with self.assertRaises(ValueError):
            summarize(data)

    def test_evidence_validator_catches_reorder_text_and_table_tamper(self):
        data=encoded('<h1>T</h1><div id="body"><p>Before</p><table><tr><td>A</td></tr></table><p>After</p></div>')
        result=extract(rules(block_xpath='./p|./table'),data)
        changed=copy.deepcopy(result)
        changed['blocks'].reverse()
        self.assertIn('body_order_changed',validate_result(changed,data))
        changed=copy.deepcopy(result)
        changed['blocks'][1]['rows']=[['Wrong']]
        self.assertIn('table_structure_changed',validate_result(changed,data))

    def test_exposed_project_one_body_sequence_regression(self):
        root=Path(__file__).resolve().parents[1]
        config=json.loads((root/'config/project2_foundation_reference.json').read_text(encoding='utf8'))
        for page in config['pages']:
            with self.subTest(page=page['id']):
                raw=(root/page['path']).read_bytes()
                result=extract(page['rules'],raw)
                reference=json.loads((root/page['reference']).read_text(encoding='utf8'))
                compact=lambda blocks:[''.join(b['text'].split()) for b in blocks]
                self.assertEqual(compact(result['blocks']),compact(reference['blocks']))

if __name__=='__main__':
    unittest.main()
