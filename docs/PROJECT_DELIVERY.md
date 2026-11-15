# 项目基本交付与学习回顾

日期：2026-11-15。岗位主线：布局聚簇 → 少样本 Coding Agent → Python/XPath → CPU复用 → 质量反馈、修复与回滚。

## 已完成与结果

- 新增12个真实网页、3个布局任务。每簇2训练、1开发、1封存测试。加上历史新浪，共4条训练任务；历史中新网单列开发任务。网页总数不能冒充独立任务数。
- 真实分词最长7768 tokens，8192窗口，无截断。prompt标签为-100，只监督assistant代码。
- 原3090完成40步、一次容量对照120步LoRA。120步训练8,798,208个参数，峰值allocated约14.57GiB，纯训练67秒。保存、参数变化和新进程重载证据齐全；时间不含生成、采集、审核与评估，不换算未经核实的金额。
- 新布局开发页：基座0/3，40步0/3，120步3/3通过。封存同布局新文章：基座0/3，120步2/3，参考2/3。通过指执行、五字段类型、非空标题正文、XPath原文与顺序，不是语义准确率。
- Linux bubblewrap+prlimit隔离运行模型代码，无网络、非root、只读输入、宿主home不可见，限制时间/CPU/内存/输出。五个拒绝控制通过，不构成内核漏洞防护证明。
- 14个历史受控Rubrics案例双评，67/70一致（95.7%）。两个隔离上下文来自同一模型；一致率不等于准确率。3项分歧保存，reward未冻结，真实GRPO未开始。
- RSI回放一次折叠正文补漏被接受、一次破坏性输出被拒绝并保持版本。是审核历史补丁与门禁回放，不冒称云模型自主修复。

## 模型学到了什么，以及失败

120步版在三个新布局任务生成代码的AST与对应监督参考一致；通过页面的输出也一致。这是小任务集上学会目标代码并在同布局新文章复用的证据，存在强记忆成分，不能证明未见布局泛化。

SQLite封存页没有命中div.fancy，模型与参考同时失败。这暴露同站异构/布局簇边界问题。失败保留，不在本轮用测试修补。后续修补必须把这页转为开发，并另封存新测试。

参考仍有代码/列表压为paragraph、规范化空白、博客日期注释可能混入等局限。图片像素与JS动态正文未获取，完整性相关项保持unknown。

## 你如何看到与亲手验证

在项目目录运行：

~~~powershell
Start-Process ".\output\stage5\multitask\showcase\index.html"
~~~

1. 看训练网页表，打开一个原网页，区分两张样本网页与一个代码任务。原始HTML保留，但外部资源未全部缓存，视觉不保证与原站一致。
2. 切换原始基座与120步LoRA，对比XML解析错误与成功正文。展开代码，找到html.document_fromstring、正文XPath和getroottree().getpath。
3. 切换SQLite封存测试，解释为什么模型和参考都失败：学会目标代码不等于目标规则覆盖所有同站文章。

浏览器自动化禁止file协议，本轮完成静态内容、链接、JSON和脚本逻辑检查，没有声称浏览器视觉验收通过。

在CPU运行已复核模型代码，无需GPU：

~~~powershell
$env:PYTHONPATH = ".deps;."
.\.venv\Scripts\python.exe -X utf8 .\learning\replay_approved_model.py --cluster python_sphinx_v1 --input .\data\natural_v1\python_sphinx_v1\dev_3.html --output .\output\my_model_result.json
~~~

已存在输出会拒绝覆盖，请用新文件名。新生成代码不能直接exec；这里只允许已与可信参考AST比较且固定哈希审核的三份候选。打开JSON观察title、blocks、metadata、excluded、warnings与每块kind/text/xpath。

这对应岗位降本逻辑：少量GPU生成代码，多篇网页CPU复用。CPU仍有成本；本实验没有GPU逐页推理的等价对照，不能编造降本倍数。

## 文件与复验

|路径|用途|
|---|---|
|config/natural_expansion_v1.json|采集前URL与角色登记|
|data/natural_v1/|12份原始HTML|
|config/next_layout_tasks.json|3个布局的路径、哈希、目标版本|
|learning/expand_natural_data.py|robots与白名单有界采集|
|learning/prepare_natural_tasks.py|train/dev目标与训练输入构建|
|output/stage5/multitask/train.jsonl、dev.jsonl|4条train、1条历史dev|
|training/multitask_sft.json、multitask_capacity.json|两次有限实验配置|
|training/minimal_sft.py|分词、训练、生成，禁止exec候选|
|training/isolate_extract.py、check_isolation.py|Linux隔离执行和控制|
|learning/evaluate_multitask.py|固定计划、一次性测试、契约原文检查|
|output/stage5/multitask/evaluation_results.json|完整执行结果及失败|
|output/stage5/multitask/test_exposure.json|测试曝光收据，不可再冒称未见|
|learning/replay_approved_model.py|已审核模型候选CPU回放|
|output/stage5/rubrics_calibration_v1/|双评、分歧、低能力Judge失败证据|
|learning/run_rsi_delivery.py|接受、拒绝与回滚演示|

~~~powershell
$env:PYTHONPATH = ".deps;."
.\.venv\Scripts\python.exe -X utf8 -m unittest discover -s tests
.\.venv\Scripts\python.exe -X utf8 .\learning\run_independent_rubric_calibration.py --compare
.\.venv\Scripts\python.exe -X utf8 .\learning\run_rsi_delivery.py
.\.venv\Scripts\python.exe -X utf8 .\learning\build_final_showcase.py
~~~

不要把测试页重跑当新实验，不要把目标答案放进测试提示。云适配器已下载核验，位置为.training-prep-cache/final_receipt/output/stage5/multitask/cloud_capacity120/adapter。二进制未提交Git，收据为archive_receipt.json。原服务器保留，GPU进程已结束。

## 学习与面试对应

第一阶段：DOM层级、XPath轴与谓词、lxml解析、正文/作者/图说/广告、原文证据和回归。

第二/三阶段：任务契约、Reference/Actor/Critic信息流、少样本、代码复用、同簇异构、有限反馈修复与CPU成本。本项目的当前对话Agent承担生成复核，不能称独立部署的多Agent服务。

第四阶段：Q1标题、Q2主要叙述、Q3结构化信息、Q4纯净度、Q5保留内容忠实性；unknown、分数/采用/reward区别；一致率与准确率区别。

第五阶段：SFT监督、mask、LoRA、optimizer、参数变化、checkpoint；基座控制、过拟合、未见页；GRPO优势/clip/KL为数学学习，无真实RL更新；RSI为有限工程回放。

本轮到此停止扩充和训练，形成可演示的工程Demo。后续研究：更多独立布局任务、自然页独立语义金标、图像与动态内容、可靠reward后真实GRPO、新badcase自动提议及隔离回归。避免继续扩张导致永不交付。

简历事实可写：搭建布局任务与XPath抽取评估链路，新增3类12页数据；在3090完成Qwen0.5B LoRA有限对照，封存同布局新文章2/3通过契约及证据检查；实现隔离执行、修复回滚并分析评审分歧。不要写准确率95.7%、普适网页模型或完成GRPO。
