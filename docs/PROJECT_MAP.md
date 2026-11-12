# 项目文件导航

## 当前学习入口

- `docs/STAGE2_AGENT_LESSON3.md`：Rubrics、当前对话 AI 的全文审核与清理反例。
- `learning/agent_io/review_pipeline.py`：复建全文任务，检查审核记录，生成独立的可追溯结果。
- `config/agent_review_rubric.json`：本课产品质量标准，变动会使旧审核失效。
- `docs/STAGE2_AGENT_LESSON2.md`：当前对话 AI 提出 XPath 候选，独立检查与拒绝反例。
- `learning/agent_io/check_candidate.py`：检查候选与任务、快照、原始段落的对应关系。
- `output/agent_io/candidate.json`：本轮 AI 规则建议，尚未发布；检查报告为同目录 check.html / check.json。
- `docs/STAGE2_AGENT_LESSON1.md`：第二阶段 Agent 任务输入与输出协议。
- `learning/agent_io/prepare_task.py`：准备两页开发样例任务包，不调用模型。

- `docs/PROJECT1_KNOWLEDGE_REVIEW.md`：第一阶段具体知识点、代码解释、操作练习和个人验收。

- `learning/xpath/`：用户运行的 XPath 练习与检查脚本。
- `docs/xpath_basics_notes.md`：XPath 知识说明。
- `docs/xpath_practice_notes.md`：实验过程与结果记录。
- `config/xpath_sina.json`：新浪模板定位规则。
- `output/xpath_sina/`：当前新浪结构化结果。
- `output/xpath_practice/baseline.json`：中新网冻结基准，不能当缓存删除。

## 工程模块

根目录的 `extract.py`、`content_scope.py`、`dom_evidence.py`、`xpath_*.py` 等是自动化流程导入的功能模块。
`collect_pages.py` 负责采集，`compare_extractors.py` 负责抽取器比较，`ai_review.py` 负责审核任务与候选结果，OCR 文件负责图片辅助分支。
`serve_review.py`、`visual_review.html`、`region_overlay.js` 为原网页复核入口。
`tests/`、`test_project.ps1` 为工程检查。

## 数据与环境

- `samples/`：保存的原网页与配套资源。网页来源见采集清单。
- `reports/`：审核记录、标注、采集清单及历史回归证据；部分旧报告仍被程序读取。
- `news_validation/`、`validation_*`：不同阶段采集与验证数据，不合并，以免混淆样本用途。
- `.venv/`、`.deps/`：当前 Python 环境和依赖，保留以保证可运行，Git 忽略。
- `__pycache__/`、`*.pyc`、`.vs/`：可重新生成的缓存，本轮清理。

## 常用命令（在项目根目录运行）

```powershell
.\.venv\Scripts\python.exe -X utf8 .\learning\xpath\xpath_practice_sina.py collected_af5904c15d1deebc.html
.\.venv\Scripts\python.exe -X utf8 .\learning\xpath\check_xpath_sina_batch.py
.\.venv\Scripts\python.exe -X utf8 .\learning\run_project1.py
```

统一验收报告位于 `output/project1/index.html`，结构化汇总位于同目录 `results.json`。
