# 第一阶段知识复习与操作手册

本阶段目标：拿到保存的新闻 HTML，理解它的 DOM，解释并运行 XPath 抽取规则，检查分类结果，定位错误并用证据验证修正。代码由助手协助维护；复习重点是理解数据经过了哪些步骤、为什么这么处理、失败时从哪里查。

这是一份复习材料，不要求重做已经完成的全部实验。文中命令默认在项目根目录的 VS Code PowerShell 终端运行。

## 1. 当前项目究竟做了什么

输入是保存的 HTML 快照，不是搜索关键词，也不会在每次运行时访问线上网页。输出是结构化 JSON 和报告。

当前统一入口：

```powershell
cd 'D:\codex project\web_extract_demo'
.\.venv\Scripts\python.exe -X utf8 .\learning\run_project1.py
Start-Process '.\output\project1\index.html'
```

统一入口重跑现有抽取和检查，不做联网采集、不调用 AI、不重新冻结基准。报告包含六篇开发页和两类新闻模板。153 个原始候选块拆成 148 个可读块、2 条作者、1 条来源、2 条排除内容。数量守恒不证明原网页的全部内容都已覆盖。

需要读懂的数据流：

```text
samples/*.html
  -> HTML解析成DOM
  -> 标题XPath、正文容器XPath
  -> 块XPath收集候选
  -> 结构检查 / 已保存审核 / 字段分类
  -> JSON输出
  -> 基准比较与回归检查
  -> HTML报告
```

## 2. 文件、路径、解释器与编码

对应文件：`learning/xpath/xpath_practice.py`、`learning/xpath/xpath_practice_sina.py`。

### 2.1 指定解释器

`.\.venv\Scripts\python.exe` 明确选择项目虚拟环境里的 Python。`(.venv)` 是终端环境提示，真正执行哪个解释器仍由命令决定。以前 `py` 指向不存在的 Python，是启动器路径问题，并不是 XPath 或依赖本身错误。

### 2.2 工作目录与脚本目录

```python
Path.cwd()                       # 终端当前目录
Path(__file__).resolve()          # 当前脚本的绝对路径
Path(__file__).resolve().parents[2]  # 当前练习脚本所在项目根目录
```

对于 `learning/xpath/xpath_practice_sina.py`，`parents[0]` 是 xpath，`parents[1]` 是 learning，`parents[2]` 是项目根目录。移动文件后必须重新核对这个层级。

`project_dir / 'samples' / sample_name` 是拼接路径，不是数学除法。`sample_path.stem` 去掉扩展名，用于生成对应 JSON 名字。

### 2.3 命令行参数

```python
sys.argv[0]  # 脚本名
sys.argv[1]  # 用户传入的第一个参数（如果存在）
```

```powershell
.\.venv\Scripts\python.exe -X utf8 .\learning\xpath\xpath_practice.py xpath_practice_02.html
```

这里文件名是参数；如果程序仍写死第一个样例，命令中换名字也不会生效。因此必须观察输出的“正在处理”文件名。

### 2.4 中文编码与 HTML 编码

`-X utf8` 控制 Python 的 UTF-8 模式。`.py` 和 JSON 文件以 UTF-8 保存。PowerShell 的 `$code | python -` 还涉及 PowerShell 把代码编码为字节，可能在进入 Python 前把中文变成问号。优先运行已保存的 `.py` 文件。

如果必须使用管道，在同一个终端先设置：

```powershell
$OutputEncoding = [Console]::OutputEncoding = [System.Text.UTF8Encoding]::new()
$env:PYTHONIOENCODING = 'utf-8'
```

这些设置只作用于当前会话。它们和网页自身的编码声明是不同问题。`read_bytes()` 将网页字节交给 lxml，解析器会参考 HTML 的编码声明；声明错误或缺失时仍可能乱码。

## 3. HTML、DOM、文字与视觉页面

例如：

