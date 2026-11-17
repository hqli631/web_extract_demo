# Web Extract Demo

报告展示已更新：先看[真实生成与正文结果](output/project2/live_flash_foundation_v2/index.html)，或[修复前后对照](output/project2/live_repair_v4/index.html)。支持文章搜索、角色筛选、候选全文切换，以及独立的规则/调用记录视图；[阅读与重建说明](docs/PROJECT2_REPORT_GUIDE.md)。

2026-11-17：[参考项目一改进固定执行层](docs/PROJECT2_FOUNDATION_UPGRADE.md)，新增原始DOM证据验证、细分元数据、代码/列表/定义项与旧博客分段，并支持任务自有摘要/评测范围。查看[三个已曝光样例的对照报告](output/project2/foundation_v2_final/index.html)。这是底层回归，不是新增模型泛化成绩；本轮全仓236项测试通过。

面向离线搜索正文提取岗位的学习项目：网页布局聚簇 → 少样本生成Python/XPath代码 → CPU批量复用 → 质量评估与有限修复。

当前已达到**可运行、可复验、可展示的工程Demo**。已使用真实云GPU完成LoRA训练；尚未完成生产级泛化、自然网页独立语义校准或真实GRPO。

项目二已完成真实千问API生成、实际反馈修复与CPU批量复用。先看 [真实生成与逐页正文](output/project2/live_flash_final/index.html)、[受控漏提后的真实修复](output/project2/live_repair_v4/index.html)、[完成记录](docs/PROJECT2_COMPLETION.md) 和 [使用指南](docs/PROJECT2_GUIDE.md)。

~~~powershell
Set-Location 'D:/codex project/web_extract_demo'
./.venv/Scripts/python.exe -X utf8 project2_agent.py --provider mock --max-repairs 2 --output output/project2/my_mock_01
~~~

mock不调用千问。正式实验使用qwen3.8-flash：2篇生成/1篇开发/2篇最终测试，正文块分别21/19/19/21/33，每页另存作者和日期。真实接口读取QWEN_API_KEY或DASHSCOPE_API_KEY。模型生成受限XPath JSON，可信Python模板导出模块，固定子进程运行。结构检查通过不是语义准确率。已有输出不能覆盖，请换新名称。

## 先看效果

~~~powershell
cd "D:codex projectweb_extract_demo"
Start-Process ".outputstage5multitaskshowcaseindex.html"
~~~

展示包含训练网页URL、开发/封存测试角色、基座/40步/120步/参考对照、全文输出、XPath和失败原因。

|方法|新布局开发页通过|封存同布局新文章通过|
|---|---:|---:|
|原始Qwen2.5-Coder-0.5B-Instruct|0/3|0/3|
|40步LoRA|0/3|未用于最终测试|
|120步LoRA|3/3|2/3|
|当前对话复核参考|3/3|2/3|

通过指标：执行、输出契约、非空正文、XPath原文与顺序。不是语义准确率。120步模型在三个自然任务生成代码AST与监督目标相同，存在强记忆成分；测试是已训练布局的新文章。SQLite异构页模型和参考同时失败，已保留。

## 数据、训练与边界

新增12个真实网页（Python文档、SQLite文档、传统博客），每簇2训练/1开发/1封存测试，构成3个任务；加入历史新浪为4个训练任务，历史中新网为开发任务。没有把页面数量当任务数，没有把历史页称为新测试。

RTX3090上完成真实optimizer更新、适配器保存与新进程重载。120步版本LoRA r16、8,798,208可训练参数、峰值allocated约14.57GiB。模型固定revision，最长7768 tokens，无静默截断，prompt不参与loss。

候选在Linux bubblewrap/prlimit中执行；本地回放只允许经过AST复核的固定哈希候选。Rubrics双评14个历史案例，67/70一致（95.7%），分歧保留；一致率不是准确率，reward未冻结。RSI已完成接受/拒绝回滚的有限回放，真实GRPO未运行。

## 快速复验

~~~powershell
$env:PYTHONPATH = ".deps;."
..venvScriptspython.exe -X utf8 -m unittest discover -s tests
..venvScriptspython.exe -X utf8 .learningun_rsi_delivery.py
..venvScriptspython.exe -X utf8 .learningun_independent_rubric_calibration.py --compare
..venvScriptspython.exe -X utf8 .learninguild_final_showcase.py
~~~

在CPU亲手运行已审核的模型抽取代码：

~~~powershell
..venvScriptspython.exe -X utf8 .learningeplay_approved_model.py --cluster python_sphinx_v1 --input .data
atural_v1python_sphinx_v1dev_3.html --output .outputmy_model_result.json
~~~

已有输出会拒绝覆盖，请换新输出路径。不要在本机直接exec任意新生成代码。新环境安装基础依赖见requirements.txt；.deps为项目已有依赖目录，.venv为本机Python环境。

## 目录与阅读顺序

|目录/文件|用途|
|---|---|
|docs/PROJECT_DELIVERY.md|本轮交付、具体知识与操作、面试事实及剩余研究项|
|docs/STAGE1_SUMMARY.md、STAGE2_SUMMARY.md、STAGE3_SUMMARY.md|基础解析、Agent任务与聚簇代码复用回顾|
|docs/STAGE4_SUMMARY.md、STAGE5_SUMMARY.md|Rubrics、训练与RSI总结|
|docs/NEXT_PHASE_PLAN.md|工作包A—F，末尾更新实际验收与停止点|
|docs/PROGRESS_HISTORY_THROUGH_20261115.md|旧README及按日期记录的历史状态，非当前结论|
|config/|采集白名单、正文规范、布局任务登记|
|samples/、data/natural_v1/|历史样本与本轮12份原始网页|
|learning/|课程实验、任务准备、评估与报告脚本|
|learning/generated/|经过复核的参考抽取器|
|training/|LoRA训练、隔离执行、云端评审脚本|
|output/stage5/multitask/|训练材料、生成代码、证据、封存评估与展示|
|output/stage5/rubrics_calibration_v1/|双评原文、证据、分歧|
|output/stage5/rsi_delivery/|修复、拒绝、回滚报告|
|tests/|工程协议与回归测试|

原有抽取/区域复核入口run.ps1、start_review.ps1和visual_review.html继续保留，说明见docs/REVIEW_GUIDE.md。原始网页的CSS、图片与动态资源未必完整缓存，不能把重建页外观当作原站视觉金标。

适配器已下载至本地.training-prep-cache，SHA256核验收据见output/stage5/multitask/archive_receipt.json；二进制不进入Git。服务器按用户要求保留，当前模型进程结束。
