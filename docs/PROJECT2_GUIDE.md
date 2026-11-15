# 项目二使用与学习指南

## 先做离线演示

离线演示不需要 API key。它使用固定的 mock 模型或保存的候选，目的是先验证 Agent 的信息流和停止逻辑。运行入口以项目二 CLI 的 `--help` 为准：

```powershell
Set-Location 'D:\codex project\web_extract_demo'
$env:PYTHONPATH = '.deps;.'
& './.venv/Scripts/python.exe' -X utf8 './project2_agent.py' --help
```

一次运行应保存任务摘要、生成代码、每轮执行状态、反馈、holdout 结果和最终结果。报告中的 `provider=mock` 明确表示没有调用千问。项目二正式入口是 `project2_agent.py`；早期课程实验不作为验收入口。

## 接入千问

不要把 key 写入 Python、JSON、PowerShell 或 Git。使用当前终端的临时环境变量：

```powershell
$env:DASHSCOPE_API_KEY = '<在本机输入，不要粘贴到聊天或提交>'
$env:PROJECT2_MODEL = 'qwen-plus'
& './.venv/Scripts/python.exe' -E -X utf8 './project2_agent.py' --provider dashscope --task config/project2_task.json --output output/project2/live
```

真实运行必须在报告中记录模型名称、请求次数、重试次数、输入/输出 token（若接口返回），而不记录 key。没有网络或 key 时，入口应失败并说明配置缺失，不能静默退回 mock。当前 mock 已验证流程；没有配置密钥时不能声称完成真实千问调用。

## 每次运行检查什么

1. 输入角色：生成页、开发反馈页和最终测试页分别登记，检查哈希不能变化。
2. 首轮候选：能否导入、是否只有允许的依赖和 `extract` 入口。
3. 执行反馈：区分语法/运行错误、契约错误、XPath证据错误和质量不确定。
4. 修复结果：必须保留前一轮代码和反馈，最多 `max_rounds` 轮；修复失败也要报告。
5. 新页面：必须在候选冻结后才读取测试页，不能用测试反馈继续修改。
6. 结论：契约通过不等于正文语义准确率；图片、动态内容和未定义的杂质保持 unknown。

## 面试时如何解释

“我用两三篇同布局网页构造任务，让单 Agent 生成 Python/XPath 抽取器。候选先在受限执行器中运行，程序把异常、输出契约和原文定位反馈给 Agent，最多修复 N 轮；最终冻结候选后在独立页面验证。每轮保留代码哈希、网页哈希、提示版本、执行结果和 token/耗时。mock 只能证明流程，真实千问调用单独标注。”

这条叙述直接对应岗位的“少量样本生成代码、CPU批量复用、反馈修复”链路；不要把已有 LoRA 训练或当前对话人工修复说成已经完成单 Agent API。

## 已验证与待实测

当前验收：mock 两轮闭环、历史新浪 holdout 契约检查通过；真实千问调用尚未实测（未配置密钥）。历史页不是独立新测试。API成本只记录实际返回的 token；未配置价格不计算金额。
