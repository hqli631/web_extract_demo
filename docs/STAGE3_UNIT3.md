# 第三阶段3.3：用反馈修复抽取代码

日期：2026-11-13。工程操作完成1轮补丁（最多2轮预算），当前停止，未启动3.4封存测试。个人理解待亲手运行解释。

## 回顾岗位要求

岗位需要根据执行报错和质量反馈修复簇级代码，以处理同簇异构与折叠内容。本单元读取split_v2中6篇固定修复页，保存v1输出，由当前对话AI对照静态正文DOM检查问题，提出v2补丁，再用6篇生成页回归。没有调用外部模型或训练参数，离线命令只重放已保存的修复过程。

## 1. 运行修改前后对比

~~~powershell
cd "D:\codex project\web_extract_demo"
./.venv/Scripts/python.exe -X utf8 ./learning/run_cluster_repair.py
Start-Process "./output/stage3/repair/index.html"
~~~

默认离线运行v1/v2，不联网、不调用模型、不读取封存页。写入本单元报告和结构化证据；如果发现已冻结输入/代码/反馈变化，会拒绝覆盖，不要删除记录消除报错。

预期关键结果：

~~~text
repair collected_c5d4b9cdcf5b4c91.html: blocks 22->21; moved=1; regression PASS
repair new_1.html: blocks 103->103; moved=0; regression PASS
repair new_2.html: blocks 20->20; moved=0; regression PASS
repair collected_4b026cde5c5744c1.html: blocks 7->7; moved=0; regression PASS
repair collected_4fdd3a7b48c5a575.html: blocks 6->6; moved=0; regression PASS
repair collected_5029464d5612ed80.html: blocks 29->22; moved=7; regression PASS
UNIT 3.3: one repair round; natural moves=8; generation unchanged=6/6; sealed test executions=0
~~~

此外会打印6篇生成页完全不变的检查。

## 2. 第一个自然badcase：独立署名混入正文

报告找到collected_c5d4b9cdcf5b4c91.html。源第一个p是“21世纪经济报道记者 程雪溶”，v1把它作为普通段落。

反馈包含：文件、XPath、原文、旧分类、期望分类和限制。v2只在正文容器第一个直接子p中，识别整行“媒体+记者+姓名”格式，移入metadata.author。正文中“据记者了解”等叙述保持，不做全局关键词删除。

观察：blocks减少1，metadata增加1，原文及XPath不变。修复的是sina_v2.py的识别代码；没有手工改结果JSON。格式仍是有限启发式，不覆盖多语种、多个作者、复杂署名或署名恰好与叙述同形的情况。

## 3. 第二个自然badcase：页尾制作信息混入正文

找到collected_5029464d5612ed80.html。最后7个p是带竖线的总策划、策划、统筹、执笔、审校、视觉及工作室出品。

v2从正文末尾反向识别连续、格式明确的制作信息，只将该后缀移入metadata.production_credit。它们不能全部叫作者，编辑仍是editor。若同样的“｜策划：……”出现在文章中间，后面还有正常正文，就保留为正文；合成中间署名对照验证了这一点。

这是明确的输出协议增补：新增production_credit类别。验证器通过显式选项支持该类，旧3.2默认契约保持原样。下游若不支持新字段，不能静默忽略后继续采用。

## 4. 第三个问题：折叠容器的内联文字

这部分是明确标注的合成反例，不是从自然页面发现的线上失败：

~~~html
<div style="display:none">Folded <span>article detail</span> remains.</div>
~~~

v1只处理段落/表格等块，递归到span时没有生成正文块；因此漏掉文字。v2在div、section、details仅含内联内容而没有已识别块后代时，把包装节点作为一个paragraph记录，保留原XPath和文字。

注意：修复针对块识别，不是删除“隐藏过滤”——v1本来就没有按display:none过滤。v2也没有决定所有隐藏内容都是正文；未识别隐藏导航仍可能混入。复杂text/tail与子块混排、CSS状态、JS加载和图片正文未解决。

受控样例还检查嵌套p：v1本来就能保留，v2不得回归。测试暴露v2草稿在“无直接p但有嵌套p”时索引空列表的错误，已在本轮候选定稿前补了非空检查；不是额外增加一次Agent修复轮数。

## 5. 原有表格不是本轮修复成果

new_2的5行3列比较表已经由v1保留，20块是19个段落加1个表格，编辑另列。本轮保持不变。不要把历史旧./p漏表案例与当前v1候选混为一谈，更不能声称本轮修复了它。

## 6. 你需要理解的工作流程

~~~text
固定修复页 + v1输出
  → 当前对话AI的具体错误判断与反馈
  → 新版本v2代码（保留v1）
  → 同页前后比较
  → 生成组回归 + 合成边界检查
  → 停止本轮，记录剩余限制
~~~

一轮已解决当前明确的两个自然元数据问题和受控包装文字遗漏，不为用完预算制造第二轮。最多两轮是上限，不是必须执行两轮。生成/修复页已用于调试，不能报告为独立准确率。

## 7. 文件导航与验收

|文件|作用|
|---|---|
|learning/generated/sina_v2.py、chinanews_v2.py|新解析候选；v1保留|
|learning/run_cluster_repair.py|固定修复组和生成组重放、检查差异、生成报告|
|output/stage3/repair/feedback.json|AI反馈、原文位置、期望动作、剩余限制|
|repair_record.json|修复预算、代码哈希、实际diff、输入协议、API和训练次数|
|results.json|完整v1/v2输出、自然变化、合成对照|
|index.html|本次阅读入口|

亲手运行后，先看两个自然问题的moved字段，再看代码diff和folded_leaf对照，回答：

1. 为什么作者和production_credit要分开？为什么不能删除所有包含“记者/策划”的段落？
2. 为什么这次修正属于代码修复，而前面改审核动作属于结果修正？
3. 合成折叠反例通过，为什么还不能说真实网页折叠内容全覆盖？

下一步严格为3.4：先冻结v2代码与评价方案，再首次执行封存测试并做CPU成本报告。未完成评价冻结前，不打开封存正文调代码。
