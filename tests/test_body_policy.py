import copy
import unittest
from lxml import html
from learning.apply_body_policy import transform,read,NATURAL,OUT,ROOT

class BodyPolicyTests(unittest.TestCase):
    def setUp(self):
        self.task=read(NATURAL/'task.json')

    def test_natural_page_moves_original_title_and_refines_structural_captions(self):
        case=copy.deepcopy(self.task['cases'][0])
        before=copy.deepcopy(case)
        source=self.task['sources'][case['source_id']]
        result=transform(case,html.document_fromstring((ROOT/source['file']).read_bytes()))
        self.assertEqual(case,before)
        after=result['after']
        self.assertEqual(len([c for c in result['changes'] if c['decision_id']=='D1']),1)
        self.assertEqual(len([c for c in result['changes'] if c['decision_id']=='D2']),4)
        self.assertEqual([r['id'] for r in after['output'] if r['id'] not in {'title','inventory'}],
                         [r['id'] for r in case['output'] if r['id'] not in {'title','inventory','o002'}])
        original=next(r for r in case['output'] if r['id']=='o002')
        moved=next(r for r in after['metadata'] if r['kind']=='original_title')
        self.assertEqual((moved['text'],moved['xpath']),(original['text'],original['xpath']))
        # Existing byline issue is not silently fixed or declared passed.
        self.assertEqual(after['output'][1]['text'],'每经记者|刘嘉魁')
        self.assertIsNone(result['new_semantic_score'])

    def test_caption_word_in_article_is_not_enough(self):
        tree=html.document_fromstring('<h1>Title</h1><div id="article"><p>文章讨论公众号截图的传播作用。</p></div>')
        node=tree.xpath('//p')[0]
        case={'case_id':'example','output':[{'id':'title','text':'Title'},
              {'id':'o1','kind':'paragraph','text':node.text_content(),'xpath':tree.getroottree().getpath(node)}],
              'metadata':[],'excluded':[]}
        result=transform(case,tree)
        self.assertEqual(result['changes'],[])
        self.assertEqual(result['after']['output'][1]['kind'],'paragraph')

    def test_ambiguous_wrapper_does_not_become_caption(self):
        tree=html.document_fromstring('<h1>Title</h1><div class="img_wrapper"><img><span class="img_descr">图说</span><p>另有正文</p></div>')
        node=tree.xpath('//div')[0]
        case={'case_id':'example','output':[{'id':'title','text':'Title'},
              {'id':'o1','kind':'paragraph','text':node.text_content(),'xpath':tree.getroottree().getpath(node)}],
              'metadata':[],'excluded':[]}
        result=transform(case,tree)
        self.assertEqual(result['changes'],[])

    def test_policy_application_is_reproducible_and_confirmation_is_real(self):
        saved=read(OUT/'application.json')
        for case,record in zip(self.task['cases'],saved['cases']):
            source=self.task['sources'][case['source_id']]
            actual=transform(case,html.document_fromstring((ROOT/source['file']).read_bytes()))
            self.assertEqual(record,actual)
        confirmation=read(OUT/'confirmed_decisions.json')
        self.assertTrue(all(d['user_status']=='confirmed' and d['user_answer'] for d in confirmation['decisions']))
        self.assertTrue(all(d['user_status']=='pending' for d in read(NATURAL/'learner_decisions.json')))

if __name__=='__main__':
    unittest.main()
