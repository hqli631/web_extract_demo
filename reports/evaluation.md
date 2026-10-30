# 正文抽取评测

已评分人工区域：0

|预测|Precision|Recall|F1|误提|漏提|
|---|---|---|---|---|---|
|baseline|N/A|N/A|N/A|0|0|
|rules|N/A|N/A|N/A|0|0|

仅评分已确认且非待判断区域；未确认区域、过期快照不会作为真值。样本内规则得分不能当成泛化效果。未检测到的区域需另外检查。

详情和 XPath 错例见 evaluation.json。rule_candidates.json 为未启用的修正规则建议，需先在界面测试匹配范围，再保存。