# 第四阶段4.3：判断如何转成分数，哪些结果不能采用

本单元来自固定计划的“reward及门槛”：岗位需要把正文质量反馈交给代码修复Agent，将来才可能用于训练写代码的Actor。程序通过、文本变长或引用存在，不能直接证明正文质量。

## 先了解纠正了什么

上一版4.2把expected_answers复制为actual，所谓1.00一致率不成立。旧代码、回答和报告保存在output/stage4/calibration/invalid_v1/，该批明确作废。新入口读取已保存的当前对话AI判断，只校验和计分，绝不从expected产生actual。

本次当前对话AI查看完整源和14个候选，逐案给出具体理由及引用，保存review_notes.json及展开引文后的reviewer_current.json。程序分别核验源、输出引文。预期标签只在最后做比较。两个独立上下文子任务连续收到空消息，未执行评审，故重复评审/独立校准继续待完成。

## 第一步：运行并看四个例子

~~~powershell
cd "D:/codex project/web_extract_demo"
./.venv/Scripts/python.exe -X utf8 ./learning/run_rubric_calibration.py
Start-Process "./output/stage4/calibration_v2/index.html"
~~~

程序回放已有回答，不新调用AI，也不更新模型参数。报告改为calibration_v2。

|案例|问题|运行输出|含义|
|---|---|---|---|
|item_04|当前任务内完整正确候选|score=1.0，candidate_within_static_scope|仅表示可进入静态任务候选采用|
|item_02|源表格未进入候选|score=0.8，reject_complete_article|Q3=no，修复表格提取|
|item_05|正文混入APP优惠券推广|score=0.8，below_threshold|Q4=no，修复用途分类|
|item_06|只有图解导语、缺少图片内容证据|score=None，needs_evidence|先补证据，不当no或yes|

展开每题，比较source_evidence与output_evidence。漏表时源证据能引用表格，输出证据应引用完整候选清单表明缺失，不能捏造“输出表格”。错标题item_03的源标题与输出标题应不同。

## 第二步：理解分数与采用门槛

五题yes=+1、no=-1，raw为五题之和；score=(raw+5)/10。五题全yes为1.0，一题no为0.8，等价于通过题数/5。

因此0.9门槛实际上要求五题全yes。当前配置下Q2/Q3关键门槛不额外改变能否通过，却保留“无法作为完整文章采用”的业务失败原因。等权与0.9是冻结的教学选择，尚未用独立数据确定，不是团队生产标准。不要为了让案例通过临时调低门槛。

unknown不是0分，更不是从分母剔除。任一题unknown时score/reward为null，路由到补证据。执行报错、缺题、伪造引用、任务不匹配也不形成语义质量分：应修执行或评审协议，不能解释为已经确认的低质量正文。

## 第三步：查看投机与失败实验

报告的“拒绝计分与投机检查”包括：

- unknown：缺证据，暂不计分。
- invalid_quote：伪造引文，不计分。
- execution_error：抽取执行失败，不计正文语义分。
- stale_task、missing_question：返回不匹配或缺题，拒绝计分。
- copy_entire_page_simulated_judge：复制整页包含作者、导航、推广等，模拟评审判Q4=no，不能以长度换高分。
- dishonest_all_yes：将推广例的Q4故意错误改为yes，保留真实引用，程序仍给1.0。此项预期就是暴露漏洞。

这些是明确标记的模拟，不是额外AI审核。真实已评审错例还覆盖重复堆长度item_08、删除难提表格item_02、删除折叠叙述item_11，分别反馈Q5/Q3/Q2。这只能检验这些受控行为，不能证明覆盖所有reward hacking。

引用核验检查“这句话存在吗”，语义审核检查“这句话支持该判断吗”，校准检查“评审在代表性数据上是否可靠”。三者不能相互替代。

## 你的参与点与下一步

不用改代码。运行一次，看item_02、item_05、dishonest_all_yes，解释：最后一个为何仍能得1.0？应先改计分公式，还是先核对评审对正文用途的判断及证据支持？说明理由即可。

按原计划还需补独立复核和少量自然争议页校准，再完成第四阶段总结。未校准前可以学习轨迹和GRPO数学，但不把当前分数当稳定训练reward，不宣称RL训练已开始。
