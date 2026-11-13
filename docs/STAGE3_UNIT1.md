# 第三阶段3.1：观察布局分组，建立样本协议

状态：结构盘点程序已实现并运行；分组和样本分工是草案，尚未补齐新测试页与冻结协议。不要越过本单元开始生成代码。

## 2026-11-12进度更新：3.1工程操作已完成，等用户运行解释

上文状态和下文23页/15簇记录是第一组历史盘点。本次保留v1结果，新增五级模板壳核验、历史近重复检查、按列表顺序补采12个新测试快照，以及修订后的冻结分工。以output/stage3/protocol/split_v2.json为当前协议；split.json为发现生成/修复重复前的初版，不再用于后续生成。

### 本次运行命令

~~~powershell
cd "D:\codex project\web_extract_demo"
./.venv/Scripts/python.exe -X utf8 ./learning/prepare_cluster_protocol.py
Start-Process "./output/stage3/protocol/index.html"
~~~

默认只读保存快照、执行结构和去重检查并重建报告，不联网、不调用模型、不生成抽取代码；不要加--collect，采集已完成，再次采集会被拒绝。

预期：

~~~text
SHELL CLUSTERS: 2 verified: True
SEALED TEST ELIGIBLE: {'sina': 6, 'chinanews': 6}
UNIT 3.1: ready_for_user_learning_check ; split: frozen
~~~

### 先看报告中的两个壳路径

新浪六个历史页的正文容器及祖先链：

~~~text
div[id=artibody;class=article]
div[class=article-content-left]
div[id=article_content;class=article-content.clearfix]
div[class=main-content]
body
~~~

中新网六个历史页也有一致的五级外壳，容器是div.left_zw。v1观察的是容器内部深度4路径，容易因段落样式、图说、表格不同拆细；v2把正文容器与祖先壳作为模板身份，把内部差异保留为簇内变体。这是基于历史知识的显式模板核验，不是为了凑两个簇降低0.60阈值，更不是通用无监督视觉聚类。

壳匹配支持复用定位框架的假设，不证明抽取代码已经有效；中新网页有多个h1和表格结构，语义处理仍留给3.2/3.3。

### 再看样本分工与重复修订

每个任务壳簇固定3个生成页、3个历史修复页、6个新封存测试页，共24个槽位。测试URL从固定列表DOM顺序选取，排除工作区已知URL；采集失败不替换，未按提取效果挑页。

近重复使用容器文字去空白后的字符5gram Jaccard，阈值0.85；另核对URL和快照SHA256。历史库发现12对重复候选，其中collected_c2d1dbf788829343.html与xpath_practice.html正文完全重复，不能分别占生成和修复名额。因此保留split.json初版，split_v2移除重复修复页，按历史路径字典序补入匹配壳且与已选页不近重复的validation_blind/samples/collected_5029464d5612ed80.html。该页此前已暴露，只作为修复材料，不作为新测试。

12个新测试页均匹配对应模板壳，未达到0.85近重复阈值，最高相似度约0.123。这里只做静态结构和去重预检，未审核提取效果。报告不展示测试标题或正文；后续3.2生成者只能读取生成组，3.3才读取修复组。

### 保留两个短文本难例

两篇新页的静态容器文字少于100字。程序最初额外加了未写入采集前协议的100字入选门槛，在正式使用分工前删除该事后条件，记录在verification.json，页面未替换。现在两页均保留为短文本风险：可能是短消息、图片或动态内容，需要后续验证，不因短文本淘汰难例。

### 本次文件

|文件|作用|
|---|---|
|learning/prepare_cluster_protocol.py|壳核验、有限采集与默认离线复验|
|output/stage3/protocol/protocol.json|采集前固定的选页顺序、目标、历史URL、模板壳|
|sina/selection.json、chinanews/selection.json|列表快照哈希与原始选页顺序|
|manifest.json|采集时间、URL、状态、快照哈希|
|verification.json|重复证据、结构匹配、短文本风险和修订原因|
|split_v2.json|当前冻结的3/3/6分工及快照哈希|
|index.html|本次阅读入口，不展示封存正文|

### 你亲手确认三个知识点

1. v1的“15个内容结构簇”和v2的“2个任务模板壳簇”为什么能同时存在？分别看什么？
2. 两个文件名不同，为什么不能分别当生成样本和修复样本？在报告里找到相似度1.0的例子。
3. 静态文字很少的两页为什么保留？后续提取失败应记录什么，而不是怎么换掉它？

工程操作达到3.1结束条件，用户运行并能解释上述问题后再进入3.2。新页仅在工作区历史范围核查“未使用”，不能证明工作区之外的使用史；结构和近重复预检不等于正文质量评估。

---

以下保留第一组盘点操作，作为方法演进回顾。

## 与岗位和固定计划的关系

岗位先对网页按DOM/布局聚簇，再让Coding Agent看少量页生成整簇代码。只有理解“哪些页可共享规则、哪些是簇内变体”，才能解释代码复用与成本摊销。计划见[岗位学习计划3.1](ROLE_ALIGNED_LEARNING_PLAN.md)。

