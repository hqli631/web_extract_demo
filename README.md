# Web Extract Demo

这是一个用于实习学习的网页正文抽取实验项目，包含网页读取、区域识别、原网页定位复核、人工标注、自动保存和结果评测。

## 项目目标

1. 从保存的 HTML 中提取标题和正文候选。
2. 区分正文、标题、来源、导航、广告、侧栏等区域。
3. 在原网页位置显示检测框，便于人工修正。
4. 将人工结果保存为 JSON，作为后续规则优化和模型分析的数据。

自动标签只是候选，最终结果以人工确认的标签为准。

## 目录结构

```text
samples/              六个本地网页和网页资源
extract.py            静态HTML抽取和初始分类
build_review.py       生成旧版文本复核入口
visual_review.html    原网页定位复核页面
region_overlay.js     注入网页内部的检测框和区域识别脚本
serve_review.py       本地HTTP服务和标注保存接口
start_review.ps1      启动复核服务
run.ps1               运行静态抽取流程
apply_review.py       根据CSV人工标签生成修正结果
evaluate.py           评估人工已确认区域，生成错例和规则建议
capture_page.js       在浏览器中重新保存当前渲染页面
collect_pages.py      定向采集静态 HTML
config/               采集配置和已启用的 XPath 规则
tests/                评测/采集单元测试和浏览器交互验证
output/               自动生成的JSON和HTML
reports/              CSV、评测报告和自动保存的标注
REVIEW_GUIDE.md       定位复核详细说明
```

## 环境

Windows、PowerShell、Python 3.10+、Chrome或Edge。项目脚本会优先使用 `.venv`，否则使用配置的Python解释器。换电脑时可安装依赖：

```powershell
python -m pip install beautifulsoup4 lxml
```

## 运行静态抽取

```powershell
cd "D:\codex project\web_extract_demo"
powershell.exe -NoProfile -ExecutionPolicy Bypass -File ".\run.ps1"
```

输出：

- `output/results.json`：页面标题、区域、自动标签和初始正文。
- `reports/region_review.csv`：旧版静态区域复核表。
- `output/review.html`：复核入口。

