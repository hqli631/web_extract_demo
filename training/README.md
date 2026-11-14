# 最小 LoRA SFT 云端方案（准备包，尚未在 GPU 实测）

这是岗位学习阶段 5.2 的一次有限训练：输入同簇少量网页结构，监督 Actor 生成 Python/XPath 抽取代码。优化器更新 LoRA 参数。不是直接训练 XPath，也不是 GRPO。历史样本很少，训练损失或代码生成发生变化都不等于质量、泛化提升。

当前只有四种模式。本轮已运行 dry-check、CPU 单元测试和真实 tokenizer 预检；tokenize仅下载分词/配置文件，未下载模型权重。train、generate 待确定兼容GPU后执行。

| 文件 | 用途 |
| --- | --- |
| minimal_sft.json | 单卡 0.5B、LoRA r=8、单条 micro-batch、1 个 optimizer step 的 smoke 配置 |
| requirements-cloud.txt | 拟用版本，尚未 GPU 联调；torch 单独按云镜像 CUDA 安装 |
| minimal_sft.py | 读取 messages JSONL，查长度，屏蔽提示词 loss，训练、存适配器和对照生成 |

## 本地检查

在项目根目录执行：

~~~powershell
..venvScriptspython.exe -X utf8 training/minimal_sft.py dry-check
~~~

应显示 train/dev 数量、数据 SHA256、gpu_training_tested=false、no_download_performed=true。model_revision 已由模型API查询并固定为 ea3f2471cf1b1f0db85067f1ef93848e38e88c25（2026-11-14）。不能悄悄改成会变化的 main。

## 后续云端顺序（现在不租、不运行）

推荐 Linux x86_64、Python 3.10/3.11、单块 NVIDIA CUDA GPU。24GB 是候选起点，实际显存以 smoke 测量为准，不保证所有型号/镜像都兼容。5090 的框架需求另行核实。

1. 上传代码及 sft_prep 数据包。当前训练只读 JSONL，不用上传全部原始网页；保留 provenance manifest 以追踪出处。
2. 执行 nvidia-smi，记录 GPU/可用显存、驱动、CUDA。只让一个 GPU 对进程可见。镜像已有 torch 不必无条件覆盖。
3. 依据镜像选官方 PyTorch 安装方式。以下仅是拟用未联调的 CUDA 12.4 示例，不适用于所有型号：

~~~bash
python3 -m venv .train-venv
source .train-venv/bin/activate
python -m pip install --upgrade pip
python -m pip install torch==2.5.1 --index-url https://download.pytorch.org/whl/cu124
python -m pip install -r training/requirements-cloud.txt
python -m pip freeze > cloud_environment.txt
~~~

镜像不匹配时先确认驱动、GPU 架构、torch wheel 兼容性，不靠反复换版本碰运气。脚本不安装驱动。

4. 核对配置中已冻结的模型 Qwen/Qwen2.5-Coder-0.5B-Instruct commit SHA，并保留来源/时间。可在模型仓库 Files and versions 查看，或允许联网后用 huggingface_hub.HfApi().model_info(...).sha 查询。不要填本项目 Git 提交。
5. 固定 revision 后先做 tokenizer-only 预检；只下载 tokenizer/config，不下载权重：

~~~bash
python training/minimal_sft.py dry-check
python training/minimal_sft.py tokenize
~~~

token_lengths.json 逐条列出提示词、监督 token 和总长度。超过 8192 立即失败，绝不截断目标代码。超限时回本地调整结构摘要或范围并重查数据，不要删除代码尾部。8192 是本实验训练窗口，不是模型最大上下文声明。

预检同时保存 preflight_manifest.json 的配置/数据 SHA256。训练和生成必须与这份预检一致，改变数据或参数请用新的 output_dir 重新预检。脚本拒绝覆盖已有 before/after 生成或训练证明。中断后本最小方案采用新目录从头重跑；没有声称支持优化器断点恢复。

6. 保存基座确定性生成，做一次更新，再加载适配器生成。使用相同 revision、输入、seed、输出上限：

~~~bash
CUDA_VISIBLE_DEVICES=0 python training/minimal_sft.py generate
CUDA_VISIBLE_DEVICES=0 python training/minimal_sft.py train
CUDA_VISIBLE_DEVICES=0 python training/minimal_sft.py generate --adapter output/stage5/unit2/cloud_sft/adapter
~~~

每次只运行一个模型进程。生成结果只存文字，不自动执行 Python。历史任务 before/after 只能观察 smoke 与机制；独立网页和布局的验证必须另外冻结。

7. update_proof.json 必须有 optimizer_steps=1、有限非零的 LoRA 参数变化、适配器序列化校验通过。最后 generate --adapter 成功后才记 adapter_reload_verified=true。这证明参数更新及保存可加载，不证明抽取质量提高。
8. smoke 通过之后再复制配置，改为新 output_dir、如 max_steps=10，做有限的小实验。不要覆盖证据。重复同一历史样本主要观察过拟合，不是普适性训练。
9. 下载 adapter/、checkpoints/、两份生成结果、update_proof.json、token_lengths.json、preflight_manifest.json、frozen_config.json、cloud_environment.txt 和日志；验证文件后停止实例。关机存储计费与到期保留政策按商家实际规则确认。

## 信号与验收边界

完整序列是 system/user/assistant。脚本用 chat template 构造提示词前缀和完整序列，确认前缀完全相同后，将提示词 labels 设为 -100；只学习 assistant 代码及结束标记。micro-batch=1，不做 packing，不引入 padding loss。

一步 SFT 不需要 reward 模型或 Rubrics 奖励。尚未独立校准的 Rubrics 不参与 loss，不能据此声称做了 Agentic RL。GRPO 需要同任务多轨迹、可靠奖励和相对优势，属于后续工作。

要证明有用，还需要未参与提示词/修复的自然网页、冻结质量标准、同生成预算基座/适配器对照、执行及语义质量检查。代码可解析、loss 下降都不能代替完整性/纯净度/结构忠实性。

## 执行候选代码

本脚本绝不 exec 模型输出。AST 检查与超时不是操作系统沙箱。后续应先审查，再在隔离容器执行：无网络、只读输入、非 root、无宿主 secrets、限制 CPU/内存/进程/时间，然后按输出协议验证。训练实例不能直接执行未经隔离的未知候选代码。
