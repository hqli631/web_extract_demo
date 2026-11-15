import unittest
from learning.report_cloud_sft import inspect_text


class CloudSFTReportTests(unittest.TestCase):
    def test_parse_does_not_imply_contract_valid(self):
        result = inspect_text("def extract(data):\n    metadata={}\n    return {'title_candidates': [], 'metadata': metadata}\n")
        self.assertTrue(result['python_parse'])
        self.assertFalse(result['executed'])
        self.assertIn('literal return keys differ from output contract', result['issues'])
        self.assertIn('metadata is dict; contract requires list', result['issues'])

    def test_malformed_output_is_not_executed(self):
        result = inspect_text('def extract(:')
        self.assertFalse(result['python_parse'])
        self.assertFalse(result['executed'])
