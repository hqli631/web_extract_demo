"""Report controls: recorded evidence remains intact and untrusted text stays inert."""
import json
from pathlib import Path
import tempfile
import unittest
from lxml import html
from project2_report import render_report

class ReportTests(unittest.TestCase):
    def trace(self):
        return dict(model='qwen3.8-flash',provider='dashscope',final_status='pass',input_pages=[
            dict(id='one',role='generation'),dict(id='two',role='final_holdout')],
            rounds=[dict(round=0,pages=[dict(id='one',role='generation',status='pass',result='one.json',issues=[])],issues=[])],
            holdout=[],api_attempts=[dict(round=0,status='succeeded',usage=dict(total_tokens=42))])

    def test_untrusted_body_metadata_and_rules_do_not_create_markup(self):
        with tempfile.TemporaryDirectory() as tmp:
            p=Path(tmp)
            payload='<img src=x onerror=alert(1)></script><script>bad()</script>'
            (p/'one.json').write_text(json.dumps(dict(title=payload,blocks=[dict(type='paragraph',text=payload,xpath='/html/body/p')],metadata=[dict(type='author',text=payload,xpath='/html/head/meta')],excluded=[],warnings=[])))
            (p/'candidate_round_0.json').write_text(json.dumps({'title_xpath':payload}))
            render_report(p,self.trace())
            dom=html.fromstring((p/'index.html').read_bytes())
            self.assertEqual(dom.xpath('//img'),[])
            self.assertEqual(len(dom.xpath('//script')),1)
            self.assertIn(payload,dom.text_content())

    def test_rebuild_only_changes_presentation_and_marks_skipped_holdout(self):
        with tempfile.TemporaryDirectory() as tmp:
            p=Path(tmp);trace=self.trace()
            trace['final_status']='development_failed'
            result=dict(title='Title',blocks=[],metadata=[],excluded=[],warnings=[])
            (p/'one.json').write_text(json.dumps(result))
            (p/'trace.json').write_text(json.dumps(trace))
            before={x.name:x.read_bytes() for x in p.iterdir()}
            render_report(p,trace)
            for name,data in before.items():
                self.assertEqual((p/name).read_bytes(),data)
            dom=html.fromstring((p/'index.html').read_bytes())
            self.assertIn('未执行',dom.text_content())
            self.assertEqual(len(dom.xpath('//article')),2)
            self.assertEqual(len(dom.xpath('//button[@role="tab"]')),4)

    def test_preserves_table_cells_and_code_indentation(self):
        with tempfile.TemporaryDirectory() as tmp:
            p=Path(tmp)
            result=dict(title='T',blocks=[dict(type='code_block',text='if True:\n    print(1)',xpath='/pre'),dict(type='table',text='AB',rows=[['A','B']],xpath='/table')],metadata=[],excluded=[],warnings=[])
            (p/'one.json').write_text(json.dumps(result))
            render_report(p,self.trace())
            dom=html.fromstring((p/'index.html').read_bytes())
            self.assertEqual(dom.xpath('//pre[@class="body-code"]/text()'),['if True:\n    print(1)'])
            self.assertEqual(dom.xpath('//table[@class="body-table"]//td/text()'),['A','B'])

    def test_untrusted_result_path_cannot_read_outside_report_directory(self):
        with tempfile.TemporaryDirectory() as tmp:
            trace=self.trace()
            trace['rounds'][0]['pages'][0]['result']='../outside.json'
            with self.assertRaises(ValueError):
                render_report(Path(tmp),trace)

    def test_failed_latest_candidate_is_not_shown_as_latest_success(self):
        with tempfile.TemporaryDirectory() as tmp:
            p=Path(tmp); trace=self.trace()
            (p/'one.json').write_text(json.dumps(dict(title='T',blocks=[],metadata=[],excluded=[],warnings=[])))
            trace['rounds'].append(dict(round=1,pages=[dict(id='one',role='generation',status='failed',issues=[dict(kind='execution_error',message='failed')])],issues=[]))
            render_report(p,trace)
            text=html.fromstring((p/'index.html').read_bytes()).text_content()
            self.assertIn('最近一轮未生成有效结果',text)

if __name__=='__main__':
    unittest.main()
