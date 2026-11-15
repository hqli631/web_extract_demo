# 新自然网页扩充记录

2026-11-15，先在 `config/natural_expansion_v1.json` 固定 URL 与角色，再由有域名和响应大小边界的采集器下载 12 个自然静态网页；三个站点 robots 均允许目标路径。未使用合成 HTML 冒充真实网页。

|布局任务|训练页|开发页|封存测试页|主要结构|
|---|---:|---:|---:|---|
|python_sphinx_v1|2|1|1|Sphinx 的 `div.body[role=main]`，章节、代码和列表|
|sqlite_document_v1|2|1|1|`div.fancy`，导航目录、章节、列表和表格|
|pg_essay_v1|2|1|1|旧式 `td[width=435]/font`，`br` 分段及文本尾节点|

12 页形成 **3 个新代码生成训练任务**，不是 12 条任务。每个任务提示只包括两篇训练页的结构前缀：最多 70 节点，文本和 tail 最多 32 字符；结构压缩和遗漏节点数逐项记录。开发页只作参考代码回归，未进入训练提示。测试页只下载、哈希和登记，未解析正文、未据其修改参考代码。最终执行测试后，应将状态改为 exposed，并保留一次性评估记录。

`natural_manifest.json` 保存 URL、原始字节哈希、抓取时间和角色；`natural_tasks.json` 保存参考代码哈希；`natural_train.jsonl` 为新训练数据；`natural_reference_checks.json` 为 9 个训练/开发页的契约、XPath 原文证据检查。

这批页面补充不同 DOM 结构、代码和长文，不代表新闻/论坛全域覆盖。没有将同布局的新文章称为整个未见布局；新增目标是当前对话中人工编写和复核的教学参考，不能称独立金标或模型自主生成结果。Sphinx/SQLite 将代码和列表归入 paragraph，空白标准化，不提供代码格式保真承诺。Paul Graham 的老式 `br` 分段使用容器级 XPath，日期和注释暂留正文，图像像素未提取；相应完整性只能 unknown。

重跑准备：

```powershell
$env:PYTHONPATH='.;.deps'
& './.venv/Scripts/python.exe' -X utf8 -m learning.prepare_natural_tasks
& './.venv/Scripts/python.exe' -X utf8 learning/prepare_next_layout_tasks.py
& './.venv/Scripts/python.exe' -X utf8 -m unittest tests.test_natural_tasks
```

采集命令为 `learning/expand_natural_data.py`；已有快照保持原始字节，不覆盖下载。保存的是原 HTML，不重构原页面，所以本地浏览缺少资源时不保证视觉还原。可直接打开清单中的原始 URL 对照。
