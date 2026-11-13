# 5.1后半：更新信号、KL与质量开销对照

前置反馈已收到：你正确区分Actor模型权重与XPath产物，也正确解释全同分优势为0。原话保存output/stage5/unit1/learning_feedback.json。本步骤仍属于固定5.1，来源是岗位“提高代码生成质量，减少搜索与修复步数”；不启动5.2真实训练。

## 1．运行

~~~powershell
cd "D:/codex project/web_extract_demo"
./.venv/Scripts/python.exe -X utf8 ./learning/grpo_update_signals.py
Start-Process "./output/stage5/unit1/update_signals/index.html"
~~~

预期：

~~~text
CLIP: A=+1 ratio=1.50 surrogate=1.20 local_slope=0
KL: current||reference = 0.130812 nats (toy)
baseline: pass=2/4 fail=1 unknown=1; rounds_all=2.75; rounds_pass=2.50; cost=330
efficient: pass=2/4 fail=1 unknown=1; rounds_all=2.00; rounds_pass=1.00; cost=240
TRAINING: parameter updates=0; hypothetical data only
~~~

全部概率、策略对照结果和成本是假设数值；不是新模型rollout、真实训练效果或API账单。原来的真实修复记录仍不补造reward。

## 2．优势告诉方向，裁剪限制本项继续获得收益

固定同一个已采样动作和上下文，old policy概率0.2，current policy概率0.3，则ratio=0.3/0.2=1.5。ratio是概率比，不是奖励比。真实LLM通常逐token计算条件概率比，不能把一个标量当成完整轨迹目标。

看最大化的标量项：s=min(ratio×A, clip(ratio,0.8,1.2)×A)。实际训练loss通常取负号，另含其他项。

当A=+1时：

- ratio=1.1：s=1.1，本项还能随ratio增长。
- ratio=1.5：min(1.5,1.2)=1.2，再增加ratio也不增加本项收益。

当A=−1、ratio=0.5时：min(−0.5,−0.8)=−0.8，继续降低ratio也不增加本项收益。相反，A=−1但ratio=1.5时，结果为−1.5，错误方向仍受惩罚。裁剪并不是把所有概率变化硬限制在区间内。

local_slope是这个标量项相对ratio的局部斜率，不是模型参数梯度。真正权重梯度还涉及ratio如何依赖模型参数；边界处可能不可微，本实验不硬填唯一导数。即使本项局部平坦，其他token、KL等项仍可能更新共享参数。

## 3．old policy与reference policy分别做什么

old是产生当前rollout时的采样策略，用于计算current/old；reference是稳定约束基准，用于限制策略偏离。两者职责不同，即使某时刻数值相同也不能混为一谈。

报告用两动作分布演示KL(current||reference)：reference=[0.5,0.5]，current=[0.75,0.25]。

~~~text
KL = 0.75×ln(0.75/0.5) + 0.25×ln(0.25/0.5)
   ≈ 0.130812 nats
~~~

相同分布KL=0，表示该分布层面没有偏离，不代表质量准确。真实框架的token级KL估计、β系数、mask、聚合和更新配置另按实现确定。本实验只计算值，没有反向传播或优化器。

## 4．评价Agent还要看轮数和总开销

固定四任务的假设对照，两策略都是pass/pass/fail/unknown。总尝试轮数包含首次生成与执行；纯修复次数为总尝试次数减1。不能把所有尝试都叫修复，也不能把全任务通过率当初始失败任务的修复成功率。

|指标|baseline|efficient|
|---|---:|---:|
|确认通过/全部任务|2/4|2/4|
|fail / unknown|1 / 1|1 / 1|
|全部任务平均尝试轮数|2.75|2.00|
|通过任务平均尝试轮数|2.50|1.00|
|假设总成本单位|330|240|
|总成本/确认通过数|165|120|

全任务指标反映失败、未知任务也发生的投入；成功任务指标描述成功时效率。两者不能互相替代。不能删掉fail/unknown再报“通过率100%”，也不能把unknown奖励设0或从分母抹掉。

本例只能说在假设质量状态相同的批次中，尝试轮数和开销减少。不能说准确率提高、泛化更好或RL训练有效；相同粗标签也不足以证明全文质量完全等价。实际对照还需相同质量标准、逐题证据、任务集与成本口径。

先固定完整性、纯净度等质量采用条件，再比较成本。本轮没有选择“质量减去轮数惩罚”的reward公式，避免让严重漏提靠少几轮补偿通过。以后设计真实reward需版本化、校准并检查预算投机。

## 5．反馈与下一步

请用自己的话回答：

- C：A=+1、ratio=1.5时，为什么该标量项不再奖励继续提高概率？
- D：两策略确认通过率相同，平均轮数和总成本下降，应怎么描述收益，能否说准确率提高？

本轮5.1材料已覆盖轨迹、优势、裁剪、KL和质量/步数/成本，个人掌握待这两个判断。答复后按5.2先检查硬件、可训练模型、框架与reward准备情况，再决定训练操作。不先下载大模型或启动付费计算；若条件不足，明确保留真实训练未完成，继续既定RSI有限工程原型。