```html
<div id="artibody" class="article">
  <p>公司发布了<a href="/notice">公告</a>。</p>
  <div><img src="photo.jpg" alt=""></div>
  <div class="pictext">现场照片说明</div>
</div>
```

- `div`、`p`、`a`、`img` 是标签。`id`、`class`、`src` 是属性。
- `div#artibody` 是父元素，第一条 `p` 是它的直接子元素。
- `a` 是 `p` 的子元素，同时也是正文容器的后代。
- 包图片的 `div` 与图说 `div` 是兄弟元素。
- `id` 通常用于唯一标识，但保存异常页面也可能重复，所以仍检查容器数。
- `class` 是多个以空白分隔的类名，不是一个只能整体比较的名称。

`html.document_fromstring(page_bytes)` 把 HTML 解析为树。lxml 不执行网页 JavaScript，也不负责浏览器布局。浏览器“检查”看到的动态 DOM，可能不同于保存文件中的静态 DOM。正文在网页上可见但静态抽取为空时，要排查是否保存完整或依赖动态加载。

### 实际观察

```powershell
Start-Process '.\samples\collected_af5904c15d1deebc.html'
```

正文处右键“检查”，在元素面板按 Ctrl+F，依次搜索：

```xpath
//div[@id='artibody']
//div[@id='artibody']/p[3]
//div[@id='artibody']/p[17]
```

预期分别定位正文容器、第一个小标题、文章来源。悬停节点观察高亮范围，但不能只靠颜色认定它的语义。

## 4. XPath 必须会解释的表达式

| 表达式 | 准确含义 | 本项目用途 |
|---|---|---|
| `//h1` | 从文档根范围搜索 h1 | 标题候选，不保证只有一个 |
| `//div[@id='artibody']` | id 恰好匹配的 div | 新浪正文容器 |
| `./p` | 当前节点的直接子 p | 有边界地收集正文候选 |
| `.//p` | 当前节点任意深度的后代 p | 可能补到嵌套段落，也可能带入嵌套推荐区 |
| `./p[3]` | 直接子 p 中第三个 | 同一快照定位，不是稳定模板规则 |
| `./a` | 当前段落的直接子链接 | 专题导航识别条件之一 |
| `.//img` | 当前节点内部所有后代图片 | 检查图说前的图片容器 |
| `./p | ./div[...]` | 合并两组节点、去重，lxml 返回文档顺序 | 同时提取段落和图说 |
| `@class` | 读取属性 | 判断节点类别 |
| `not(...)` | 条件取反 | 排除已知编辑节点 |

注意：在 `container.xpath('//p')` 中使用开头 `//`，会回到整个文档范围；限定当前容器应使用 `./p` 或 `.//p`。XPath 返回类型不总是元素：`//p` 返回元素列表，`//p/@class` 返回属性字符串列表，`count(//p)` 返回数值。不能对所有结果都调用 `text_content()`。

### 4.1 为什么完整类名匹配写得很长

```xpath
contains(concat(' ', normalize-space(@class), ' '), ' pictext ')
```

`normalize-space` 规范空白，`concat` 给两端补空格，再按带空格的完整类名查找。这样能匹配 `class='pictext muted'`，又不会把 `pictext-extra` 误当 `pictext`。Python 对应写法是：

```python
'pictext' in (node.get('class') or '').split()
```

### 4.2 容器与文本块两级定位

先找到唯一的正文容器，再在它内部挑选内容块。容器解决“去哪块区域找”，块规则解决“区域内哪些元素符合目标”。

容器数量 0：检查模板、保存文件、动态加载、规则拼写。
容器数量大于 1：检查选择条件过宽或重复 DOM。
容器等于 1：只是定位检查通过，仍可能漏段落或混入杂质。

本项目两类规则：

- 中新网：`div.left_zw` 容器，直接子 `p` 加 `div.pictext`。
- 新浪：`div#artibody` 容器，练习脚本当前直接用 `./p` 收集原始候选，再由 Python 分类。

