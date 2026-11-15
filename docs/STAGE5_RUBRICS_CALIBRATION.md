# Rubrics 独立校准准备

现有Rubrics有规则和当前对话评审，但历史评审者知道受控案例，不能把一致率称为准确率，也不能直接把分数当GRPO reward。本包只准备盲评任务，不编造第二个评审者。

运行：

~~~powershell
cd "D:\codex project\web_extract_demo"
.\.venv\Scripts\python.exe -X utf8 .\learning\run_independent_rubric_calibration.py --prepare
Start-Process ".\output\stage5\rubrics_calibration_v1\index.html"
~~~

task只包含rubric、源证据和候选输出，不含旧expected标签。14个案例来自历史受控fixture，属于校准练习，不是新自然网页测试。两个彼此隔离的评审上下文分别填写reviewer_1.json与reviewer_2.json，返回Q1—Q5的yes/no/unknown、理由和逐字证据。主对话已知旧fixture，不能充当独立评审者。

两份文件完成后运行：

~~~powershell
.\.venv\Scripts\python.exe -X utf8 .\learning\run_independent_rubric_calibration.py --compare
~~~

脚本检查任务身份、案例顺序、五题、合法verdict、理由和证据结构，再统计每题一致/分歧/unknown。没有独立金标时accuracy=null、reward_frozen=false、grpo_ready=false。一致性不是准确率；unknown不映射为no。Q3承接漏表/列表/图说，Q4承接广告/导航/评论引导，图片无法核实时保留unknown。

## 2026-11-15 双评结果与边界

两份隔离上下文评审完成，引用校验通过：67/70一致（95.7%），来自相同模型家族，非人类独立金标。原始判断与三个分歧保留。第二份原先只引用记录ID，机械展开全文quote，原件reviewer_2_original.json保留，未更改verdict或reason。

未来规范澄清（不倒改本轮盲评）：Q1评标题，Q5评保留正文的事实/顺序，错标题不自动重复扣Q5；图片像素未获取时，最多判断静态文字完整，不能升级为文章整体完整，相关Q2/Q3保持unknown。自然页独立语义校准待完成，reward_frozen=false、grpo_ready=false。

额外尝试原始Qwen0.5B作为Judge，两种提示共28次生成，多数缺题或证据为空；cloud_raw_review原文保留，不将无效输出用于奖励。
