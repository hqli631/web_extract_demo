import json
from pathlib import Path
from lxml import html

project_dir = Path(__file__).resolve().parents[2]

# 当前三个固定样例的预期：
# 文件名、原始段落数、应排除的原始编号及理由。
cases = [
    (
        "blog_01.html",
        45,
        {1: "topic_navigation", 45: "editor_metadata"},
        {},
        {},
        list(range(2, 45)),
    ),
    (
        "collected_14a028de299edfab.html",
        23,
        {},
        {},
        {},
        list(range(1, 24)),
    ),
    (
        "collected_af5904c15d1deebc.html",
        17,
        {},
        {17: "article_source"},
        {3: "center_aligned_subheading", 10: "center_aligned_subheading", 11: "center_aligned_subheading"},
        list(range(1, 17)),
    ),
]

for filename, expected_count, expected_excluded, expected_sources, expected_subheadings, expected_content_indices in cases:
    source_path = project_dir / "samples" / filename
    result_path = (
        project_dir / "output" / "xpath_sina"
        / f"{source_path.stem}.json"
    )

    data = json.loads(result_path.read_text(encoding="utf-8"))
    raw = data["raw_blocks"]
    cleaned = data["cleaned_blocks"]
    excluded = data["excluded_blocks"]
    sources = data["source_blocks"]
    subheadings = data["subheading_blocks"]
    content = data["content_blocks"]

    assert data["file"] == filename, f"{filename}：结果对应错了网页"

    # 从原网页重新读取全部非空直接子 p，核对原始提取结果。
    tree = html.document_fromstring(source_path.read_bytes())
    containers = tree.xpath("//div[@id='artibody']")
    assert len(containers) == 1, f"{filename}：正文容器数量异常"

    source_blocks = []
    for node in containers[0].xpath("./p"):
        text = " ".join(node.text_content().split())
        if text:
            source_blocks.append({
                "index": len(source_blocks) + 1,
                "text": text,
                "xpath": tree.getroottree().getpath(node),
            })

    assert len(raw) == expected_count, f"{filename}：原始数量变化"
    assert raw == source_blocks, f"{filename}：原始文字、顺序或 XPath 不一致"

    # 既检查删掉哪段，也检查排除理由。
    actual_excluded = {
        block["index"]: block["reason"]
        for block in excluded
    }
    assert actual_excluded == expected_excluded, f"{filename}：排除项不符"
    assert len(excluded) == len(expected_excluded), f"{filename}：排除记录重复"
    actual_sources = {
        block["index"]: block["reason"]
        for block in sources
    }
    assert actual_sources == expected_sources, f"{filename}：文章来源字段不符"
    assert len(sources) == len(expected_sources), f"{filename}：文章来源记录重复"

    actual_subheadings = {
        block["index"]: block["reason"]
        for block in subheadings
    }
    assert actual_subheadings == expected_subheadings, f"{filename}：小标题字段不符"
    assert len(subheadings) == len(expected_subheadings), f"{filename}：小标题记录重复"
    assert all(b.get("type") == "subheading" for b in subheadings), f"{filename}：小标题类型不符"

    actual_content_indices = [block["index"] for block in content]
    assert actual_content_indices == expected_content_indices, f"{filename}：可读内容顺序不符"
    assert all(block.get("type") in {"paragraph", "subheading"} for block in content), f"{filename}：可读内容类型不符"

    # 清理后的内容必须完整对应原始段落，且保持顺序。
    expected_cleaned = [
        {**block, "type": "paragraph"} for block in raw
        if (
            block["index"] not in expected_excluded
            and block["index"] not in expected_sources
            and block["index"] not in expected_subheadings
        )
    ]
    assert cleaned == expected_cleaned, f"{filename}：保留内容或顺序变化"

    # 分类后可以增加类型和理由，原始文字、编号和路径必须原样保留。
    all_classified = cleaned + subheadings + sources + excluded
    assert sorted(b["index"] for b in all_classified) == [b["index"] for b in raw], f"{filename}：分类重复或遗漏"
    for block in all_classified:
        original = {
            key: block[key]
            for key in ("index", "text", "xpath")
        }
        assert original == raw[block["index"] - 1], "分类证据与原始记录不符"

    # 可读内容是普通段落与小标题按原始编号合并，不包含来源或杂质。
    assert content == sorted(cleaned + subheadings, key=lambda b: b["index"]), f"{filename}：可读内容与分类结果不符"

    print(
        f"PASS: {filename} "
        f"raw={len(raw)} kept={len(cleaned)} "
        f"sources={len(sources)} subheadings={len(subheadings)} "
        f"content={len(content)} excluded={len(excluded)}"
    )

print("ALL PASS: 3 pages checked.")
