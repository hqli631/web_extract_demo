# 第 4 课：结构化反馈、有限修正与回归

本课完成“错误审核 -> 程序反馈 -> 当前对话 AI 提出修正计划 -> 执行计划 -> 重新审核 -> 已知样例回归”。使用已准备的错误审核，不需要手动破坏文件。本次修改的是一个审核决定，不是 XPath 规则，不是模型参数。

## 1. 一条命令运行完整实验

~~~powershell
cd "D:\codex project\web_extract_demo"
.\.venv\Scripts\python.exe -X utf8 .\learning\agent_io\repair_review.py
Start-Process ".\output\agent_io\repair\index.html"
~~~

预期：

~~~text
BEFORE: REJECTED; AFTER: PASS
CHANGED: 1; UNCHANGED: 67
KNOWN-CASE REGRESSION: PASS; AI calls=0; NOT PUBLISHED.
~~~

不用先重跑前几课。脚本会从当前 HTML、候选与 Rubrics 重建任务，重算错误审核的反馈，再核对修正计划。所有输出保存在本课 repair 目录，不覆盖第 3 课的原始审核。

## 2. 在报告看一次修正的三个环节

第一部分是反馈：blog_01.html 第 2 段被误判为导航，程序要求 keep/R4，却收到 exclude/R2。

第二部分是本轮 AI 的计划：保留该段。它叙述日期、股价和涨幅，公司名是内联链接；整段文字不等于链接文字，也不是专题入口。只改 action、criterion、reason，不改 index、xpath、text。

第三部分是复验：修正后 68 个决定完整，其他 67 个决定不变；第一篇正文43、编辑1、导航排除1，第二篇正文23。程序再次按 Rubrics 审核，并与第 3 课已确认记录的原文和去向比较。理由允许换措辞，不能凭此改变结果。

## 3. 打开三份 JSON，理解输入输出

在 VS Code 按 Ctrl+P 打开以下文件：

|文件|职责|重点字段|
|---|---|---|
|output/agent_io/repair/feedback.json|检查器给出的反馈|issue_records：code/file/index/xpath/text/actual/expected|
|output/agent_io/repair_plan.json|当前对话 AI 保存的修正计划|before、after、input_audit_sha256、feedback_sha256|
|output/agent_io/repair/repair_result.json|执行与复验报告|changed_count、unchanged_count、regression_matches_known_reference|

在 feedback.json 中找到 rubric_conflict。它把之前终端的一句话变为机器可读字段，不需要用正则从中文报错里猜编号。

计划中的 before 是完整旧决定，after 只允许 action/criterion/reason。执行前核对任务、审核哈希、反馈哈希和旧决定内容。旧输入一旦改变，旧计划就不能直接套用。这些检查防止误用，不是身份认证。

程序不会自动调用 AI 生成计划：计划来自本轮对话 AI，脚本只严格重放和检查。重复运行是重现实验，不是 AI 再学习了一次。

## 4. 区分重新审核与回归

- 重新审核：把修正后记录交回 Rubrics 检查器，看列明条件是否通过。
- 回归比较：与此前已确认记录比较，检查正文、编辑和排除去向有没有意外变化。
- 未见评估：在未参与规则与标准调试的新页面上验证泛化。本课没有开展。

通过回归不代表发现了新知识，也不代表覆盖所有漏文。沿用历史答案做对照只能证明本次修正恢复了已知期望。

## 5. 为什么只允许改一个决定

反馈指向第 2 段，因此计划只修该段。若顺手改其他段落，必须提供新的证据与审核。执行器拒绝无反馈支撑的修改、重复修改、改写原文、过期计划以及与要求相反的动作。修正后若仍未通过，不生成有效修正结果。

这是一个有边界的修正执行器，还不是能自行浏览网页、规划多轮和调用模型的完整 Agent。不要把本实验称为强化学习：没有训练数据优化步骤、梯度或参数更新。

本课应能说清：错误是哪一层（审核决定）、反馈用什么定位（页/块/XPath/原文）、修改范围是什么（一个决定的三个字段）、为什么再验证（修正也可能引入错误）。

下一课进入评估数据分工：区分开发页、回归页、未见页；先定质量标准再冻结新批次，避免边看答案边声称盲测。网页模板变化造成的定位失败与语义审核错误需要分开统计。
