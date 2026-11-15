import unittest
from learning.evaluate_multitask import source_only,gate,validate_result

class MultitaskEvaluationTests(unittest.TestCase):
    def test_fence_normalization_only(self):
        fence=chr(96)*3
        self.assertEqual(source_only(fence+'python\ndef extract(data):\n    return {}\n'+fence),('def extract(data):\n    return {}',True))
        with self.assertRaises(ValueError):source_only(fence+'python\nx=1')
    def test_policy_is_not_sandbox(self):
        gate('from lxml import html\ndef extract(data):\n    return {}')
        for code in ['import os\ndef extract(data):return {}','def extract(data): return open("x")','def extract(data):return data.__class__']:
            with self.assertRaises(ValueError):gate(code)
    def test_contract_and_source_order(self):
        raw=b'<h1>Title</h1><div><p>First</p><p>Second</p></div>'
        result=dict(title='Title',blocks=[dict(kind='paragraph',text='First',xpath='/html/body/div/p[1]'),dict(kind='paragraph',text='Second',xpath='/html/body/div/p[2]')],metadata=[],excluded=[],warnings=[])
        self.assertEqual(validate_result(result,raw),[])
        result['blocks'].reverse()
        self.assertIn('body_order_changed',validate_result(result,raw))
        result['metadata']={}
        self.assertIn('metadata_not_list',validate_result(result,raw))

if __name__=='__main__':unittest.main()
