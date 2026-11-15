# 5.2 首次真实 LoRA SFT 操作回顾

日期：2026-11-15。用户提供已租服务器SSH后，执行准备包的一次有限训练验证。未购买新实例、修改驱动、扩大步数或执行模型代码。密码未保存到项目。

## 操作及意义

1. SSH只读检查：Ubuntu22.04.4、RTX3090 24576MiB、驱动580.119.02、Python3.12.12、系统内存31GiB、磁盘剩余约26GB。PyTorch2.8.0+cu128实际CUDA可用、支持bf16。驱动显示CUDA13.0是支持上限。
2. 在/root/web_extract_sft_20261115建立独立虚拟环境，继承现有torch。补齐transformers4.46.3、peft0.13.2、accelerate1.1.1等，Trainer导入成功，未覆盖驱动/torch。
3. 上传训练脚本、配置、两条历史任务。来源SHA256与本机一致。直连模型仓库被重置，改用hf-mirror.com获取相同固定revision；模型卡声明apache-2.0。revision仍为ea3f2471cf1b1f0db85067f1ef93848e38e88c25。本轮首次下载模型权重。
4. 云端分词复验7768/5240 token。窗口8192、prompt labels=-100，assistant目标参与loss。先保存基座两条确定性生成结果。
5. 一次LoRA SFT：r8、alpha16、q_proj/v_proj、micro-batch1、lr1e-4、seed42、bf16、SDPA、gradient checkpointing。优化器更新LoRA，基座冻结。
6. 校验保存tensor等于内存参数，新进程重载adapter并生成after。所有生成代码只保存文字。
7. 导出adapter、checkpoint、before/after、日志、环境及证明，6.7MB压缩包传回本机、核对SHA256。远端GPU进程结束、SSH退出；实例未关闭。

## 证据与边界

|项目|实际结果|意义|
|---|---|---|
|optimizer_steps|1|真实发生更新|
|可训练参数|540672|LoRA参数数目，非基座全部参数|
|最大参数变化|约0.0001|有限非零变化|
|训练loss|1.626846|单次批次损失，不是下降曲线|
|历史dev loss|1.830495|历史任务损失，不是未见泛化指标|
|峰值allocated/reserved|14.47/17.02GiB|本次条件实测，不能外推其他模型|
|保存/新进程重载|通过|可保存并恢复适配器|
|新浪before/after|相同，285 token|参数变化可能不改变贪心输出|
|中新网before/after|变化，375→350 token|变化不等于变好|

静态查看发现生成结果仍不符合契约：新浪返回输入摘要字段、metadata等为dict而非list；中新网同样有类型问题，更新后block缺少xpath。剥离代码围栏后可解析为Python，也不等于可以执行或质量正确。没有采用候选、没有质量提升结论。

本轮是SFT而非GRPO；独立Judge校准仍未完成。仅1条历史train＋1条历史dev，不是正式训练语料规模。5.2有限真实更新冒烟完成，效果实验与5.3 RSI未完成。

## 你现在操作

~~~powershell
cd "D:\codex project\web_extract_demo"
.\.venv\Scripts\python.exe -X utf8 .\learning\report_cloud_sft.py
Start-Process ".\output\stage5\unit2\cloud_run_20261115\index.html"
~~~

预期REAL SFT PASS，同时QUALITY未证明。此命令只复验本地证据，不联网不训练。打开update_proof.json，观察optimizer_steps、parameter_max_abs_delta、adapter_reload_verified；对照before_generation.json与after_generation.json理解权重变化和行为改善的区别。

压缩包在output/stage5/unit2/cloud_run_20261115/training_receipt.tar.gz；SHA256为961f00e0226320ac43b23b1549043681771fe77ab738f8bca89bbc1359f2cfc0。receipt内含adapter与optimizer checkpoint；二进制和大包只在本机保存，不进GitHub。精简文本证据按约定同步。远端目录和模型缓存仍保留。

## 下一步

先理解更新证据和静态失败，不立即增加步数。后续应扩充独立布局任务、复核目标、冻结开发与未见测试协议，在相同预算下比较基座/adapter执行、正文质量与成本。单条样例反复训练主要增加记忆风险。

请在租赁平台确认停止/释放及存储计费规则。退出SSH或GPU任务结束不等于停费；当前不知道平台关机与磁盘保留规则，没有擅自关机/删除文件。本机已有备份，可按平台规则暂停实例避免空转。

两个理解点：为什么540672不是模型全部参数？为什么新浪输出相同也不能否认训练发生？只需观察证明并用自己的话解释，不用改代码。
