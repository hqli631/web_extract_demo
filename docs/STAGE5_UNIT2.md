# 5.2第一步：先检查训练条件，再选择实操路线

2026-11-14后续更新：用户E/F反馈已收到，本机资源检查后转为本地准备＋外部兼容GPU的最小LoRA SFT。材料、知识讲解、运行命令和租赁停止点见[训练准备交接](STAGE5_SFT_PREPARATION.md)。真实tokenizer预检完成；历史2任务不是正式训练语料/未见测试，真实训练仍未完成。下文保留第一步资源检查时状态。

来源：固定5.2要求先确认GPU、模型、框架、任务、reward与预算。5.1的轨迹、优势、裁剪、KL及质量/轮数/开销教学已完成，用户A/B/C/D理解点已确认。数学计算不是训练准备完成的证据。

## 1．运行检查，查看自己的环境

~~~powershell
cd "D:/codex project/web_extract_demo"
./.venv/Scripts/python.exe -X utf8 ./learning/check_training_readiness.py
Start-Process "./output/stage5/unit2/index.html"
~~~

当前机器在本次检查中的结果：Python 3.12.14；虚拟环境没有torch、transformers、peft、trl、accelerate、ms-swift、bitsandbytes。系统物理内存约27.7 GiB，D盘可用约490 GiB，动态可用内存/磁盘会变化。

当前对话先前执行的一次授权只读系统查询列出了AMD Radeon 780M Graphics。集成显卡的AdapterRAM字段不能当作专用可用训练显存，本机尚未验证可用LLM训练后端。nvidia-smi不在PATH也不证明没有显卡；默认环境WMI拒绝访问记为探测error，不把error冒充无设备。你在普通VS Code终端重跑可能成功，报告以当次结果为准，先前记录另存observed_display.json。

预期终端至少能看到：

~~~text
PYTHON: 3.12.14
TORCH: not_installed_in_this_interpreter
TRAINING: environment=not_ready; backend/model/data/reward/budget need verification
SIDE EFFECTS: installs=0; model downloads=0; training updates=0
~~~

这里的not_ready是当前项目环境未准备，不是断言这台机器永远不能做任何训练。安装包也不能自动解决全部条件。AMD平台的可用后端/模型/框架需实际核验，不能给它套用未经验证的CUDA命令。暂不下载模型、安装大型依赖或启用付费算力。

## 2．按六项清单判断，而非只看显卡名字

|条件|需要确认什么|当前状态|
|---|---|---|
|硬件与后端|可用计算设备、显存/共享内存口径、驱动、框架实际可访问设备|设备已观察；LLM训练后端未验证|
|模型与框架|模型规模/许可、tokenizer、框架与OS/Python版本、LoRA支持|未选模型；当前环境训练包缺失|
|数据|任务与目标示例、质量检查、train/dev/test分工、近重复控制|已有历史证据；真实训练需新协议|
|reward|同任务采样、有效评审与奖励、unknown处理、独立校准|第四阶段独立校准未完成|
|预算|生成/采样/训练/审核总开销、步数和停止条件|未定，无付费训练|
|验证|训练前后对照、损失与权重更新记录、固定测试质量/步数/成本|尚无真实训练、checkpoint更新|

模型权重大小不是训练总内存：还需激活、梯度、优化器、序列长度、batch以及rollout推理支出。硬盘足够不能说明显存足够。小机数学实验能运行也不能说明Qwen训练可行。

## 3．用同一个岗位任务区分训练方式

任务仍是“看到少量同布局网页→生成抽取代码”，不更换成无关玩具任务。

**提示与代码迭代：** 给模型网页和错误反馈，它输出新代码。此时上下文与产物变化，模型权重未变，属于已有工程流程。

**SFT：** 准备任务输入与经过验证的目标代码/工具轨迹，例如“HTML结构与输出契约→参考extract函数”。训练通常让模型更可能输出目标token，使用目标序列的监督损失；目标代码错误也会被学进去，所以“保存了v2”不代表它自动成为高质量训练标签。需要核验代码、样本覆盖与数据分工。

**LoRA：** 通常冻结基础模型权重，在选定层训练低秩适配参数，减少可训练参数量。它是参数高效训练方式，不是与SFT/GRPO互斥的任务；可以与合适的SFT/RL流程组合。LoRA不会自动修好坏标签、补齐缺失正文或校准reward。

**GRPO等RL：** 在同任务下用当前采样policy生成多条轨迹，经过执行与评审得到奖励，形成相对优势，结合概率、裁剪/KL等目标更新Actor的可训练参数。模型不需要每个输出位置都有唯一目标代码，但需要可信任务反馈与正确训练实现。旧历史修复记录不能直接当作当前policy的新rollout。

无论SFT还是RL，都要有实际backward、optimizer step及参数/checkpoint变化，才发生训练。本轮没有这些步骤。

## 4．接下来怎么推进

当前先完成有限训练准备学习：你解释本报告条件及SFT/RL信号区别；下一步整理一条来源清楚的代码生成SFT教学样例，检查输入/目标/loss覆盖与数据分工，不直接把历史全库塞给训练器。

真实训练继续标为未完成。若之后具备兼容本地或外部GPU，可再明确设备、模型、预算与reward条件后实施；资源不足则按原计划保留缺口，进入5.3 RSI有限工程原型。不要求为了让阶段“完成”先购买算力，也不把无关CPU玩具更新冒称岗位Coding Agent的训练成果。

## 5．本轮反馈

- E：检测到显卡、磁盘空间充足，为什么仍不能直接宣布可以训练Qwen？
- F：SFT用目标输出示例，GRPO用采样轨迹与奖励，两者的训练信号有什么区别？

不用背术语，用自己的话说明即可。文件：learning/check_training_readiness.py是检查入口；resource_report.json是本次快照（重跑更新）；observed_display.json是先前成功的系统查询证据；index.html为报告。没有读取账号凭据、扫描用户模型目录或进行网络操作。
