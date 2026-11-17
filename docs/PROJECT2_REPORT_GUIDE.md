# 项目二报告阅读与重建

报告采用项目一的“汇总 → 页面信息 → 正文 → 原文证据”阅读顺序，并增加项目二独有的生成与修复、规则与代码、调用记录。它只读取保存的证据，不发起API请求、不重新提取、不修改实验数据。

## 四个视图

- 提取结果：顶部样本表、侧栏搜索和角色筛选、正文阅读。元数据独立成表；正文按原文顺序标号，XPath默认收起。代码保留缩进，表格按单元格展示。多轮页面可选择首轮或修复后的全文。
- 生成与修复：每轮执行结果、具体问题、模型输入/响应链接、规则差异及冻结状态。首轮直接通过不会虚构修复。参考回归改为显示参考/当前块数和顺序对照。
- 规则与代码：每个XPath字段分项展示，保留候选JSON/Python入口。参考报告明确展示人工配方，不冒充模型生成。
- 调用记录：模型、提供方、API尝试、每次输入/输出/总tokens和耗时，以及完整原始记录。失败请求没有用量时显示未返回。

本轮更新入口：

- output/project2/live_flash_foundation_v2/index.html：当前真实生成实验。
- output/project2/live_repair_v4/index.html：受控漏提修复实验。
- output/project2/foundation_v2_final/index.html：项目一基础迁移对照。

页面中的正文块数不是准确率。最新一轮失败时不会把历史候选当成最新成功；未执行页面仍列出并解释原因。排除和语义待审核问题保留。参考回归不计算模型调用成绩。

## 重新生成展示（无需API）

~~~powershell
Set-Location 'D:/codex project/web_extract_demo'
./.venv/Scripts/python.exe -X utf8 project2_report.py output/project2/live_flash_foundation_v2 output/project2/live_repair_v4 output/project2/foundation_v2_final
~~~

只更新指定目录的index.html，trace、rules、候选代码、原始HTML和各篇JSON保持不变。以后project2_agent.py和project2_foundation_check.py会自动使用新展示器。所有CSS和交互脚本内嵌，无外部前端依赖；JavaScript禁用时仍保留正文内容。

浏览器检查工具本轮拒绝file协议，未完成截图和真实浏览器交互验收；已检查HTML结构、链接、脚本语法和原始证据不变。请在本地浏览器打开报告查看实际效果。
