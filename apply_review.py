from pathlib import Path
import csv
import json


ROOT = Path(__file__).resolve().parent
RESULTS = ROOT / "output" / "results.json"
REVIEW = ROOT / "reports" / "region_review.csv"
OUTPUT = ROOT / "output" / "corrected_results.json"


def main() -> None:
    labels = {}
    with REVIEW.open(encoding="utf-8-sig", newline="") as f:
        for row in csv.DictReader(f):
            label = row["manual_label"].strip()
            if label:
                labels[(row["file"], row["region_id"])] = label

    data = json.loads(RESULTS.read_text(encoding="utf-8"))
    output = []
    counts = {"正文": 0, "杂质": 0, "缺漏": 0, "未标注": 0}
    for page in data:
        accepted = []
        for region in page.get("regions", []):
            label = labels.get((page["file"], str(region["region_id"])), "")
            final_label = label or ("正文" if region["auto_label"] in {"正文候选", "标题/小标题"} else "未标注")
            counts[final_label] = counts.get(final_label, 0) + 1
            region["final_label"] = final_label
            if final_label in {"正文", "缺漏"}:
                accepted.append(region["text"])
        output.append({"file": page["file"], "title": page["title"], "content": "\n".join(accepted), "regions": page["regions"]})

    OUTPUT.write_text(json.dumps(output, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"已生成: {OUTPUT}")
    print("区域统计:", counts)


if __name__ == "__main__":
    main()
