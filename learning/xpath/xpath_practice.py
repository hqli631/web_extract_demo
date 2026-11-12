import sys
import json
from pathlib import Path
from lxml import html


# __file__ 是当前脚本的位置，parent 是脚本所在目录。
project_dir = Path(__file__).resolve().parents[2]
rules_path = project_dir / "xpath_rules.json"

with rules_path.open("r", encoding="utf-8") as file:
    rules = json.load(file)

print(f"使用规则：{rules['name']}，版本：{rules['version']}")
# 命令行指定文件名；没有指定时，仍使用第一个样本。
sample_name = (
    sys.argv[1]
    if len(sys.argv) > 1
    else "xpath_practice.html"
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

# 3. 提取每个容器中直接属于它的 p 段落。
paragraphs = []

for container in containers:
    for paragraph in container.xpath(rules["block_xpath"]):
        text = " ".join(paragraph.text_content().split())

        # 忽略没有文字的空段落。
        if text:
            paragraphs.append(text)

print(f"提取到非空文本块：{len(paragraphs)} 块")
print("=" * 40)

for index, paragraph in enumerate(paragraphs, start=1):
    print(f"\n【第 {index} 个文本块】")
    print(paragraph)