本次完成3.1第一组操作：盘点本地历史HTML、计算结构特征和候选分组、展示数据分工及缺口。暂不采集或生成解析代码，不改变原始样例和旧基准。

## 1. 运行并打开结果

在VS Code的PowerShell终端执行：

~~~powershell
cd "D:\codex project\web_extract_demo"
./.venv/Scripts/python.exe -X utf8 ./learning/cluster_layouts.py
Start-Process "./output/stage3/layout/index.html"
~~~

此命令离线运行，不调用模型，不执行网页JS，只覆盖本单元的inventory.json及index.html。预期：

~~~text
INVENTORY: pages=23; candidate_clusters=15
sina: historical=6; generation=3; repair_pool=3; fresh_test_gap=6
chinanews: historical=6; generation=3; repair_pool=3; fresh_test_gap=6
UNIT 3.1: inventory ready; fresh test data and split freeze still pending
~~~

23是21个samples目录HTML加前阶段两篇快照，包含导航索引等非文章，不表示23篇合格文章。samples/index.html明确标为non_article_navigation。其他非目标页面只作盘点，不自动进入两个目标模板的训练或测试。

## 2. 先读顶部：为什么不是有6页就够了

新浪和中新网各6篇历史页，草案各分3篇生成和3篇修复池，均不是新测试页。每类缺6篇自然新页，总计缺12篇；还要排查近重复和核验布局簇后才能封存。

两个目标模板不等于已经聚成两个簇。报告列出每个模板对应的多个候选簇。当前3+3只是业务模板层面的资源盘点，不能宣称已满足“每簇3篇样本”。若最终分簇不适合复用，须根据结构证据重新核验候选，不按抽取结果挑页。

修复池表示计划用途，不表示从未见过；这批页此前均已用于学习。下一步生成提示只放选定的3篇，不能用当前历史材料声称对整个学习过程严格盲测。

## 3. 看一个同簇例子：文字不同，结构相似

在报告中查找xpath_practice.html和xpath_practice_02.html，展开两条记录。它们当前同属layout_12，相似度0.6875。观察共同的div.left_zw容器、直接子p，以及第二页多出的图说和图片结构。

实际特征例子是“容器签名/p/strong”这样的路径。程序不保留段落原文和兄弟位置序号，并把重复路径折叠成集合。因此文章更长、p更多不一定更远；新增图说或嵌套节点才会增加结构差异。

亲手回答：第二页有图片说明，为什么它仍可能和纯段落页共享大部分抽取逻辑？答案应同时提到共同容器和额外节点处理，不能只说来自同站点。

## 4. 看一个分开例子：同站点为何不自动同簇

对比xpath_practice.html和xpath_practice_03.html，相似度约0.579，低于本次0.60阈值，因此候选分组不同。不要立即推导“规则不能复用”：我们已有证据说明两者可以共用部分容器规则，当前特征还包含内容内部结构和样式差异，可能把可复用页面拆细。

再看blog_01.html与collected_14a028de299edfab.html：同有artibody，路径集合相似度0.4。单独一个id相同不足以描述全部局部结构，但局部结构不一样也不必然要独立写整份代码。这正是后续核验“不同簇”还是“同簇分支”的问题。

本次先保留未校准结果，不为凑两簇临时调阈值。你需要学会诊断结构特征的局限，而非相信一个聚类数字就是答案。

## 5. 相似度如何计算

设A、B为两页去重后的路径特征集合，Jaccard(A,B)=共同特征数/并集特征数。它衡量特征重合，不是提取准确率。

程序先按历史已知容器或唯一article/main选择候选区域，无唯一候选则用文档回退。选择过程没有根据域名分簇，但有历史容器知识辅助，因此不是完全无监督聚类。对不同候选区域的分数不能直接当视觉布局相似程度。

再按固定文件顺序分组，要求新页与簇内每个已有成员均达到0.60；这避免A像B、B像C就把并不相似的A/C串起来。但贪心顺序、深度上限4、忽略频次、属性过滤和阈值都可能影响结果。

浏览器视觉布局还受CSS、屏幕大小和JS影响，本脚本未验证这些。完全相同页面或相同URL已做初筛，正文近重复尚未完成；不把此盘点当成完整采集与去重系统。

## 6. 文件分工与本次结束点

|文件|作用|
|---|---|
|learning/cluster_layouts.py|读取历史页面、计算局部结构特征、分组并写报告|
|output/stage3/layout/index.html|用户阅读、展开特征、打开本地快照和原网址|
|output/stage3/layout/inventory.json|来源、SHA256、候选区域、特征、簇ID、相似度、分工和缺口|
|tests/test_layout_inventory.py|检查正文文字/段落数量不改变集合特征，嵌套结构可见，避免链式合并，旧页不升级新测试|

本次不要求逐页人工贴标签。完成三个观察即可：解释0.6875的共同结构、解释0.579为什么需要核验、解释历史样例为什么不能充当新封存测试。

后续继续留在3.1：核验候选簇与簇内变体，完成必要补采和近重复排查，记录封存分组。未满足这些条件前，本单元标为进行中，不启动3.2。
