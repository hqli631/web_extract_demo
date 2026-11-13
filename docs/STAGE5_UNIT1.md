# 5.1：从代码修复轨迹理解Agentic RL与GRPO

后续：用户已正确回答A/B，原话保存output/stage5/unit1/learning_feedback.json。继续本单元后半部分见[更新信号与质量开销对照](STAGE5_UNIT1_FOLLOWUP.md)，入口learning/grpo_update_signals.py；下文A/B保留为历史学习问题，无需重复回答。

本单元来自固定计划5.1，围绕岗位“训练生成/修复抽取代码的Actor，提升质量并减少搜索步数”。复用第三阶段真实修复记录，不另建网页项目。第四阶段独立校准仍未完成，以下奖励数组是数学教学假设，不能直接用于真实训练。

## 本单元的三部分

1. 真实修复记录→任务、动作、观察和反馈的轨迹。
2. 同任务多条候选的假设reward→组均值、标准差、相对优势。
3. 概率比裁剪、KL与策略更新的概念边界。先看前两部分，再查看第三部分，不启动5.2训练。

## 操作一：运行并打开报告

~~~powershell
cd "D:/codex project/web_extract_demo"
./.venv/Scripts/python.exe -X utf8 ./learning/grpo_basics.py
Start-Process "./output/stage5/unit1/index.html"
~~~

预期输出：

~~~text
HISTORY: byline body 22 -> 21; moved to author; historical reward=None
input: mean=0.600000 std=0.316228
  advantages: -1.264911, -0.632456, 0.632456, 1.264911
all_equal: mean=0.800000 std=0.000000
  advantages: 0.000000, 0.000000, 0.000000, 0.000000
TRAINING: model rollouts=0; parameter updates=0; rewards=hypothetical
~~~

脚本只读取历史记录和计算数值，不调用模型、不执行新代码生成、不更新模型参数。历史输入的哈希会记录，v1/v2代码哈希会与补丁记录核对；文件改变会报错，不能重写历史凑通过。

## 操作二：读懂一条真实轨迹

报告第二部分展开6步：任务与样本→v1代码→执行观察→署名反馈→v2补丁→回归观察。

实际例子是“21世纪经济报道记者 程雪溶”被v1归入正文。评审提供原文、XPath和分流要求；v2加位置与整行格式约束，将其移入author。该页正文22→21块，6篇生成页输出不变。这是保存记录支持的修复，不代表所有作者格式都解决。

|概念|项目中的含义|不要混淆|
|---|---|---|
|Actor|生成和修复代码的模型|不是CPU上运行的XPath解析器|
|可见状态/上下文|任务、样本、已有代码、工具观察、历史反馈|Agent通常不能看到环境全部信息|
|动作action|输出代码、提交补丁或调用工具|一次action可含多个token|
|环境观察observation|执行结果、报错、Rubrics证据反馈|结构检查通过不等于语义质量通过|
|轨迹trajectory|按顺序记录任务、动作、观察与反馈|本次是事后重构，不是当时保存了概率的训练rollout|
|policy|模型给定上下文选择动作的概率分布|不是一份XPath规则配置|
|rollout|在指定policy下实际采样得到的交互轨迹|历史补丁不能自动视作当前policy的新采样|
|terminal reward|对结束结果提供的标量评价|反馈理由是信息，不等于自动已有数值奖励|
|credit assignment|最终结果好坏该归因给前面哪些动作|最后得高分不证明每一步动作都好|

历史轨迹没有校准后的数值训练reward，保留null。改Python代码是动作，只有利用loss反向传播并由优化器更新Actor权重，才有模型训练参数更新。历史记录不含old-policy token概率，也不能直接当作本轮GRPO的on-policy训练批次。

## 操作三：手算组相对优势

假设同一个任务采样4条候选轨迹，教学reward为0.2、0.4、0.8、1.0，均值0.6。

~~~text
总体方差 = ((−0.4)² + (−0.2)² + 0.2² + 0.4²) / 4 = 0.1
总体标准差 = sqrt(0.1) ≈ 0.316228
A_i = (r_i − mean) / (std + 1e−8)
~~~

对应优势约−1.264911、−0.632456、0.632456、1.264911。奖励回答“怎样评价结果”，优势回答“这条轨迹相对这一组怎样”。不能把正优势理解成业务采用通过，也不能把不同任务任意混成同组。

本实验约定总体标准差（除以G），epsilon在标准差之外。实际GRPO框架的标准差、归一化、epsilon位置或奖励缩放可能不同，训练时以具体实现为准。

再运行一个对照，不必改代码：

~~~powershell
./.venv/Scripts/python.exe -X utf8 ./learning/grpo_basics.py --rewards "0.8,0.8,0.8,0.8"
Start-Process "./output/stage5/unit1/custom/index.html"
~~~

预期均值0.8、标准差0、优势全0。自定义实验保存在custom/，默认记录不被覆盖。全同分可能是候选确实相近、任务太简单或评审分辨率不足，不能仅凭这一点断言具体原因。仅本组reward项没有相对区分信号；KL或其他损失项仍可能产生梯度。unknown不是0分，不能为了运行而塞入奖励数组。

## 操作四：理解优势如何参与更新（本轮可选查看）

报告中概率比裁剪只算标量：ratio=当前policy对同一动作的概率/采样old policy概率，不是两个reward相除。

~~~text
s = min(ratio × A, clip(ratio, 0.8, 1.2) × A)
~~~

这是要最大化的surrogate项，实际loss通常取负并包含其他项。A=1、ratio=1.5时s=1.2；A=−1、ratio=0.5时s=−0.8。A=−1、ratio=1.5时s=−1.5，A=1、ratio=0.5时s=0.5；裁剪不是一律截断所有方向。只算这些数值没有计算图，也没有更新权重。

KL约束通常限制当前policy偏离参考policy。参考policy是稳定约束基准；old policy是采样轨迹时的策略，二者角色不同。完整GRPO还涉及token概率、mask、轨迹聚合、KL估计和框架变体；本脚本不是完整训练器，也没有自动微分。

## 本轮请反馈两个理解点

- A：岗位中的Actor要改进什么？这里是否直接训练XPath本身？
- B：四条轨迹都得0.8时，为何不能仅靠该组reward辨别谁更好？

用自己的话回答即可。答复后继续5.1的训练信号与质量/修复步数/开销比较，再按5.2检查资源；不跳过概念就开训练。

文件：learning/grpo_basics.py是统一入口；output/stage5/unit1/results.json记录真实历史证据与假设计算，index.html用于查看。默认没有参数更新，实际训练与RSI分别属于5.2和5.3。
