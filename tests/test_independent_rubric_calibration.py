import unittest
from learning.run_independent_rubric_calibration import validate_review, QUESTIONS


class IndependentRubricCalibrationTests(unittest.TestCase):
    def setUp(self):
        self.task = {"task_id": "t", "cases": [{"case_id": "blind_01", "source_id": "source",
                                                   "output": [{"id": "o", "text": "y"}]}],
                     "sources": {"source": {"records": [{"id": "s", "text": "x"}]}}}

    def template(self):
        return {"task_id": "t", "cases": [{"case_id": "blind_01", "answers": [
            {"id": q, "verdict": "unknown", "reason": "evidence insufficient",
             "source_evidence": [{"id": "s", "quote": "x"}], "output_evidence": [{"id": "o", "quote": "y"}]}
            for q in QUESTIONS]}]}

    def test_valid_review_schema(self):
        self.assertEqual(validate_review(self.task, self.template()), [])

    def test_expected_shortcut_rejected(self):
        row = self.template()
        row["cases"][0]["answers"][0]["verdict"] = "expected"
        self.assertTrue(any("invalid verdict" in x for x in validate_review(self.task, row)))

    def test_todo_and_missing_evidence_rejected(self):
        row = self.template()
        row["cases"][0]["answers"][0]["reason"] = "TODO: reviewer decision"
        row["cases"][0]["answers"][0]["source_evidence"] = []
        errors = validate_review(self.task, row)
        self.assertTrue(any("missing reason" in x for x in errors))
        self.assertTrue(any("missing source_evidence" in x for x in errors))

    def test_question_order_is_fixed(self):
        row = self.template()
        row["cases"][0]["answers"].reverse()
        self.assertTrue(any("question order" in x for x in validate_review(self.task, row)))

    def test_fabricated_quote_rejected(self):
        row = self.template()
        row["cases"][0]["answers"][2]["source_evidence"][0]["quote"] = "fabricated"
        self.assertTrue(any("quote/id differs" in x for x in validate_review(self.task, row)))


if __name__ == "__main__":
    unittest.main()
