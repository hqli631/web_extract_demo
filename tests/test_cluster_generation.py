import unittest
import subprocess
from pathlib import Path
from learning.run_cluster_generation import ROOT, execute, check_code, validate


class ClusterGenerationTests(unittest.TestCase):
    def source(self,name):
        return (ROOT/f'learning/generated/{name}_v1.py').read_text(encoding='utf-8')

    def test_same_code_handles_unseen_synthetic_text_and_inline_link(self):
        data=b'<h1 class="main-title">New title</h1><div id="artibody"><p>Before <a>link</a> after.</p><p cms-style="font-L align-Center">Heading</p></div>'
        result=execute(self.source('sina'),data)
        validate(result,data)
        self.assertEqual(result['title'],'New title')
        self.assertEqual([b['text'] for b in result['blocks']],['Before link after.','Heading'])
        self.assertEqual(result['blocks'][1]['kind'],'subheading')

    def test_table_order_and_rows_not_flattened(self):
        data=b'<h1 class="main-title">T</h1><div id="artibody"><p>A</p><table><tr><th>X</th><td>Y</td></tr></table><p>B</p></div>'
        result=execute(self.source('sina'),data)
        validate(result,data)
        self.assertEqual([b['kind'] for b in result['blocks']],['paragraph','table','paragraph'])
        self.assertEqual(result['blocks'][1]['rows'],[['X','Y']])

    def test_chinanews_title_author_and_interview(self):
        data='''<meta charset="utf-8"><h1>duplicate display title</h1><h1 class="content_left_title">Article</h1><div class="left_zw"><p>中新社记者 张三</p><p>中新社记者：问题？</p><div class="pictext">Caption</div><table class="adInContent"><tr><td>ad</td></tr></table></div>'''.encode()
        result=execute(self.source('chinanews'),data)
        validate(result,data)
        self.assertEqual(result['metadata'][0]['kind'],'author')
        self.assertEqual(result['blocks'][0]['text'],'中新社记者：问题？')
        self.assertEqual(result['excluded'][0]['kind'],'advertisement_or_page_widget')

    def test_bad_selector_fails_instead_of_silent_empty(self):
        with self.assertRaises(ValueError):
            execute(self.source('sina'),b'<h1>Other</h1><p>text</p>')

    def test_capability_check_and_timeout(self):
        for code in ['import os\ndef extract(data): return {}','def extract(data): return open("x").read()']:
            with self.assertRaises(ValueError):
                check_code(code)
        with self.assertRaises(subprocess.TimeoutExpired):
            execute('def extract(data):\n    while True: pass',b'<p>x</p>',timeout=.2)

    def test_validator_catches_modified_quote(self):
        data=b'<h1 class="main-title">T</h1><div id="artibody"><p>A</p></div>'
        result=execute(self.source('sina'),data)
        result['blocks'][0]['text']='invented'
        with self.assertRaises(ValueError):
            validate(result,data)


if __name__=='__main__':
    unittest.main()
