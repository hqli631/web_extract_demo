import importlib.util
import io
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import project2_agent as agent
from project2_engine import digest, extract, export_python, structural_feedback, validate_rules

ROOT = agent.ROOT

class Project2Tests(unittest.TestCase):
    def task(self):
        return agent.load_task(ROOT/'config/project2_python_blog.json')

    def test_frozen_manifest_and_roles(self):
        task = self.task()
        self.assertEqual([p['role'] for p in task['pages']], ['generation']*2+['development_feedback']+['final_holdout']*2)

    def test_actual_feedback_drives_mock_repair(self):
        with tempfile.TemporaryDirectory() as tmp:
            trace = agent.run(self.task(), tmp)
            self.assertEqual(trace['final_status'],'pass')
            self.assertEqual(len(trace['rounds']),2)
            self.assertTrue(trace['rounds'][0]['issues'])
            self.assertFalse(trace['rounds'][1]['issues'])
            self.assertEqual(trace['api_attempts'],[])
            self.assertTrue(trace['frozen_before_holdout'])
            self.assertEqual(len(trace['holdout']),2)
            self.assertEqual(trace['engine_sha256'],digest((ROOT/'project2_engine.py').read_bytes()))
            saved = json.loads((Path(tmp)/'prompt_round_1.json').read_text(encoding='utf8'))
            self.assertIn('uncovered_article_node',json.dumps(saved))
            self.assertIn('development_samples',saved[-1]['content'])
            self.assertNotIn('python_blog_4',json.dumps(saved))
            self.assertNotIn('python_blog_5',json.dumps(saved))

    def test_exhausted_budget_skips_holdout(self):
        with tempfile.TemporaryDirectory() as tmp:
            trace = agent.run(self.task(),tmp,max_repairs=0)
            self.assertEqual(trace['final_status'],'development_failed')
            self.assertEqual(trace['holdout'],[])

    def test_transport_failure_persists_one_attempt_no_retry(self):
        with tempfile.TemporaryDirectory() as tmp, patch.object(agent,'call_qwen',side_effect=TimeoutError):
            trace = agent.run(self.task(),tmp,provider='dashscope')
            self.assertEqual(trace['final_status'],'failed')
            self.assertEqual(len(trace['api_attempts']),1)
            self.assertEqual(trace['api_attempts'][0]['error'],'TimeoutError')
            self.assertEqual(trace['holdout'],[])
            self.assertTrue((Path(tmp)/'trace.json').exists())

    def test_holdout_failure_never_repairs(self):
        original = agent.evaluate
        def evaluation(item,*args):
            result = original(item,*args)
            if item['role']=='final_holdout':
                result['status']='failed'
            return result
        with tempfile.TemporaryDirectory() as tmp, patch.object(agent,'evaluate',side_effect=evaluation):
            trace = agent.run(self.task(),tmp)
            self.assertEqual(trace['final_status'],'holdout_failed')
            self.assertEqual(len(trace['rounds']),2)

    def test_qwen_payload_and_key_precedence(self):
        payload = json.dumps({'choices':[{'message':{'content':'{}'}}],'usage':{'total_tokens':9}}).encode()
        class Opener:
            def open(self, request, timeout):
                self.request = request
                self.timeout = timeout
                return io.BytesIO(payload)
        for model in agent.PREFERRED_MODELS:
            opener = Opener()
            with patch.dict(os.environ,{'QWEN_API_KEY':'test-placeholder','DASHSCOPE_API_KEY':'second-placeholder'},clear=True), patch.object(agent.urllib.request,'build_opener',return_value=opener):
                _, usage = agent.call_qwen([], model)
                self.assertEqual(opener.request.get_header('Authorization'),'Bearer test-placeholder')
                body=json.loads(opener.request.data)
                self.assertEqual(body['model'],model)
                self.assertEqual(body['max_tokens'],1500)
                self.assertEqual(usage['total_tokens'],9)

    def test_missing_key_and_nonofficial_endpoint_fail_closed(self):
        with patch.dict(os.environ,{},clear=True):
            with self.assertRaisesRegex(RuntimeError,'QWEN_API_KEY'):
                agent.call_qwen([],agent.DEFAULT_MODEL)
        with patch.dict(os.environ,{'QWEN_API_KEY':'test-placeholder','QWEN_BASE_URL':'https://example.com'},clear=True):
            with self.assertRaisesRegex(ValueError,'official'):
                agent.call_qwen([],agent.DEFAULT_MODEL)

    def rules(self, **changes):
        value = {'title_xpath':'//h1','container_xpath':'//article','block_xpath':'./p', 'exclude_xpath':'','metadata_xpath':''}
        value.update(changes)
        return value

    def test_scalar_escape_overlap_empty_title_rejected(self):
        data=b'<h1>T</h1><article><div><p>Keep</p></div></article><p>Outside</p>'
        for rules in [self.rules(title_xpath='string(//h1)'),self.rules(block_xpath='//p'), self.rules(block_xpath='.//div|.//p')]:
            with self.subTest(rules=rules), self.assertRaises(ValueError):
                extract(rules,data)
        with self.assertRaisesRegex(ValueError,'empty'):
            extract(self.rules(),b'<h1></h1><article><p>text</p></article>')

    def test_partial_exclusion_rejected_full_exclusion_needs_review(self):
        data=b'<h1>T</h1><article><p>Keep <span>REMOVE</span> tail</p><p class="ad">Ad</p></article>'
        with self.assertRaisesRegex(ValueError,'Partial exclusion'):
            extract(self.rules(exclude_xpath='.//span'),data)
        result=extract(self.rules(exclude_xpath='./p[@class="ad"]'),data)
        issues=structural_feedback(result,data)
        self.assertEqual([i['kind'] for i in issues],['exclusion_requires_review'])
        self.assertEqual(agent.quality_status(issues), 'needs_review')
        self.assertEqual(agent.quality_status(issues + [{'kind':'empty_output'}]), 'failed')

    def test_pending_semantics_do_not_block_holdout_or_become_pass(self):
        original = agent.evaluate
        def evaluation(item,*args):
            row = original(item,*args)
            if not row['issues']:
                row['issues'] = [{'kind':'exclusion_requires_review'}]
                row['status'] = 'needs_review'
            return row
        with tempfile.TemporaryDirectory() as tmp, patch.object(agent,'evaluate',side_effect=evaluation):
            trace = agent.run(self.task(),tmp)
            self.assertEqual(trace['final_status'],'needs_review')
            self.assertTrue(trace['frozen_before_holdout'])
            self.assertEqual(len(trace['holdout']),2)
            self.assertEqual(len(trace['rounds']),2)

    def test_hidden_inline_caption_table_and_order(self):
        data=b'<h1>T</h1><article><p>Before <a>link</a></p><p hidden>Folded text</p><figcaption>Caption</figcaption><table><tr><td>A</td><td>B</td></tr></table></article>'
        result=extract(self.rules(block_xpath='./p|./figcaption|./table'),data)
        self.assertEqual([b['text'] for b in result['blocks']],['Before link','Folded text','Caption','AB'])
        self.assertEqual(result['blocks'][2]['type'],'caption')
        self.assertEqual(result['blocks'][3]['rows'],[['A','B']])
        self.assertEqual(structural_feedback(result,data),[])

    def test_export_reproduces_result_without_model_execution(self):
        rules=self.rules()
        data=b'<h1>T</h1><article><p>Body</p></article>'
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)/'extractor.py'
            path.write_text(export_python(rules),encoding='utf8')
            spec=importlib.util.spec_from_file_location('test_generated_extractor',path)
            module=importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)
            self.assertEqual(module.extract(data),extract(rules,data))

    def test_invalid_schema_and_no_overwrite(self):
        with self.assertRaises(ValueError):
            validate_rules({'code':'import os'})
        with tempfile.TemporaryDirectory() as tmp:
            (Path(tmp)/'trace.json').write_text('{}')
            with self.assertRaisesRegex(ValueError,'overwrite'):
                agent.run(self.task(),tmp)

if __name__=='__main__':
    unittest.main()