重要代码事实：新浪配置中的 `block_xpath` 是早期排除编辑节点的规则记录，当前新浪脚本未执行它。修改这个配置字段并不会改变脚本的候选块收集。练习入口和根目录工程抽取器也不是完全相同的算法。

## 5. 提取文字时，哪些信息被保留或丢失

```python
text = ' '.join(node.text_content().split())
```

先取得节点及后代文字，再拆开空白并用一个空格连接。例如 `<p>阅读<a>公告</a>。</p>` 能保留“阅读公告。”；仅取 `node.text` 可能只得到“阅读”。

这条语句会合并换行、缩进和重复空白，不适合直接保真提取代码、诗歌等依赖格式的内容；不会读取图片像素，也不会判断 CSS 是否隐藏某段文字。

```python
if not text:
    continue
```

空文本节点被跳过。但含图片的 div 也可能文本为空，不能因此认定它无内容。第一个中新网样例 8 个 p 只有 7 个非空块；另两篇图说前的 div 无文字，但确实包含 img。

DOM 观察方法：`getparent()` 看父节点，`getprevious()` 和 `getnext()` 看前后兄弟元素，`get('src')` 读图片地址，`get('alt')` 读替代文字。alt 为空不证明图片没有文字；图说是 DOM 文本，OCR 是识别图片像素中的文字，两者不同。

## 6. 字段分类与内容范围

当前新浪字段：

| 字段 | 用途 | 是否进入可读内容 |
|---|---|---|
| raw_blocks | 当前候选规则选出的原始非空块，并非整个原网页 | 不直接全部使用 |
| cleaned_blocks | 普通段落 | 是 |
| subheading_blocks | 小标题 | 是 |
| source_blocks | 文章中写出的来源，如上海证券报 | 否，作为元数据单列 |
| excluded_blocks | 专题导航、责任编辑 | 否 |
| content_blocks | 普通段落和小标题按原始顺序合并 | 直接用于阅读 |

`content_blocks` 是合并视图，不是又一种互斥分类，不能重复计数。来源的网页 URL、发布媒体署名、作者姓名是不同字段；`source_blocks` 不是 URL。

中新网当前结构则是 `blocks` 保存原始输出，`cleaned.blocks` 保存正文与图说，`cleaned.authors` 保存作者。两条管线还没有统一字段协议，不能假设它们都有新浪字段。

### 6.1 新浪分类条件与误判边界

1. 责任编辑：匹配完整类名 `article-editor`，而不是删除一切含“编辑”的文字。
2. 专题导航：直接子链接恰好一个、链接文字等于整段文字、以“专题：”开头、href 指向新浪专题路径，四项同时满足。正文含股票链接仍保留。
3. 文章来源：当前仅识别以全角“（文章来源：”开头且以“）”结尾的段落。其他写法可能漏识别，不能声称已解决所有来源格式。
4. 小标题：`cms-style` 的完整样式词命中 `align-Center`。这是当前页面的启发式，居中图说也可能误中，其他样式的小标题也可能漏掉。
5. 其余段落：保留为 paragraph。保留不等于已经确认语义正确。

分类分支顺序为来源 -> 排除项 -> 小标题 -> 普通段落。`if/elif/else` 保证每个候选只进入一个主分类。小标题和普通段落同时附加到可读列表，维持 DOM 顺序。风险声明本轮按内容范围保留；这是任务要求，不能用标签本身推导。

### 6.2 原始块与派生记录

```python
record = {'index': 3, 'text': '...', 'xpath': '...'}
classified = {**record, 'type': 'subheading'}
```

`**record` 复制字段进入新字典。原始记录不必增加分类字段，也不因清理被删掉。原始编号在分类后仍保留，方便定位。这里是浅复制；本例原始字段都是数字或字符串，不含需要同步修改的嵌套对象。

输出使用 `json.dumps(..., ensure_ascii=False, indent=2)`，前者保留可读中文，后者控制缩进；它们只影响表示方式，不提高抽取质量。

## 7. 追溯：XPath、哈希与审核指纹

