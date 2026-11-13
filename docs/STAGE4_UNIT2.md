# 第四阶段4.2：保存实际判断，再检查一致性

纠正日期：2026-11-13。上一版直接读取expected_answers生成actual，所谓70题一致率1.00属于标签复制，不是AI评审结果。结论撤回，历史文件保存在output/stage4/calibration/invalid_v1/；原入口显示失效提示。

本次当前对话AI实际阅读完整源及14个候选，保存逐题判断和具体理由；Python只核对引用、任务哈希、题目齐全，再与预期比较。expected只用于比较，不参与生成actual。测试验证改变expected不改变已保存答案或质量分。

learning/prepare_rubric_review.py输出不带expected和变换名称的task.json，另存private_mapping.json供比较。review_notes.json记录当前对话判断及引用ID，reviewer_current.json展开精确引文。评审者知道历史案例构造，不能叫盲评。两个隔离上下文任务收到空消息未执行，独立复核和重复一致率为待完成/null。

运行learning/run_rubric_calibration.py；打开output/stage4/calibration_v2/index.html。具体命令、例子和知识讲解见[4.3操作说明](STAGE4_UNIT3.md)。

comparison.json提供逐题三类混淆矩阵、unknown率、协议有效数及预期/实际比较；不将合成案例一致率称为真实网页准确率。API回放调用0，API费用和评审耗时未测量为null，训练更新0。无效引用不计语义分；引文存在不保证理由正确或覆盖完整。

状态：保存评审、引用验证、比较统计已实现；独立抽查、重复评审和自然页校准待完成。4.3计分与门槛检查已实现，第四阶段未整体完成。
