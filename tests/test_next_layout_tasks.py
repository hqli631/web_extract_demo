import hashlib
import json
import tempfile
import unittest
from pathlib import Path

from learning.prepare_next_layout_tasks import check, template, validate


class NextLayoutTaskTests(unittest.TestCase):
    def _ready(self, root: Path):
        rows = []
        for task_number in range(3):
            pages = []
            for role, count in (("train", 2), ("dev", 1), ("test", 1)):
                for index in range(count):
                    rel = Path(f"pages/c{task_number}_{role}_{index}.html")
                    path = root / rel
                    path.parent.mkdir(parents=True, exist_ok=True)
                    path.write_text(f"<html><h1>{task_number}-{role}-{index}</h1></html>", encoding="utf-8")
                    digest = hashlib.sha256(path.read_bytes()).hexdigest()
                    pages.append({"role": role, "exposure": "new", "path": rel.as_posix(),
                                  "url": f"https://example.test/{task_number}/{role}/{index}", "sha256": digest})
            rows.append({"task_id": f"new_task_{task_number}", "layout_family": f"family_{task_number}",
                         "status": "ready", "pages": pages,
                         "target_code": {"path": f"targets/t{task_number}.py", "sha256": ""}})
            target = root / f"targets/t{task_number}.py"
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text("def extract(data): return {}\n", encoding="utf-8")
            rows[-1]["target_code"]["sha256"] = hashlib.sha256(target.read_bytes()).hexdigest()
        value = template()
        value["clusters"] = rows
        value["known_exposed_task_ids"] = ["sina_shell_v2", "chinanews_shell_v2"]
        return value

    def test_draft_template_is_explicitly_pending(self):
        value = template()
        result = {"errors": validate(value, check_files=False)}
        self.assertEqual(result["errors"], [])
        self.assertEqual(sum(c["status"] == "todo" for c in value["clusters"]), 3)

    def test_ready_three_tasks_allows_independent_test_claim(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            import learning.prepare_next_layout_tasks as mod
            old = mod.ROOT
            try:
                mod.ROOT = root
                value = self._ready(root)
                self.assertEqual(validate(value), [])
                path = root / "tasks.json"
                path.write_text(json.dumps(value), encoding="utf-8")
                result = check(path)
                self.assertEqual(result["status"], "PASS")
                self.assertTrue(result["unseen_page_test_registration_allowed"])
                self.assertFalse(result["cross_layout_generalization_claim_allowed"])
            finally:
                mod.ROOT = old

    def test_test_page_must_be_new(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            import learning.prepare_next_layout_tasks as mod
            old = mod.ROOT
            try:
                mod.ROOT = root
                value = self._ready(root)
                value["clusters"][0]["pages"][-1]["exposure"] = "historical_exposed"
                self.assertTrue(any("test exposure must be new" in e for e in validate(value)))
            finally:
                mod.ROOT = old

    def test_cross_task_hash_and_url_are_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            import learning.prepare_next_layout_tasks as mod
            old = mod.ROOT
            try:
                mod.ROOT = root
                value = self._ready(root)
                value["clusters"][1]["pages"][0]["sha256"] = value["clusters"][0]["pages"][0]["sha256"]
                value["clusters"][1]["pages"][1]["url"] = value["clusters"][0]["pages"][1]["url"]
                errors = validate(value)
                self.assertTrue(any("cross-task/content hash" in e for e in errors))
                self.assertTrue(any("cross-task/url" in e for e in errors))
            finally:
                mod.ROOT = old

    def test_missing_source_hash_and_path_escape_are_rejected(self):
        value = template()
        value["clusters"][0]["pages"] = [{"role": "train", "exposure": "new", "path": "../secret.html",
                                            "url": "https://example.test/a", "sha256": "0" * 64}]
        errors = validate(value, check_files=False)
        self.assertTrue(any("escapes repository" in e for e in errors))
        value["clusters"][0]["pages"][0]["path"] = "x.html"
        value["clusters"][0]["pages"][0]["sha256"] = "bad"
        self.assertTrue(any("64 hex" in e for e in validate(value, check_files=False)))


if __name__ == "__main__":
    unittest.main()