`tree.getroottree().getpath(node)` 得到同一棵树里定位节点的绝对 XPath，例如 `/html/body/div[2]/.../p[17]`。这是输出证据；不同文章的层级变化可能让该路径失效，不宜直接当作跨页模板规则。

`hashlib.sha256(page_bytes).hexdigest()` 计算网页文件字节的指纹：相同字节可核对为同一快照，任一字节变化都会导致指纹变化；它不能证明事实正确、正文完整或网页来源可信。

审核指纹还包含规则、标题、容器数量和抽取块，因此仅网页未变也不够：规则或输出变化后，旧审核可能过期。

`xpath_semantic.py` 读取保存记录并校验：

- missing：没有记录。
- stale：输入、规则或输出与审核时不一致。
- invalid：记录重复、审核项不完整或证据无法对应。
- current：记录适用于当前输出，不代表已没有质量问题。

`xpath_corrections.py` 只有在审核适用且指令匹配原文、XPath、块类型和已确认的证据时，才移动署名到作者字段。带冒号或问号等句式被拒绝，防止把“中新社记者：……”访谈问题误当独立署名。当前规则也是受限策略，并非通用作者识别器。

## 8. 三种检查分别能证明什么

| 检查 | 能回答的问题 | 不能独自回答的问题 |
|---|---|---|
| 结构检查 | 已知容器内 p/pictext 候选是否漏选、重复或顺序异常 | 容器外、任意其他标签、图片里是否仍有正文 |
| 语义审核 | 在明确范围内，某块为什么是正文、署名或杂质 | 不能把 AI 判断自动当真值 |
| 回归检查 | 新输出是否违背已确认的预期或与冻结结果不同 | 变化是改进还是退化，要结合任务和证据 |

基准是固定比较对象，不是天然正确答案；改变规则时不覆盖基准，不为了让检查变绿而更改预期。先说明需求变化和证据，再修改对应检查，同时保留其他保护条件。

典型真实例子：把第 17 段移到来源后，旧检查仍要求它留在正文，导致 AssertionError。原因是预期没有同步，而不是简单认为提取程序错误。后来增加 type 字段，旧字典不带 type，直接相等比较也会失败；检查应明确比较哪些原始字段和新增类型。

### 必须会读的 Python 检查

```python
assert raw == source_blocks
assert sorted(b['index'] for b in all_classified) == [b['index'] for b in raw]
assert content == sorted(cleaned + subheadings, key=lambda b: b['index'])
```

第一条比较原始文字、XPath 和顺序；第二条检查全部候选恰好分配一次；第三条检查可读结果等于按原始编号排列的正文与标题。数量相同也可能文字错、顺序错或重复，所以不能只比较 len。

`assert` 条件为假会抛出 AssertionError，后面的 PASS 不再执行。练习使用普通启动方式即可；不要用 `python -O`，它会禁用 assert。PASS 只表示写出的这些断言通过。

## 9. 已确认样例：用于读懂结果，不用于背数字

| 样例 | 原始 | 可读 | 另外单列的内容 |
|---|---:|---:|---|
| xpath_practice.html | 7 | 7 | 无独立署名 |
| xpath_practice_02.html | 27 | 26 | 作者 1，3 条图说仍在可读内容中 |
| xpath_practice_03.html | 34 | 33 | 作者 1，4 条图说及 3 条记者问题仍保留 |
| blog_01.html | 45 | 43 | 专题导航、责任编辑各 1 |
| collected_14a028de299edfab.html | 23 | 23 | 当前未命中排除项 |
| collected_af5904c15d1deebc.html | 17 | 16 | 来源 1；可读内容含 13 段和 3 个小标题 |

以上均为已参与开发或审核的样例，不能用 6/6 检查通过宣称泛化准确率。72 项工程测试同样是已编码行为的验证，不是 72 篇真实网页准确率。

## 10. 巩固操作：四组观察，不改规则

### 操作 A：整体数据流（10 分钟）

运行统一入口并打开报告（第 1 节命令）。先查看运行日志，再进入单页结果。回答：原 HTML 放在哪、生成 JSON 在哪、报告是重新运行还是展示旧数据、这次有没有调用模型？

