# 第二阶段第 2 课：AI 提出候选，独立程序验证

上一课准备任务；这课把当前对话 AI 的候选存为 JSON，再用原始 HTML 独立验证。重点是把自然语言目标转换为可执行、可拒绝、有证据的输出协议。当前没有 API 调用、模型训练、自动发布。

## 1. 先读候选，理解三个规则

在 VS Code 用 Ctrl+P 打开 output/agent_io/candidate.json。由本轮对话 AI 根据 task.json 提出并写入，不是生成器自行填答案。

|规则|表达式|原因与边界|
|---|---|---|
|标题|//h1|两份证据各一个 h1；不保证其他页面唯一|
|容器|//div[@id='artibody']|共享属性不依赖文章内容或多层位置；本轮容器已由任务给出|
|原始段落|./p|直接子 p，执行器过滤空白并读取完整文本；暂时保留导航和编辑信息|

explanations 说明依据；limitations 说明范围。程序只检查它们是否完整，不能证明解释合理。本课未自动判断选择器是否对所有模板稳定；位置索引在当前页也可能通过，泛化仍需审核和额外验证。

## 2. 运行独立检查

在项目根目录的 PowerShell 运行：

~~~powershell
cd "D:\codex project\web_extract_demo"
.\.venv\Scripts\python.exe -X utf8 .\learning\agent_io\check_candidate.py
Start-Process ".\output\agent_io\check.html"
~~~

预期：

~~~text
blog_01.html: actual=45 expected=45; PASS
collected_14a028de299edfab.html: actual=23 expected=23; PASS
CONTRACT PASS; semantic review pending; NOT PUBLISHED.
~~~

检查顺序：字段类型 -> 重算任务编号 -> 候选与任务 SHA256 -> 本地 HTML SHA256 -> XPath 可编译 -> 标题/容器唯一 -> 原始段落节点及顺序与独立遍历结果一致。

任务编号和哈希用于发现旧回答、快照不对应，不是签名认证，不能防止同时篡改输入与哈希。程序只执行 XPath，不执行 AI 给出的 Python 代码。

## 3. 读报告，只看两个重点

展开 blog_01.html 的完整段落，观察第 1 段专题链接和最后一段责任编辑仍在。这符合“收集原始 p”的任务。之前清理版为 43 段，本课原始版为 45 段；数字属于不同任务。

点击“打开保存的原网页”可以回到本地样例；每条段落保留完整文字和 XPath。没有要求逐条重做人工标注。机器结果为 check.json，阅读报告为 check.html。

semantic_review=pending 表示尚未判断全部段落的保留/排除；published=false 表示候选未写入正式配置。字段完整、表达式可运行、范围正确、语义质量好、允许发布是不同判断。

## 4. 运行反例，不用手改代码

candidate_early_cleanup.json 在相同任务上提前删除责任编辑，语法正确，但违反“保留原始段落供后续分类”。

~~~powershell
.\.venv\Scripts\python.exe -X utf8 .\learning\agent_io\check_candidate.py --candidate .\output\agent_io\candidate_early_cleanup.json --output-dir .\output\agent_io\early_cleanup
Start-Process ".\output\agent_io\early_cleanup\check.html"
~~~

预期第一篇 actual=44 expected=45，第二篇 23/23，最终 REJECTED。退出码 1 是实验预期结果。报告给出缺失 XPath，作为具体反馈。反例使用单独目录，正确候选报告保持原样，无需恢复规则或重建基准。

## 5. 本课应能解释的知识

- XPath 选节点；Python 过滤空白、读完整文本、记录证据。./p 不是整个抽取系统。
- 参照来自任务要求与独立遍历的直接子 p，只是范围契约，不是正文金标。
- 原始证据完整保存，后续分类才能追溯保留、排除、移入元数据的决定。
- PASS 只能证明所检查的条件；没有语义标准和未见数据就不能报告泛化准确率。
- 具体缺失 XPath 可以反馈给 Agent；下课给质量要求增加 Rubrics 和审核证据。

下一课复用原始 45/23 段，将专题导航、责任编辑、正常链接段落、风险声明的处理要求写为 Rubrics。沿用历史确认案例学习评审协议，不称作新盲测，也不重做人工标注。