## 打开原网页定位复核

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File ".\start_review.ps1"
```

保持终端运行，打开 <http://127.0.0.1:8765/visual_review.html>。不要直接双击HTML；停止服务按 `Ctrl+C`。

选择网页后，点击原网页中的检测框或文字可定位右侧卡片；点击卡片可滚动回原位置。用下拉框修改标签；正文优先视图、父区域批量修改和 XPath 规则见下方新版流程。

## 标签说明

可用标签包括：

- `正文`：应进入正文抽取结果。
- `缺漏`：自动结果漏掉、人工确认应补回的正文。
- `标题`、`发布时间`、`来源`、`作者`：文章元信息。
- `导航`、`广告`、`相关推荐`、`侧栏`、`评论`、`功能工具`、`页脚版权`：通常排除出正文。
- `图片`、`音视频`：非纯文本内容。
- `其他杂质`、`待判断`：暂时无法确定的区域。

侧栏不一定都是广告，广告也不一定都在侧栏中；自动标签必须人工检查。

## 标注保存

修改标签后会自动保存到：

```text
reports/annotations.json
```

该文件按网页名称保存全部区域、标签、标题、元信息和修正后的正文，后续可直接提供给模型。按钮“导出本页修正”仍可下载一份JSON备份，通常在浏览器“下载”文件夹。

## 网页外观异常时重新保存

如果本地页面缺少动态样式、图片或组件，使用 `capture_page.js`：

1. 在Chrome或Edge打开外观正常的原网页并等待加载。
2. 打开 `capture_page.js`，复制全部内容。
3. 按 `Ctrl+Shift+J` 打开控制台，粘贴并回车执行。
4. 下载 `captured_page.html`，改名为原样本名并替换 `samples/` 中的文件。
5. 重启服务并刷新复核页面。

该脚本保存当前元素样式和开放Shadow DOM；图片、伪元素、canvas及跨域iframe仍可能无法完整保存。

## 旧版CSV流程

在 `reports/region_review.csv` 的 `manual_label` 列填写标签后运行：

```powershell
python .\apply_review.py
```

结果写入 `output/corrected_results.json`。CSV使用静态区域编号，与新版浏览器定位编号不同；新流程优先使用 `reports/annotations.json`。

## 评测

运行 `evaluate.py` 比较自动结果和人工结果，重点记录正文误判、正文漏提、重复抽取和不同网页模板下的规则表现。每次改规则后重新检查六个样本。

## GitHub同步

仓库：<https://github.com/hqli631/web_extract_demo>

```powershell
cd "D:\codex project\web_extract_demo"
git add .
git commit -m "Describe the change"
git push origin main
```

`.venv/`、`.deps/`和缓存不会提交。`.gitignore`也忽略 `samples/*_files/`；如果需要让其他电脑完整复现网页资源：

```powershell
git add -f samples/*_files
git commit -m "Include saved webpage assets"
git push origin main
```

## 常见问题

PowerShell禁止运行脚本时，使用 `powershell.exe -NoProfile -ExecutionPolicy Bypass -File ".\start_review.ps1"`。出现“请通过本地服务打开”时，不要双击文件，先启动服务再访问HTTP地址。标注没有保存时，确认服务终端仍在运行，并检查页面是否显示“已自动保存到 reports/annotations.json”。

## 新版：正文优先 → 批量修正 → 规则复用 → 评测 → 扩充数据

当前是启发式抽取和 XPath 规则系统，还没有训练机器学习模型。`evaluate.py` 现在实现了真实的评测；XPath 负责定位，人工修正提供真值，规则负责复用经验。

### 第一步：重启复核服务

在原服务终端按 `Ctrl+C`，然后运行：

```powershell
cd "D:\codex project\web_extract_demo"
powershell.exe -NoProfile -ExecutionPolicy Bypass -File ".\start_review.ps1"
```

浏览器访问 <http://127.0.0.1:8765/visual_review.html>，按 `Ctrl+F5` 更新脚本。

### 第二步：先复核正文，避免逐条处理整页

1. 选择样本，保持“只看正文主区”勾选。右侧展示正文预览与主区卡片，原页面只显示主区框。
2. 检查预览中是否有广告、推荐语、重复内容。点击有问题的文字定位卡片。
3. 展开“批量修正 / XPath 规则”，点击“选择上一层父区域”，可以反复向上选择。
4. 核对所选区域数量和卡片；点“整块保留正文”或“整块排除正文”。范围过大时重新点击单个段落，避免将整个网页一起标成正文。
5. 取消“只看正文主区”，从原文中找出缺漏段落，将标签改成“正文”或“缺漏”；将误提内容改成具体噪声类型。图片、标题、时间、来源不属于纯文本正文，应单独保留对应标签。
6. 检查当前列表后，点“确认当前列表标签”。只确认实际看过的内容；如要确认整页，先取消主区筛选再检查。
7. 点“保存本页”，确认显示“已保存”。普通标签修改也会自动保存。切换页面前会等待保存；刷新同一快照会恢复人工修正。

主区由文本量、链接比例、语义容器等启发式信号选择，并不保证总是正确。网页替换后会通过文件 SHA256 发现变化，不会套用旧快照标注。HTML 文件以外的资源变化和动态在线内容变化无法由这个哈希覆盖。

### 第三步：用 XPath 将一次修正变成可复用规则

1. 点击一个正文段落，再选择包含整篇正文的父区域。
2. 界面会生成 XPath 定位链。也可改成较稳定的属性 XPath，例如：
   ```json
   ["//*[@id='article-content']"]
   ```
3. 点“测试匹配”，检查匹配数量和列出的区域，确保没有捎带导航、广告。
4. 选择“保留正文”或“排除正文”，点“保存本页规则”。
5. 刷新页面，规则会自动运行；人工已确认的标签仍保留，卡片的“预测”展示规则输出，便于和真值比较。
6. 同模板复用时，在“应用到样本文件”中填写完整文件名，例如 `news_01.html,news_02.html`；先在每个目标样本上核对。不同模板不能直接假定共用同一个 XPath。

规则写入 `config/rules.json`，后面的规则覆盖前面的规则。可删除错误规则并刷新重新运行。默认生成的带位置序号 XPath 适合当前快照；跨页面优先采用稳定的 id、class 或语义属性。普通 XPath 不能穿过 Shadow DOM，因此定位链每段分别在 document 或对应 ShadowRoot 内执行。闭合 Shadow DOM、跨域 iframe 内部不在支持范围内。

### 第四步：自动比较人工真值和预测

另开一个终端（不要关服务终端）：

```powershell
cd "D:\codex project\web_extract_demo"
.\.venv\Scripts\python.exe .\evaluate.py
```

如果虚拟环境解释器不可用，可使用：

```powershell
& "C:\Users\35516\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe" .\evaluate.py
```

输出：

| 文件 | 用途 |
|---|---|
| `reports/evaluation.md` | baseline（初始预测）与 rules（规则后预测）的正文 Precision、Recall、F1、误提和漏提数量 |
| `reports/evaluation.json` | 各页面人工确认覆盖率、错例正文、真值、预测标签和 XPath |
| `reports/rule_candidates.json` | 由错例生成的单区域规则建议，尚未启用；复制定位链到界面测试后再保存 |
| `reports/annotations.json` | 人工标签、是否确认、快照指纹、原预测和规则预测、最终正文 |

Precision 低意味着正文混入杂质；Recall 低意味着漏提正文。没有人工真值时显示 N/A，不会凭空计算准确率。只评已确认且非“待判断”的区域，未检测出的区域仍需用原网页检查。改规则后刷新并保存，再运行评测，避免读到上一次的预测。

这一步实现“自动找差异、生成候选修正规则、复用已验证规则”，不是无人监督的模型训练。规则在同一页上修好后的分数只代表样本内效果。每种模板至少留 2 个页面只用于验证，不根据这些页面修改规则；上线前还需单独建立足量测试集。

### 第五步：定向采集更多网页

新增 `collect_pages.py` 和 `config/collection.json`。配置默认为空，避免在不知道目标网站时抓取无关内容。将实际可访问的列表页、文章页、RSS 或 sitemap URL 填入 `seeds`，将精确主机名填入 `allowed_domains`，`article_url_pattern` 用正则限制要保存的文章 URL。例如以下只是配置格式，需换成自己的网址：

```json
{
  "seeds": ["https://your-site.example/news/"],
  "allowed_domains": ["your-site.example"],
  "article_url_pattern": "/article/",
  "max_pages": 10,
  "max_fetches": 30,
  "max_depth": 1,
  "delay_seconds": 1,
  "min_text_chars": 200
}
```

启动采集前，确认本机 Python 已有 `beautifulsoup4`、`lxml`；如果依赖放在 `.deps`，先设置 `PYTHONPATH`。虚拟环境坏掉时用上面的完整解释器路径替换 Python 命令。

```powershell
$env:PYTHONPATH = ".deps"
.\.venv\Scripts\python.exe .\collect_pages.py --dry-run
.\.venv\Scripts\python.exe .\collect_pages.py --limit 5
```

`--dry-run` 只检查配置并打印范围，不联网验证页面。实际采集有允许域名、最大页数、最大请求次数、深度、请求间隔、超时、响应大小限制，读取 robots.txt，并对页面可见静态文本做哈希去重。列表/RSS/sitemap 可以发现下一层链接。重复执行会重新访问种子页发现新链接，相同内容不重复保存；下载失败记录在报告中。

| 文件 | 用途 |
|---|---|
| `samples/collected_*.html` | 新采集的 HTML，文件名来自来源 URL 哈希 |
| `reports/collection_manifest.json` | 来源 URL、域名、采集时间、内容哈希、快照哈希、字数 |
| `reports/collection_last_run.json` | 本次新增页面、访问尝试数和失败原因 |

**采集的是静态 HTML，不是完整离线网页包。** 相对资源通过原站 base URL 解析，仍依赖网络；采集器不执行 JavaScript，也不下载完整 CSS/图片，动态加载的正文可能缺失。遇到这种页面仍用 `capture_page.js` 保存浏览器渲染快照。数量增加不能解决外观资源缺失，也不能直接证明模型变好。

采集后刷新复核页，新文件自动出现在下拉框；如要生成静态抽取 JSON，再运行 `run.ps1`。注意 `run.ps1` 会重建旧 CSV，新版人工标注保存在独立的 annotations.json，不受影响。

建议先选 2–3 个可稳定访问的网站，每种模板采集 5–10 页，覆盖短文、长文、带图文、列表段落、有广告或推荐的文章。先用少量页面改规则，再在未参与改规则的页面检查；优先补充误提/漏提多的模板。保留来源，按网站或模板隔离训练/验证数据，不要把同一文章副本分到两边。

### 验证与当前边界

新增 Python 测试：

```powershell
$env:PYTHONPATH = ".deps"
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
```

`tests/test_pipeline.py` 用本地 HTTP 站点验证链接发现、robots、去重、重复种子访问和人工评测隔离。`tests/browser_review.cjs` 使用 Playwright + Chrome，在独立临时目录验证正文筛选、父区域批量修正、保存恢复、规则应用和 Shadow DOM 定位；运行前需安装 Playwright，或将现有安装位置配置到 `NODE_PATH`，并将 Python 路径设为 `PYTHON`。

网页复核在 DOM 可用后检测一次；长时间异步加载内容可能需要刷新。当前算法没有经过大规模准确率验证，也不执行自动模型参数训练。下一阶段应在积累真值后建立独立测试集，再决定继续优化规则还是训练区域分类模型。

复核服务冻结原网页的可执行脚本，防止原站脚本重写页面、插入广告或跳转导致区域编号漂移；原网页依赖 JavaScript 生成的样式/内容，应先用浏览器快照保存。检测脚本使用本地绝对地址，原站 base URL 不会再把检测框脚本引向外网。`tests/smoke_samples.cjs` 可只读检查实际样本是否返回区域与正文主区；它阻断外网请求，因此不用于证明离线外观与在线页面一致。

## 已配置的真实采集来源（2026-10-30）

`config/collection.json` 已填入你提供的头条文章、新浪文章、AI 湾帖子。去除了网址中的跟踪参数。默认深度为 0、最多请求 3 页，用于逐站诊断，不会直接大范围扩张。

试采发现：头条文章响应为 HTTP 200，但静态文本为空，不能当作成功正文；新浪 robots.txt 跳转到 `www.sina.com.cn`，被当前精确域名限制拦下，报告会记录跳转原因；AI 湾帖子能返回标题和正文。不要将这些不同情况混成“网络不可用”，也不要只凭 HTTP 200 就认为采集成功。

已另建 `config/collection_aicove.json`，只发现 `/forum/t/数字` 的帖子链接，避免把首页、登录、CSS 和脚本的访问耗尽在文章采集额度里。一次最多保存 5 个新内容快照、访问 15 个候选 URL、只发现一层，每次请求至少间隔 1 秒：

```powershell
cd "D:\codex project\web_extract_demo"
$env:PYTHONPATH = ".deps"
& "C:\Users\35516\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe" .\collect_pages.py --config .\config\collection_aicove.json --limit 5
```

刷新复核页后，选择 `collected_*.html`；文件与来源 URL 的对应关系在 `reports/collection_manifest.json`。`collection_last_run.json` 只代表最近一次采集，新增 `skipped` 字段说明空正文、重复内容、URL 筛选等跳过原因。完整三站试采请使用默认配置；不要把一次无新增直接当作失败，应先看是不是重复内容。

AI 湾帖子建议以楼主原帖正文为目标，标题、时间、作者单列；回复评论、侧栏热门、最新帖子、站点统计、投票/收藏/举报按钮不并入原帖正文。如果以后目标改为讨论串全文，需要独立的回复提取与评测口径。每站先人工确认少量主区，检查规则能否跨页生效，再增加采集数量。

头条静态空壳需在正常浏览器中确认文章确实加载后，用 `capture_page.js` 保存渲染快照；HTTP 200 并不能确定原因是客户端渲染还是站点拦截。新浪本轮没有抓取文章正文，不能据此断言文章本身不可访问；本轮保留域名限制，未扩大允许范围。

### 正文优先显示的修正

正文主容器与正文标签是两个独立概念。旧版只显示主容器内区域，会隐藏论坛列表其他行中已标为正文的内容；现已改为“正文优先（含区外正文）”，保留主区内区域，以及任何位置标为 `body`/`missing` 的区域。它只改变框和卡片筛选，不改变正文预览/保存内容的筛选。正文预览仍按最终正文标签拼接。

当前浏览器算法：检测可见 DOM 段落/列表项/表格单元等，去除父子重复；根据祖先 id/class 和标签识别导航、广告、侧栏、评论等，未命中时以 80 字符为正文候选阈值；聚合可见候选文本选择一个主容器，主区内短 p/li/pre/blockquote/h2/h3 从待判断提升为正文；依次应用 XPath 规则，最后恢复同快照人工真值。主容器评分为启发式，长列表上可能只选择第一行，不能以它作为正文完整性的保证。列表页卡片是摘要，不能等同链接文章全文；需要全文时需另外采集详情页。静态 extract.py 与浏览器复核流程使用不同的区域划分，旧 output/results.json 不代表新版复核结果。