### 操作 B：结构定位（15 分钟）

打开博盈特焊本地网页，在元素面板执行第 3 节的三个 XPath。再打开新浪脚本，搜索 `container.xpath("./p")` 和 `is_subheading`，对应容器、块选择和分类。回答：为什么选中 artibody 还需要过滤？为什么第 3 段分类后不应丢掉？

### 操作 C：字段核对（15 分钟）

```powershell
.\.venv\Scripts\python.exe -X utf8 .\learning\xpath\xpath_practice_sina.py collected_af5904c15d1deebc.html
.\.venv\Scripts\python.exe -X utf8 .\learning\xpath\check_xpath_sina_batch.py
```

打开 `output/xpath_sina/collected_af5904c15d1deebc.json`，查 raw_blocks、cleaned_blocks、subheading_blocks、source_blocks 和 content_blocks。确认第 3/10/11 块在标题与阅读视图中，第 17 块只在原始与来源列表中。回答：17=13+3+1 为什么成立，而 17+16 为什么不能当成总块数？

### 操作 D：审核与反例（15 分钟）

在总报告找到中新网访谈页。查看作者字段、三条记者问题和四条图说；再打开 `xpath_corrections.py` 搜索 `move_to_author`。回答：为什么不能删除所有含“记者”的段落？当审核 stale 时程序会如何处理？

复习期间不覆盖 baseline、不改真实审核记录、不逐条重标全部区域。下一轮可在临时副本做反例，由助手准备，用户运行观察。

## 11. 报错排查与 Git

| 现象 | 优先检查 |
|---|---|
| cannot open file | 脚本新路径、工作目录、引号 |
| 找不到 JSON | 先运行生成脚本，确认成功与保存路径；检查脚本不负责生成数据 |
| 标题正确但正文 0 | 容器选择器、模板、静态文件是否有正文 |
| 有图但文字为空 | img 是否存在、alt 是否为空；不能只看 text_content |
| 中文变问号 | 管道编码与终端会话；优先直接运行 UTF-8 文件 |
| AssertionError | 看失败条件，判断输入变化、结果错误还是预期未同步 |
| PASS 但仍有语义问题 | 检查是否没有覆盖该问题，不能据此认定没问题 |

VS Code 的 M 表示已跟踪文件被修改，U 表示未跟踪。`git status` 查看状态，`git diff` 观察文本变化。commit 是本地版本，push 才把提交送到远端；GitHub 的提交时间通常是 commit 时间，不等于 push 时间。

```powershell
git status --short
git diff -- learning/xpath/xpath_practice_sina.py
git log -3 --oneline
```

这些命令只读。依赖环境与缓存无需提交；实验规则、结果证据和基准的保留策略与缓存不同。

## 12. 个人验收：用解释证明理解

### 应会写或能做小改动

- 选择指定 id 的容器、选择直接子 p、合并 p 与图说 XPath。
- 用 text_content、空白规范化和非空过滤生成文字列表。
- 从列表/字典读取 index、type、text，并用一个具体条件分类。

### 应会读并说明意图

- Path、sys.argv、循环、列表推导式、字典展开、JSON 保存。
- 完整类名匹配、来源条件、小标题启发式、分类分支顺序。
- 哈希、审核指纹、原文/XPath 证据、原始与派生结果。
- 回归断言如何保护正文顺序和防止误删。

### 应会判断与汇报

- 新问题属于容器、块选择、字段分类、页面保存还是审核过期。
- 明确区分结构检查、语义审核、回归检查和独立验证。
- 能举出漏图说、误提编辑信息、署名与访谈问题三个案例。
- 能说明当前项目没有训练模型、没有自动聚类，统一运行不会重新调用 AI。

不要求背诵整个项目或从零重写 72 项测试。合格标准是：看着实际网页和结果，能把“现象 -> 原因 -> 处理 -> 验证 -> 限制”讲完整。
