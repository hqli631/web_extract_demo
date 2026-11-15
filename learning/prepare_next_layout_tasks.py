"""Register future layout-cluster tasks and check split/leakage boundaries.

This module deliberately does not fetch webpages. A human supplies stable URLs and
saved HTML snapshots first; the checker then verifies provenance and task-level
train/dev/test separation before any model or rule sees the test pages.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DEFAULT = ROOT / "config/next_layout_tasks.json"
ROLES = {"train", "dev", "test"}
EXPOSURES = {"new", "historical_exposed", "pending"}


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def template() -> dict:
    return {
        "format_version": 1,
        "status": "draft",
        "purpose": "Register new natural layout-cluster tasks before generation or training.",
        "rule": "A cluster is one code-generation task; never random-split pages or prompt variants.",
        "clusters": [
            {
                "task_id": "future_cluster_01",
                "layout_family": "TODO_news_or_blog",
                "status": "todo",
                "pages": [],
                "target_code": None,
                "notes": "Add 2-3 train pages, 1 dev page and at least 1 unseen test page.",
            },
            {
                "task_id": "future_cluster_02",
                "layout_family": "TODO_interview_or_forum",
                "status": "todo",
                "pages": [],
                "target_code": None,
                "notes": "Use a genuinely different DOM layout; do not copy a prior target.",
            },
            {
                "task_id": "future_cluster_03",
                "layout_family": "TODO_table_or_caption_variant",
                "status": "todo",
                "pages": [],
                "target_code": None,
                "notes": "Cover tables/captions or folded content and record image unknowns.",
            },
        ],
        "known_exposed_task_ids": ["sina_shell_v2", "chinanews_shell_v2"],
    }


def _safe_path(value: str) -> Path:
    path = (ROOT / value).resolve()
    if not path.is_relative_to(ROOT.resolve()):
        raise ValueError(f"path escapes repository: {value}")
    return path


def validate(config: dict, *, check_files: bool = True) -> list[str]:
    errors: list[str] = []
    if config.get("format_version") != 1:
        errors.append("format_version must be 1")
    clusters = config.get("clusters")
    if not isinstance(clusters, list) or not clusters:
        return errors + ["clusters must be a non-empty list"]
    ids: set[str] = set()
    seen_path: dict[str, str] = {}
    seen_hash: dict[str, str] = {}
    seen_url: dict[str, str] = {}
    for cluster in clusters:
        task = cluster.get("task_id")
        if not isinstance(task, str) or not task:
            errors.append("cluster missing task_id")
            continue
        if task in ids:
            errors.append(f"duplicate task_id: {task}")
        ids.add(task)
        if task in set(config.get("known_exposed_task_ids", [])):
            errors.append(f"task reuses historically exposed id: {task}")
        pages = cluster.get("pages")
        if not isinstance(pages, list):
            errors.append(f"{task}: pages must be a list")
            continue
        counts = {role: 0 for role in ROLES}
        for number, page in enumerate(pages):
            prefix = f"{task}.pages[{number}]"
            if not isinstance(page, dict):
                errors.append(prefix + ": page must be an object")
                continue
            role, exposure = page.get("role"), page.get("exposure")
            if role not in ROLES:
                errors.append(prefix + ": role must be train/dev/test")
            else:
                counts[role] += 1
            if exposure not in EXPOSURES:
                errors.append(prefix + ": exposure must be new/historical_exposed/pending")
            if role == "test" and exposure != "new":
                errors.append(prefix + ": test exposure must be new")
            path_value = page.get("path")
            if not isinstance(path_value, str) or not path_value:
                errors.append(prefix + ": missing saved HTML path")
                continue
            if path_value in seen_path:
                errors.append(f"cross-task/path duplicate: {path_value} ({seen_path[path_value]}, {task})")
            seen_path[path_value] = task
            try:
                _safe_path(path_value)
            except ValueError as exc:
                errors.append(prefix + ": " + str(exc))
            if check_files:
                try:
                    path = _safe_path(path_value)
                    if not path.is_file():
                        errors.append(prefix + ": saved HTML does not exist")
                    digest = sha256(path)
                    if page.get("sha256") != digest:
                        errors.append(prefix + ": sha256 does not match saved bytes")
                except (OSError, ValueError) as exc:
                    errors.append(prefix + ": " + str(exc))
            digest_value = page.get("sha256")
            if not isinstance(digest_value, str) or not re.fullmatch(r"[0-9a-fA-F]{64}", digest_value):
                errors.append(prefix + ": sha256 must be 64 hex characters")
            elif digest_value in seen_hash:
                errors.append(f"cross-task/content hash duplicate: {digest_value} ({seen_hash[digest_value]}, {task})")
            else:
                seen_hash[digest_value] = task
            url = page.get("url")
            if not isinstance(url, str) or not url.startswith(("http://", "https://")):
                errors.append(prefix + ": url must be an http(s) URL")
            elif url in seen_url:
                errors.append(f"cross-task/url duplicate: {url}")
            else:
                seen_url[url] = task
        if cluster.get("status") == "ready":
            for role, minimum in (("train", 2), ("dev", 1), ("test", 1)):
                if counts[role] < minimum:
                    errors.append(f"{task}: ready cluster needs at least {minimum} {role} pages")
            target = cluster.get("target_code")
            if not isinstance(target, dict) or not target.get("path") or not re.fullmatch(r"[0-9a-fA-F]{64}", str(target.get("sha256", ""))):
                errors.append(f"{task}: ready cluster needs reviewed target_code path and SHA256")
            elif check_files:
                try:
                    target_path = _safe_path(target["path"])
                    if not target_path.is_file():
                        errors.append(f"{task}: target_code does not exist")
                    elif sha256(target_path) != target["sha256"]:
                        errors.append(f"{task}: target_code SHA256 does not match")
                except (OSError, ValueError) as exc:
                    errors.append(f"{task}: target_code: {exc}")
        if counts["test"] and any(p.get("role") == "test" and p.get("exposure") != "new" for p in pages):
            errors.append(f"{task}: test pages must remain unseen/new")
    return errors


def check(path: Path, *, check_files: bool = True) -> dict:
    config = json.loads(path.read_text(encoding="utf-8"))
    errors = validate(config, check_files=check_files)
    clusters = config.get("clusters", [])
    ready = sum(c.get("status") == "ready" for c in clusters if isinstance(c, dict))
    exposure_receipt = ROOT / 'output/stage5/multitask/test_exposure.json'
    exposed = exposure_receipt.exists() and any(c.get('task_id') in {'python_sphinx_v1','sqlite_document_v1','pg_essay_v1'} for c in clusters)
    return {"status": "PASS" if not errors else "FAIL", "errors": errors,
            "clusters": len(clusters), "ready_clusters": ready,
            "unseen_page_test_registration_allowed": bool(clusters) and not errors and ready >= 3 and not exposed,
            "test_pages_final_evaluation_exposed": exposed,
            "cross_layout_generalization_claim_allowed": False}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, default=DEFAULT)
    parser.add_argument("--write-template", action="store_true")
    parser.add_argument("--allow-missing-files", action="store_true")
    args = parser.parse_args()
    path = args.config if args.config.is_absolute() else ROOT / args.config
    if args.write_template:
        path.parent.mkdir(parents=True, exist_ok=True)
        if path.exists():
            raise SystemExit(f"refusing to overwrite existing config: {path}")
        path.write_text(json.dumps(template(), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        print(f"WROTE DRAFT TEMPLATE: {path}")
        return
    report = check(path, check_files=not args.allow_missing_files)
    print(json.dumps(report, ensure_ascii=False, indent=2))
    if report["errors"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
