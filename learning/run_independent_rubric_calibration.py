"""Prepare and compare blinded rubric reviews without fabricating labels."""
from __future__ import annotations
import argparse
import hashlib
import json
import random
from html import escape
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "output/stage4/calibration_v2/task.json"
OUT = ROOT / "output/stage5/rubrics_calibration_v1"
QUESTIONS = ("Q1", "Q2", "Q3", "Q4", "Q5")
VERDICTS = {"yes", "no", "unknown"}


def digest(value):
    raw = value if isinstance(value, bytes) else json.dumps(value, ensure_ascii=False, sort_keys=True).encode()
    return hashlib.sha256(raw).hexdigest()


def read(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def prepare():
    original = read(SOURCE)
    indices = list(range(len(original["cases"])))
    random.Random(4102026).shuffle(indices)
    cases = []
    for number, index in enumerate(indices, 1):
        case = original["cases"][index]
        cases.append({"case_id": f"blind_{number:02d}", "source_id": case["source_id"],
                      "execution_status": case.get("execution_status", "success"),
                      "output": case.get("output", []), "metadata": case.get("metadata", []),
                      "excluded": case.get("excluded", [])})
    task = {"schema_version": 1, "calibration_id": "rubrics-calibration-v1",
            "rubric": original["rubric"], "cases": cases,
            "sources": {c["source_id"]: original["sources"][c["source_id"]] for c in cases},
            "instructions": "只依据完整源证据和候选输出，逐题返回Q1-Q5。verdict只能yes/no/unknown，填写理由及source_evidence/output_evidence。不要返回总分，不要引用expected标签。",
            "origin": "historical controlled fixture; expected labels absent",
            "source_task_sha256": digest(original), "model_api_calls": 0, "training_updates": 0}
    task["task_id"] = "blind-" + digest(task)[:16]
    OUT.mkdir(parents=True, exist_ok=True)
    target = OUT / "task.json"
    if target.exists() and read(target) != task:
        raise ValueError("Frozen calibration task changed; create a new version.")
    target.write_text(json.dumps(task, ensure_ascii=False, indent=2), encoding="utf-8")
    for n in (1, 2):
        template = {"task_id": task["task_id"], "reviewer": f"fill_reviewer_{n}",
                    "independent_review": None, "review_context": "TODO: specify isolated review context", "cases": [
                        {"task_id": task["task_id"], "case_id": c["case_id"], "answers": [
                            {"id": q, "verdict": "unknown", "reason": "TODO: reviewer decision",
                             "source_evidence": [], "output_evidence": []} for q in QUESTIONS]}
                        for c in task["cases"]]}
        (OUT / f"reviewer_template_{n}.json").write_text(json.dumps(template, ensure_ascii=False, indent=2), encoding="utf-8")
    manifest = {"task_sha256": digest(task), "source_task_sha256": digest(original),
                "cases": len(cases), "labels_in_task": False, "reviewers_required": 2,
                "api_calls": 0, "training_updates": 0, "status": "PENDING_TWO_INDEPENDENT_REVIEWS",
                "limitations": ["Historical controlled fixtures, not new natural pages.",
                                "No accuracy without an independent gold review.",
                                "Current conversation knows old fixture and cannot serve as independent reviewer."]}
    (OUT / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    page = ["<!doctype html><meta charset='utf-8'><title>独立Rubrics校准准备</title>",
            "<style>body{font:16px/1.7 sans-serif;max-width:1100px;margin:30px auto}pre{white-space:pre-wrap;background:#f3f5f8;padding:15px}</style>",
            "<h1>独立 Rubrics 校准：等待两份盲评</h1>",
            "<p>任务不含expected标签、不计算分数、不调用模型。14个案例来自历史受控fixture，不能当作自然网页准确率。</p>",
            "<p>请把task.json交给两个彼此隔离的评审上下文，分别填写reviewer_template_1.json和reviewer_template_2.json。</p>",
            "<pre>" + escape(json.dumps(manifest, ensure_ascii=False, indent=2)) + "</pre>"]
    (OUT / "index.html").write_text("\\n".join(page), encoding="utf-8")
    print(f"PREPARED: {len(cases)} blinded cases; expected labels absent; reviewers=2; API calls=0")
    print(OUT / "index.html")


def validate_review(task, review):
    errors = []
    if review.get("task_id") != task["task_id"]:
        errors.append("task_id mismatch")
    rows = review.get("cases")
    if not isinstance(rows, list) or [r.get("case_id") for r in rows] != [c["case_id"] for c in task["cases"]]:
        errors.append("case order/id mismatch")
        return errors
    for row in rows:
        case = next(c for c in task["cases"] if c["case_id"] == row["case_id"])
        records = {
            "source_evidence": {r["id"]: r["text"] for r in task["sources"][case["source_id"]]["records"]},
            "output_evidence": {r["id"]: r["text"] for r in case["output"]}}
        answers = row.get("answers")
        if not isinstance(answers, list) or [a.get("id") for a in answers] != list(QUESTIONS):
            errors.append(row["case_id"] + ": question order/missing")
            continue
        for answer in answers:
            if answer.get("verdict") not in VERDICTS:
                errors.append(row["case_id"] + "/" + answer["id"] + ": invalid verdict")
            if not isinstance(answer.get("reason"), str) or not answer["reason"].strip() or answer["reason"].startswith("TODO:"):
                errors.append(row["case_id"] + "/" + answer["id"] + ": missing reason")
            for field in ("source_evidence", "output_evidence"):
                refs = answer.get(field)
                if not isinstance(refs, list) or not refs:
                    errors.append(row["case_id"] + "/" + answer["id"] + ": missing " + field)
                elif any(not isinstance(x, dict) or not x.get("id") or not x.get("quote") for x in refs):
                    errors.append(row["case_id"] + "/" + answer["id"] + ": malformed evidence")
                else:
                    for ref in refs:
                        if ref["id"] not in records[field] or ref["quote"] not in records[field][ref["id"]]:
                            errors.append(row["case_id"] + "/" + answer["id"] + ": evidence quote/id differs from record")
    return errors


def compare():
    task = read(OUT / "task.json")
    reviews = [read(OUT / f"reviewer_{n}.json") for n in (1, 2)]
    errors = [validate_review(task, r) for r in reviews]
    if any(errors):
        raise ValueError(json.dumps({"review_errors": errors}, ensure_ascii=False, indent=2))
    if any(not isinstance(r.get("reviewer"), str) or r["reviewer"].startswith("fill_") for r in reviews):
        raise ValueError("Record actual reviewer identity, not template placeholder.")
    if reviews[0]["reviewer"] == reviews[1]["reviewer"]:
        raise ValueError("Two reviews must record distinct reviewer context identities.")
    matrix = {q: {"same": 0, "different": 0, "unknown_in_pair": 0} for q in QUESTIONS}
    disagreements = []
    for left, right in zip(reviews[0]["cases"], reviews[1]["cases"]):
        for a, b in zip(left["answers"], right["answers"]):
            q = a["id"]
            if "unknown" in (a["verdict"], b["verdict"]):
                matrix[q]["unknown_in_pair"] += 1
            if a["verdict"] == b["verdict"]:
                matrix[q]["same"] += 1
            else:
                matrix[q]["different"] += 1
                disagreements.append({"case_id": left["case_id"], "question": q,
                                      "reviewer_1": a["verdict"], "reviewer_2": b["verdict"],
                                      "reason_1": a["reason"], "reason_2": b["reason"]})
    total = len(task["cases"])
    report = {"calibration_id": task["calibration_id"], "task_sha256": digest(task),
              "cases": total, "questions": len(QUESTIONS), "pair_count": total * len(QUESTIONS),
              "per_question": matrix,
              "overall_pair_agreement": sum(x["same"] for x in matrix.values()) / (total * len(QUESTIONS)),
              "disagreements": disagreements, "independent_human_gold": False,
              "accuracy": None, "reward_frozen": False, "grpo_ready": False,
              "independent_review_declared": all(r.get("independent_review") is True for r in reviews),
              "independent_context_verified_by_program": False,
              "api_calls": 0, "training_updates": 0,
              "interpretation": "Pair agreement is reviewer consistency, not accuracy; unknown is not mapped to no.",
              "fixture_limit": "Historical controlled cases; natural unseen webpage calibration remains pending."}
    (OUT / "comparison.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    page = ["<!doctype html><meta charset='utf-8'><title>Rubrics双评校准</title>",
            "<style>body{font:16px/1.7 sans-serif;max-width:1100px;margin:30px auto}td,th{border:1px solid #ccc;padding:8px}table{border-collapse:collapse}pre{white-space:pre-wrap;background:#f3f5f8;padding:12px}</style>",
            "<h1>Rubrics 双评一致性</h1><p><strong>一致性不是准确率；当前仍不是可信reward。</strong></p>",
            "<pre>" + escape(json.dumps(report, ensure_ascii=False, indent=2)) + "</pre>",
            "<p>需要独立金标/第三方复核，才能讨论准确性和冻结reward。</p>"]
    (OUT / "index.html").write_text("\\n".join(page), encoding="utf-8")
    print("COMPARE PASS: pair agreement computed; accuracy=None; reward_frozen=False; grpo_ready=False")
    print(OUT / "index.html")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--prepare", action="store_true")
    parser.add_argument("--compare", action="store_true")
    args = parser.parse_args()
    if args.prepare:
        prepare()
    elif args.compare:
        compare()
    else:
        parser.error("use --prepare or --compare")
