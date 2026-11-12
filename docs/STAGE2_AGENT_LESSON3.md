# 第 3 课：Rubrics、AI 审核与可追溯清理

课程编号以 STAGE2_PLAN.md 为准。反馈修正实验见 STAGE2_AGENT_LESSON4.md，该文件为本课后半部分，不是新增课程。

本课接续候选 XPath 检查，使用同样两份已知开发页。第 2 课只保证收集完整原始 p，本课增加产品质量标准、当前对话 AI 的全文审核记录、可执行约束和清理结果。不是模型训练，也不是新数据盲测。

## 1. 先理解标准再运行

在 VS Code 用 Ctrl+P 打开 config/agent_review_rubric.json。

|编号|要求|为什么|
|---|---|---|
|R1|每个原始块恰好一个决定，不改写、不调序|可追溯并防止丢失证据|
|R2|整段专题链接且 URL 为新浪专题路径，排除|它引导去其他主题，不是文章叙述|
|R3|责任编辑移入 editor|编辑身份和作者身份不同，不能凭空造作者字段|
|R4|保留正常叙述中的内联链接段落|链接可能是股票或机构注释，不能见链接就删除|
|R5|保留本样例的投资风险声明|本次产品口径是可读文章，声明属于阅读内容|
|R6|保留叙述、分析、小标题；无法判断则 uncertain|避免没有依据就删除，不确定时阻止自动清理|

Rubrics 不仅是分类名称，还要写出判断条件与边界。R5 是产品选择，其他产品可以不同；标准改变后应重新审核，不能沿用旧结果。

## 2. 运行并看结果

~~~powershell
cd "D:\codex project\web_extract_demo"
.\.venv\Scripts\python.exe -X utf8 .\learning\agent_io\review_pipeline.py
Start-Process ".\output\agent_io\review\review.html"
~~~

预期：

~~~text
blog_01.html: raw=45 content=43 editor=1 excluded=1
collected_14a028de299edfab.html: raw=23 content=23 editor=0 excluded=0
REVIEW CHECK PASS; NOT PUBLISHED.
~~~

报告中分别展示排除、编辑元数据、可读正文。每项都有原始编号、全文、XPath、标准编号和审核理由。重点看第一篇第 1、2、44、45 段：导航排除、正常链接保留、风险声明保留、责任编辑进入元数据。无需逐段标注。

此前历史脚本把专题和编辑都放在 excluded_blocks，本课把编辑单列；正文仍为 43 段。它们是分类口径差异，不能只比较 excluded 数量判对错。本课独立输出，不重写历史结果、基准或生产规则。

## 3. 看机器结果，理解数据流

用 Ctrl+P 依次打开以下文件：

|文件|内容|
|---|---|
|output/agent_io/review_task.json|完整 68 段、属性、链接、快照信息、Rubrics；本轮审核的输入证据|
|output/agent_io/review_ai.json|当前对话 AI 阅读全文后的保存决定；每段 action/criterion/reason|
|output/agent_io/review/review_result.json|检查后派生的 raw_blocks/content_blocks/editor_blocks/excluded_blocks|

本轮 AI 已在对话工具输出中读过两页完整文字、链接与节点属性，再保存判断。review_pipeline.py 重放这些记录，不会在每次运行时重新调用 AI。要重新生成全文任务可运行同脚本 --prepare；若网页、候选或 Rubrics 改变，旧审核会因 review_task_id 不对应被拒绝。SHA/任务编号是内容对应检查，不是身份认证。

清理器不原地删除 raw_blocks，而是生成新列表。合并三个去向并按原始编号排序，应能覆盖所有原始块。责任编辑保留完整文字，尚未把姓名与编辑编号进一步拆分。

## 4. 亲手验证错误审核如何被拦截

反例故意把第一篇第 2 段判作导航，理由是“只要有链接就删除”。运行：

~~~powershell
.\.venv\Scripts\python.exe -X utf8 .\learning\agent_io\review_pipeline.py --audit .\output\agent_io\review_bad_link.json --output-dir .\output\agent_io\review_bad_link
Start-Process ".\output\agent_io\review_bad_link\review.html"
~~~

预期收到针对 blog_01.html #2 的 FAIL，指出需要 keep/R4，而收到 exclude/R2，最终 REVIEW REJECTED。退出码 1 是预期结果。拒绝结果中 pages 为空，不输出部分清理正文。正例报告保持原样。

这一步说明反馈应包含“哪页、哪块、违反哪条标准、收到什么动作”，而不仅是一个分数。后续 Agent 才能定位并修正。

## 5. 读懂代码中的判断边界

程序能自动验证：任务是否对应；全文/XPath/顺序是否被改写；每段是否有决定；动作和标准是否匹配；列明的专题、编辑、内联链接和声明约束是否满足；uncertain 是否阻止清理。

程序不能证明：所有文章内容都提取完整、语义理由一定合理、容器外没有漏文、规则跨站稳定。R6 的语义判断仍来自当前对话 AI 的保存审核；检查器不把关键词判断冒充新的 AI 审核。测试通过是程序行为证据，不是抽取准确率。

本课后半部分用结构化拒绝反馈修正一个审核决定，见 STAGE2_AGENT_LESSON4.md。完成后进入原第4课“复用和采用条件”，不新增课程。
