# 第三阶段3.2：少样本生成簇级抽取代码

日期：2026-11-13。状态：两簇候选v1与生成组执行报告已实现。只运行每簇3篇生成页，不读取修复/封存测试正文；没有启动3.3修复或3.4最终评估。

## 1. 先回顾岗位和本单元要求

岗位主方案是按布局簇采样，由Coding Agent生成解析代码，CPU在整簇复用。3.1已形成两个经过壳核验的任务簇和split_v2分工。3.2将“XPath候选”推进为两个可执行Python模块，统一函数接口并保留生成输入、代码版本与运行证据。

本次由当前对话AI读取6篇生成页的正文DOM、标题及结构后编写代码，没有调用外部模型API。父对话此前已了解历史修复样例，因此本过程不是独立盲生成实验；本单元新执行只使用生成组，不能把输入限制写成模型完全不知历史样例。新封存正文未用于生成。

## 2. 亲手运行

~~~powershell
cd "D:\codex project\web_extract_demo"
./.venv/Scripts/python.exe -X utf8 ./learning/run_cluster_generation.py
Start-Process "./output/stage3/generation/index.html"
~~~

默认离线重放已生成代码，核验split_v2和生成快照哈希；不重新生成代码、不联网、不调用模型、不打开修复/封存页。首次保存task及生成记录，此后输入或代码版本变化会拒绝覆盖，后续修复需创建v2。

预期：

~~~text
sina: blog_01.html blocks=43 metadata=1 excluded=3; contract PASS
sina: collected_14a028de299edfab.html blocks=23 metadata=0 excluded=1; contract PASS
sina: collected_af5904c15d1deebc.html blocks=16 metadata=1 excluded=1; contract PASS
chinanews: xpath_practice.html blocks=7 metadata=1 excluded=2; contract PASS
chinanews: xpath_practice_02.html blocks=26 metadata=2 excluded=2; contract PASS
chinanews: xpath_practice_03.html blocks=33 metadata=2 excluded=2; contract PASS
UNIT 3.2: generation-only execution complete; repair/test untouched
~~~

PASS仅验证执行、输出契约、原文引用、表格行列和顺序，不代表语义全对、完整率或新页泛化。遇到frozen generation changed时不要删除记录再跑，先检查哪个输入/候选变了，并用新版本保留历史。

## 3. 看懂输入—代码—输出分工

~~~text
split_v2的3篇生成页
  → task.json：生成任务、完整文章DOM、标题候选、输入哈希
  → 当前对话AI：提出两个独立Python代码候选
  → sina_v1.py / chinanews_v1.py：extract(bytes)
  → 执行器：独立进程运行候选、设超时、检查输出
  → results.json与index.html
~~~

生成一次代码以后，对同簇页面执行该模块不需要逐页调用大模型。但代码生成、修复、审核和CPU执行均有成本，不能说CPU零成本。新页面是否可复用尚待3.3/3.4验证。

## 4. 打开两个代码模块，按顺序观察

### 4.1 统一接口

两个模块都提供extract(data)，data是HTML字节，返回：

|字段|含义|观察重点|
|---|---|---|
|title|主标题字符串|不是随便取第一个h1|
|blocks|有序正文块|kind/text/xpath；table另带rows|
|metadata|作者、来源、编辑|单列而不进入阅读正文|
|excluded|确认的独立组件|保留类别、原文和位置，不静默删除|
|warnings|静态内容和未处理风险|警告不是已经解决了风险|

函数不接收文件名，不自己读目录，不请求网站；它只处理调用者传进来的HTML。这样批处理执行器可复用同一份代码。

### 4.2 标题选择

新浪选择h1.main-title，中新网选择h1.content_left_title；两者都检查匹配数等于1。中新网生成样本包含两个h1，使用全页第一个h1会依赖位置或重复展示。选明确类别，是把DOM观察转成稳定条件；未来模板变动时仍可能失败。

### 4.3 有序块收集

先遍历正文容器的子节点，对包装div继续递归；遇到段落、图说或表格时作为一个块处理，避免再递归生成重复子块。不是全页搜所有p。

table使用rows保存行列，保留它在段落之间的位置。中新网adInContent在生成样本中是广告占位，因此作为独立组件排除，而非“所有table都是广告”。目前只测了合成信息表格，不能称真实表格泛化已验证。

### 4.4 分类与证据

新浪专题段需要同时有专题前缀和链接；文章里正常链接保留。带article-editor类别的内容单列编辑，来源前缀单列source。居中样式小标题分类是一条候选启发式，可能误判，保留原文。

中新网独立署名用整行受限格式匹配；带冒号的“中新社记者：……”问题不匹配署名。广告占位、页码组件和编辑分别归档。不能把包含“记者”的所有句子删除。

所有记录保留原节点XPath。程序用原HTML重新定位并核对文本；这证明引用存在，不证明分类语义必然正确。

## 5. 为什么元数据和排除数与旧练习不同

旧练习主要收集p和pictext；本次从容器子树遍历，还能记录容器内部的编辑div、广告占位table、二维码推广div等。例如中新网第一篇可读仍是7块，但增加编辑元数据1条和组件排除2条。

因此不能把blocks+metadata+excluded总数与旧raw_blocks直接相等比较：候选范围不同，部分排除组件文本还是空的。可读块数一致也不等于旧审核全部被独立复核。

## 6. 候选代码限制和未解决问题

执行前只允许lxml/re导入及受限代码结构，在独立Python进程和临时工作目录运行并设8秒超时。AST检查降低误用风险，**不是操作系统安全沙箱**；只能运行本项目已审查的可信候选，不能据此执行任意不可信生成代码。没有配置任意网络或文件工具，但进程本身未获得内核层隔离。

当前v1局限：

- 只覆盖两个已知静态模板壳，不执行JS/CSS，不做OCR。
- 不因display:none一律删除节点，但仍未证明折叠内容完整。
- 包装节点自身text/tail、复杂嵌套、广告类别变化、表格合并单元格都可能需要后续反馈。
- 表格行列未展开rowspan/colspan；不把普通文本序列当完整表格语义。
- 作者格式、样式小标题是有限启发式，不适用于任意站点。
- 生成上下文有历史知识、无独立人工金标，本次只有生成组契约验证。

这些限制写入候选说明，3.3按固定修复组找证据，不在本轮偷看修复/测试原文调代码。

## 7. 文件导航与本次验收

|文件|用途|
|---|---|
|learning/generated/sina_v1.py|新浪代码候选，独立extract函数|
|learning/generated/chinanews_v1.py|中新网代码候选，独立extract函数|
|learning/run_cluster_generation.py|生成组任务准备、候选执行和契约检查|
|output/stage3/generation/task.json|完整生成输入与代码哈希；不含修复/测试正文|
|generation_record.json|生成来源、版本、API调用0与范围边界|
|results.json|6页执行输出、源证据、验证状态|
|index.html|用户阅读报告|

亲手运行后回答三点：为什么extract函数不需要知道文件名；为什么中新网标题不能直接全页取第一个h1；为什么contract PASS还不能证明跨页泛化。

3.2工程产物已具备，个人理解待运行确认。下一步只进入计划3.3：打开修复组、记录错误、生成v2补丁、回归，最多两轮。不使用封存测试组挑补丁，不提前做RL或API集成。
