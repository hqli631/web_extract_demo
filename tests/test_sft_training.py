"""CPU-only guards; no model or tokenizer downloads."""
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest

PATH = Path(__file__).resolve().parents[1] / "training/minimal_sft.py"
spec = importlib.util.spec_from_file_location("minimal_sft", PATH)
sft = importlib.util.module_from_spec(spec)
spec.loader.exec_module(sft)


class FakeTokenizer:
    def apply_chat_template(self, messages, tokenize=True, add_generation_prompt=False):
        return [10, 11, 20] if add_generation_prompt else [10, 11, 20, 30, 31, 99]


class TrainingPreparationTest(unittest.TestCase):
    def setUp(self):
        self.row = {"messages": [{"role": role, "content": "sample"} for role in ("system", "user", "assistant")]}

    def test_masks_prompt_preserves_answer_and_end_token(self):
        encoded, length = sft.encode_example(FakeTokenizer(), self.row, 6)
        self.assertEqual(length, 3)
        self.assertEqual(encoded["labels"], [-100, -100, -100, 30, 31, 99])
        self.assertEqual(encoded["input_ids"], [10, 11, 20, 30, 31, 99])

    def test_overlong_is_rejected_never_truncated(self):
        with self.assertRaisesRegex(ValueError, "no truncation"):
            sft.encode_example(FakeTokenizer(), self.row, 5)

    def test_template_prefix_mismatch_is_rejected(self):
        class BadTokenizer(FakeTokenizer):
            def apply_chat_template(self, messages, tokenize=True, add_generation_prompt=False):
                return [50, 60] if add_generation_prompt else [50, 70, 80]
        with self.assertRaisesRegex(ValueError, "prefix mismatch"):
            sft.encode_example(BadTokenizer(), self.row, 99)

    def test_missing_supervised_tokens_is_rejected(self):
        class EmptyTokenizer(FakeTokenizer):
            def apply_chat_template(self, *args, **kwargs):
                return [50, 60]
        with self.assertRaisesRegex(ValueError, "no supervised"):
            sft.encode_example(EmptyTokenizer(), self.row, 99)

    def test_model_revision_must_be_frozen_commit(self):
        for rev in (None, "main", "a" * 39, "g" * 40):
            with self.assertRaises(ValueError):
                sft.require_revision({"model_revision": rev})
        sft.require_revision({"model_revision": "a" * 40})

    def test_schema_rejects_multiple_assistant_turns(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "train.jsonl"
            bad = {"messages": self.row["messages"] + [{"role": "assistant", "content": "extra"}]}
            path.write_text(json.dumps(bad), encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "exactly"):
                sft.load_rows(path)

    def test_schema_keeps_trace_metadata(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "train.jsonl"
            self.row["task_id"] = "traceable-task"
            path.write_text(json.dumps(self.row), encoding="utf-8")
            self.assertEqual(sft.load_rows(path)[0]["task_id"], "traceable-task")

    def test_cloud_config_has_finite_smoke_default(self):
        cfg = json.loads((PATH.parent / "minimal_sft.json").read_text(encoding="utf-8"))
        sft.validate_config(cfg)
        self.assertEqual(cfg["max_steps"], 1)
        sft.require_revision(cfg)

    def test_preflight_rejects_changed_data_before_weights_download(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            path = root / "train.jsonl"
            path.write_text("original", encoding="utf-8")
            cfg = {"model_revision": "a" * 40}
            with self.assertRaisesRegex(ValueError, "run tokenize"):
                sft.check_preflight(cfg, {"train": path}, root)
            sft.write_json(root / "preflight_manifest.json", sft.material_fingerprint(cfg, {"train": path}))
            sft.check_preflight(cfg, {"train": path}, root)
            path.write_text("changed", encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "data changed"):
                sft.check_preflight(cfg, {"train": path}, root)


if __name__ == "__main__":
    unittest.main()
