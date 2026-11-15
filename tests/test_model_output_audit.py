import unittest
from learning.audit_model_outputs import audit_text

class ModelOutputAuditTests(unittest.TestCase):
    def test_current_style_rejected(self):
        r=audit_text("import re\ndef extract(data):\n metadata={}\n return {'title_candidates': [], 'metadata': metadata, 'blocks': [], 'excluded': [], 'warnings': []}",'train')
        self.assertFalse(r['accepted'])
        self.assertIn('missing_sina_artibody_container',r['issues'])
        self.assertIn('metadata_dict_assignment',r['issues'])

    def test_no_semantic_claim(self):
        r=audit_text("from lxml import html\ndef extract(data):\n return {'title':'','blocks':[],'metadata':[],'excluded':[],'warnings':[]}",'train')
        self.assertEqual(r['quality_evaluation'],'not_run')
        self.assertFalse(r['executed'])

    def test_syntax_error(self):
        r=audit_text('def extract(:','train')
        self.assertFalse(r['python_parse'])
        self.assertFalse(r['accepted'])

    def test_wrong_xpath_evidence_is_detected(self):
        r=audit_text("def extract(data):\n xpath=node.get('xpath','')\n text=node.find('.//p/text()')\n return {}",'dev')
        self.assertIn('reads_xpath_attribute_instead_of_computing_dom_path',r['issues'])
        self.assertIn('element_find_does_not_support_xpath_text_function',r['issues'])

    def test_bytes_regex_mismatch_detected_without_execution(self):
        r=audit_text("import re\ndef extract(data):\n return re.search('<article>',data)",'train')
        self.assertIn('string_regex_pattern_used_on_bytes_input',r['issues'])
        self.assertFalse(r['executed'])

if __name__=='__main__':
    unittest.main()
