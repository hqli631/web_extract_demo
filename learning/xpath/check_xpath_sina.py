import json
from pathlib import Path

# 根据脚本所在位置定位项目，不依赖终端当前目录。
project_dir = Path(__file__).resolve().parents[2]
result_path = project_dir / "output" / "xpath_sina" / "blog_01.json"

data = json.loads(result_path.read_text(encoding="utf-8"))

raw = data["raw_blocks"]
cleaned = data["cleaned_blocks"]
excluded = data["excluded_blocks"]

assert len(raw) == 45, "原始段落数量与当前练习样本不符"
assert len(cleaned) == 43, "清理后数量不符"
assert len(excluded) == 2, "排除数量不符"

# 每个原始编号必须恰好进入清理结果或排除记录。
all_indices = [x["index"] for x in cleaned + excluded]
assert sorted(all_indices) == [x["index"] for x in raw], "存在遗漏或重复分配"

# Python 列表下标从 0 开始：raw[1] 是第 2 段。
assert {**raw[1], "type": "paragraph"} in cleaned, "误删了含正常链接的正文段落"

# -2 表示倒数第 2 段，即本样本的风险声明。
assert {**raw[-2], "type": "paragraph"} in cleaned, "误删了风险声明"

kept_indices = [x["index"] for x in cleaned]
assert kept_indices == sorted(kept_indices), "正文顺序发生变化"

print("PASS：当前样本的全部检查通过。")
print(f"原始 {len(raw)} 段，保留 {len(cleaned)} 段，排除 {len(excluded)} 段。")
print("正常链接段落与风险声明保留，段落顺序正确。")
