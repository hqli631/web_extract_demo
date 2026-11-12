import sys
import json
import hashlib
from pathlib import Path
from lxml import html


# 脚本位于 learning/xpath，向上两层定位项目根目录。
project_dir = Path(__file__).resolve().parents[2]
rules_path = project_dir / "config" / "xpath_sina.json"

with rules_path.open("r", encoding="utf-8") as file:
    rules = json.load(file)

print(f"使用规则：{rules['name']}，版本：{rules['version']}")
# 命令行指定文件名；没有指定时，仍使用第一个样本。
sample_name = (
    sys.argv[1]
    if len(sys.argv) > 1
    else "blog_01.html"
)

sample_path = project_dir / "samples" / sample_name
print(f"正在处理：{sample_path.name}")

if not sample_path.exists():
    raise FileNotFoundError(f"没有找到网页文件：{sample_path}")

# 以字节读取，让 lxml 根据 HTML 中的编码声明解析。
page_bytes = sample_path.read_bytes()
tree = html.document_fromstring(page_bytes)

# 1. 提取标题：先取第一个非空的 h1。
title_elements = tree.xpath(rules["title_xpath"])
titles = [
    " ".join(element.text_content().split())
    for element in title_elements
]
titles = [title for title in titles if title]
title = titles[0] if titles else "未找到标题"

# 2. 找到正文容器。
containers = tree.xpath(rules["container_xpath"])

print(f"标题：{title}")
print(f"找到正文容器：{len(containers)} 个")
print()

if len(containers) != 1:
    print("提示：正文容器不是 1 个，请检查保存的网页和 XPath。")

# 3. 本次先收集容器内全部直接子 p，再逐条判断。
# 故意不使用已经排除编辑信息的 block_xpath，
# 这样可以保留清理前的候选段落和排除证据。
if len(containers) != 1:
    raise ValueError("本练习要求恰好找到一个正文容器")

container = containers[0]
raw_blocks = []
cleaned_blocks = []
excluded_blocks = []
source_blocks = []
subheading_blocks = []
content_blocks = []

for node in container.xpath("./p"):
    text = " ".join(node.text_content().split())
    if not text:
        continue

    record = {
        "index": len(raw_blocks) + 1,
        "text": text,
        "xpath": tree.getroottree().getpath(node),
    }
    raw_blocks.append(record)

    classes = (node.get("class") or "").split()
    reason = None

    # 条件一：责任编辑属于页面元数据。
    if "article-editor" in classes:
        reason = "editor_metadata"

    # 条件二：整段文字来自新浪专题链接。
    else:
        links = node.xpath("./a")
        if len(links) == 1:
            link = links[0]
            link_text = " ".join(link.text_content().split())
            href = link.get("href") or ""

            if (
                text == link_text
                and link_text.startswith("专题：")
                and href.startswith("https://finance.sina.com.cn/zt_d/")
            ):
                reason = "topic_navigation"

    # 条件三：文章来源单独进入 source_blocks。
    is_source = (
        text.startswith("（文章来源：")
        and text.endswith("）")
    )

    # 条件四：当前开发样例中确认过的小标题具有居中样式。
    # 这是模板启发式，居中图片说明或其他居中文字也可能命中，尚未验证通用性。
    is_subheading = "align-Center" in (node.get("cms-style") or "").split()

    if is_source:
        source_blocks.append({
            **record,
            "reason": "article_source",
        })
    elif reason is not None:
        excluded_blocks.append({
            **record,
            "reason": reason,
        })
    elif is_subheading:
        classified = {
            **record,
            "type": "subheading",
            "reason": "center_aligned_subheading",
            "evidence": {"cms-style": node.get("cms-style")},
        }
        subheading_blocks.append(classified)
        content_blocks.append(classified)
    else:
        classified = {
            **record,
            "type": "paragraph",
        }
        cleaned_blocks.append(classified)
        content_blocks.append(classified)

result = {
    "file": sample_path.name,
    "source_sha256": hashlib.sha256(page_bytes).hexdigest(),
    "title": title,
    "rules": rules,
    "candidate_xpath": "./p",
    "cleanup_policy_version": 3,
    "scope": "可读正文保留段落、小标题及风险声明；来源单列；专题导航与责任编辑排除",
    "subheading_rule_note": "居中样式为当前模板的小标题线索，不保证其他网页的居中文字都是标题。",
    "raw_blocks": raw_blocks,
    "cleaned_blocks": cleaned_blocks,
    "source_blocks": source_blocks,
    "subheading_blocks": subheading_blocks,
    "content_blocks": content_blocks,
    "excluded_blocks": excluded_blocks,
}

output_dir = project_dir / "output" / "xpath_sina"
output_dir.mkdir(parents=True, exist_ok=True)
output_path = output_dir / f"{sample_path.stem}.json"

output_path.write_text(
    json.dumps(result, ensure_ascii=False, indent=2),
    encoding="utf-8",
)

print(f"原始非空段落：{len(raw_blocks)}")
print(f"清理后正文段落：{len(cleaned_blocks)}")
print(f"文章来源：{len(source_blocks)}")
print(f"小标题：{len(subheading_blocks)}")
print(f"可读内容块：{len(content_blocks)}")
print(f"排除段落：{len(excluded_blocks)}")

for block in source_blocks:
    print(f"来源字段：第 {block['index']} 段 -> {block['text']}")

for block in subheading_blocks:
    print(f"小标题字段：第 {block['index']} 段 -> {block['text']}")

for block in excluded_blocks:
    print(f"排除第 {block['index']} 段："
          f"{block['reason']} -> {block['text']}")

print(f"\n已保存到：{output_path}")
