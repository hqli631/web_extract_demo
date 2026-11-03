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
compare_extractors.py 比较当前启发式抽取器与 Trafilatura 的页面级结果
dom_evidence.py       将差异文本定位回原始快照 DOM，保留 Shadow DOM 定位边界
ai_review.py          导出 AI 审核任务、校验建议、生成独立正文修正候选
requirements.txt      Python 运行依赖
capture_page.js       在浏览器中重新保存当前渲染页面
collect_pages.py      定向采集静态 HTML
config/               采集配置和已启用的 XPath 规则
tests/                评测/采集单元测试和浏览器交互验证
output/               自动生成的JSON和HTML
reports/              CSV、评测报告和自动保存的标注
REVIEW_GUIDE.md       定位复核详细说明
```

## 一键同步到 GitHub

在 Windows 文件资源管理器中打开项目文件夹，双击 sync_github.bat。窗口会自动暂存所有未被 .gitignore 忽略的新增、修改和删除，创建带时间的提交，并将 main 推送到项目的 GitHub 仓库；没有新改动时仍会尝试推送已有提交。显示 Sync succeeded. 表示推送成功。同步前请确认项目目录中没有不想公开的文件，尤其是密码、令牌和私人数据。

脚本只接受当前分支为 main 且 origin 是本项目地址。它使用已有代理和登录配置，并为本次推送指定已验证可用的 OpenSSL 和 HTTP/1.1，不会修改全局设置；若失败，窗口会保留错误信息，提交成功但推送失败时重新双击即可重试。远程有本地没有的提交时，请先检查并处理分支差异，不要强制推送。

## 环境

Windows、PowerShell、Python 3.10+、Chrome或Edge。项目脚本会优先使用 `.venv`，否则使用配置的Python解释器。换电脑时可安装依赖：

```powershell
python -m pip install -r requirements.txt
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

### 新增：自动比较两种正文抽取器

`compare_extractors.py` 会将当前启发式提取器与 Trafilatura 的结果按页面比较，输出双方独有的段落候选。它不写入 `annotations.json`，也不会擅自把差异改成标签；两种算法意见一致仍可能同时漏掉正文。

在项目目录新建一个 PowerShell 终端，安装依赖到项目本地目录：

```powershell
cd "D:\codex project\web_extract_demo"
& "C:\Users\35516\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe" -m pip install --target .deps -r requirements.txt
$env:PYTHONPATH = ".deps"
& "C:\Users\35516\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe" .\compare_extractors.py --sample collected_855c0d89cc5b8f45.html
```

把最后一个文件名替换成 `samples` 里的 HTML 文件名。先从一个 AI 湾楼主帖子开始，再分别试一篇新闻和一篇博客。检查 `reports/extractor_comparison.md` 的页面摘要和双方独有段落；完整文本在同目录 JSON。当前独有段落是“可能误提”，基线独有段落是“可能漏提”，先比较候选区域和 DOM，再把确认后的模板规则加入规则配置。不要根据单页分歧直接改成全站通用规则。

如果安装依赖时报网络连接错误，先保留报错内容；采集代理设置与 Python 包下载代理是两套配置。安装成功后，`[ERROR] 缺少 Trafilatura` 不应再出现。

不带 `--sample` 运行可批量比较 `samples/*.html`。同时生成 `reports/extractor_comparison.html`：直接用浏览器打开此文件即可查看左右正文和可展开差异，不需要重启服务。服务仍在 8768 运行时也可访问 `http://127.0.0.1:8768/reports/extractor_comparison.html`。报告展示静态抽取流程，不改变 `visual_review.html` 的标签。

`empty_output` 仅表示至少一种算法没有输出正文，不表示原网页没有内容。浏览器快照中的正文可能位于声明式 Shadow DOM 的 `<template shadowrootmode>` 内；静态提取与 Trafilatura 对比现在都先在副本中展开这些模板，再解析文本。原样本不改动，普通未启用的 template 不参与提取。此处理不等同浏览器的 slot 分配或可见性计算，仍可能包含隐藏/重复内容，需要继续做结构过滤。

送入 Trafilatura 的 HTML 副本还会移除内联 `style`，避免浏览器捕获的巨量计算样式影响筛选；原快照和当前提取器输入不作同样的样式移除。两种输出字符数差异不能解释为准确率提升。

### 自动差异队列与 XPath 依据

每次运行比较脚本，同时生成 `reports/auto_review_queue.json`，对比页展开差异候选后可查看 DOM / XPath 定位依据：

- `possible_extra` / `exclude_candidate`：当前独有内容，可能需要排除。
- `possible_missing` / `include_candidate`：基线独有内容，可能需要保留。
- `unique`：找到一个包含该文本的候选块；`ambiguous`：匹配多处；`unresolved`：未定位。文本定位成功不等于标签判断正确。
- `locator`：原始快照定位链，跨 Shadow DOM 时分段。`source_xpath`：包含 template 的原始文件结构路径，不能直接当浏览器 Shadow DOM XPath 使用。
- `snapshot`、`expected_text`、`containers`：分别用于快照校验、匹配文本核验和祖先容器分析。最多列出三个匹配，不自动把长段模糊匹配到整页。
- 所有候选 `enabled=false`；普通差异项 `reviewed=false`，来源为 `algorithm_disagreement`。不写入人工真值，也不自动启用 XPath 规则。提取器为空时只生成诊断项，避免把另一方整篇文章误列为标签错误。

下一阶段可让 AI 读取队列中的文本和 DOM 证据返回建议，再检查快照、定位范围和跨页表现后启用规则。当前没有调用云端或本地 AI；页面内容仅作为待分析数据，不应作为模型执行指令。未定位、重复匹配与纯格式分歧仍需要后续处理。`visual_review.html` 仍使用原浏览器预测流程，本工具不会直接更新其标注。

### 已实现：对话 AI 审核结果导入与修正候选

新增 `ai_review.py` 支持离线审核闭环。首批 `blog_01.html` 的 12 条唯一定位差异由当前对话中的 AI 审核：8 条建议保留正文，4 条建议排除推广或侧栏。未调用外部 API，也不是程序独立运行模型。此样本内审核不构成独立准确率测试。

打开 `reports/ai_review.html` 查看 AI 决策、理由与按建议生成的正文候选。`reports/ai_review_response.json` 是该批原始建议，`ai_review_tasks.json` 是任务包，`ai_review_suggestions.json` 是经过本地校验的建议；`output/ai_corrected_results.json` 包含正文候选和各块是否实际改变。原始输出、样本、人工标注和规则配置均不覆盖。

需要重新生成这批任务或重新导入建议时：

```powershell
cd "D:\codex project\web_extract_demo"
$env:PYTHONPATH = ".deps"
& "C:\Users\35516\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe" .\ai_review.py prepare --limit 12
& "C:\Users\35516\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe" .\ai_review.py import --response .\reports\ai_review_response.json
```

任务 ID 由文件、快照、差异和证据生成。若重新采集/修改页面、改变差异队列，旧建议可能不再匹配，必须重新审核，不应强行套用。`prepare` 选取前 N 条唯一定位候选，不自动跳过先前审核过的条目。

可把任务包作为数据交给选定的模型服务，返回 `{"decisions":[{"id":"任务ID","decision":"body|noise|metadata|uncertain","reason":"依据"}]}` 后导入。`body` 保留正文，`noise` 排除，`metadata` 从纯正文中排除但保留在建议记录中，`uncertain` 不改变结果。只对原始快照中唯一定位、整块文本匹配、并能在静态区域中唯一对应的条目生成修正候选；局部、重复或未定位的结果不整块套用。未知 ID、重复 ID、源文件变化或伪造定位被拒绝，AI 不允许自带新 XPath。浏览器复核页尚未接入此候选，后续可统一输出并在新页面验证规则复用。

报告将空输出列为 `empty_output`、不足 100 字的结果列为 `short_output`，这些状态是排查提示，不代表短文章必然错误。相似度使用去空白后字符五元组的对称 Dice，范围为 0–1，不是准确率；标点、段落边界和基线漏提仍会造成分歧。JSON 记录快照哈希、双方正文和全部差异。静态提取器现在检查祖先导航/侧栏/页脚，排除文章容器之外的站点页头，同时保留文章内部 header 中的标题；浏览器检测流程尚未同步这些静态规则。

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

### 当前对话 AI 审核（2026-10-30）

已由当前对话中的 AI 阅读差异文本、DOM 容器与文章标题，填写 `reports/ai_review_response.json`；没有调用外部模型 API。它是保存下来的本轮审核判断，不是运行脚本就会自动产生的新 AI 判断。

本轮原始队列 150 条差异，其中 71 条能唯一定位，去重后为 69 条，已全部审核：36 条正文、29 条杂质、4 条元数据。68 条已应用到正文候选，实际改变 56 个区域；1 条因静态区域重复匹配未应用。另 79 条定位不明确或未找到的原始差异尚未审核修正。

| 文件 | 本轮用途 |
|---|---|
| `reports/ai_review.html` | 直接打开查看逐页诊断、修正候选、审核原因与 XPath；审核详情可展开 |
| `reports/ai_review_tasks.json` | 当前快照对应的待审核文本与定位证据 |
| `reports/ai_review_response.json` | 当前对话 AI 给出的标签、理由和页面诊断 |
| `reports/ai_review_suggestions.json` | 校验快照、任务指纹和 DOM 后的建议；不是人工真值 |
| `output/ai_corrected_results.json` | 修正候选及实际变更记录；不覆盖原始抽取结果 |
| `reports/article_context.json` | MSN 多文章快照中核实的局部文章标题，辅助说明混入来源 |

可重新校验并生成相同快照的本轮报告：

```powershell
cd "D:\codex project\web_extract_demo"
$env:PYTHONPATH = ".deps"
& "C:\Users\35516\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe" .\ai_review.py import --response .\reports\ai_review_response.json
```

更新样本后应先重新生成比较和任务，不能直接复用旧决策；旧响应绑定文件快照与任务指纹，校验不通过会拒绝应用。本轮报告不会直接修改 `visual_review.html` 的标签、人工标注或可复用 XPath 规则。

本轮发现：MSN 快照包含多篇独立文章，`article` 容器不代表全部属于目标文章；短正文被 80 字阈值漏掉；导航目录和话题列表被当成文章。`collected_911f560fdd154136.html` 移出标题后候选为空，是短原帖正文漏提未解决，不能据此认为原网页没内容。

下一步依次推进：先识别详情页/列表页并限定目标文章容器；再为短段落、原帖列表和 Shadow DOM 完善定位，解决剩余差异；将已审核结论归纳为候选 XPath 规则，在同模板的其他页面验证后再启用；最后才扩大定向采集。AI 建议保持独立来源，不用于冒充人工准确率或模型训练结果。

### 正文范围优化第二轮

本轮将审核发现落实到静态提取器 `extract.py`，正文范围选择集中在 `content_scope.py`：

- AI 湾使用 `#floor-1 .md-body:not(.signature-md)` 保留楼主原帖，排除签名、回复和侧栏；原帖内短段落、列表项一并保留。
- 新浪使用 `#artibody`；具有标准语义标记的页面优先使用 `[itemprop="articleBody"]`。
- MSN 多文章快照按 `consumption-page` 的 H1 与文档标题唯一匹配，提取该页内的 article；不能唯一匹配时暂缓，避免把多篇文章拼接起来。
- BBC 样本使用正文段落上的 `data-sticky-nav-anchor` 及正文小标题，避免依赖自动生成的 CSS 类名。
- 话题列表和重复的网站目录卡片标记为 `listing` / `not_article`，不把它们的空文章输出当作故障。
- 修复广告标识的误匹配：`continue-read-break` 不再因包含 `ad-` 而被排除。文章标题、责任编辑及部分声明单列为元数据。

当前 11 页重跑结果在 `reports/scope_v2/progress.html`，新版与 Trafilatura 的差异在同目录的 `extractor_comparison.html`，完整提取结果在 `output/scoped_results.json`。之前的 AI 审核报告、队列与人工标注保持不变。复现命令：

```powershell
$env:PYTHONPATH = ".deps"
& "C:\Users\35516\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe" .\compare_extractors.py --reports-dir .\reports\scope_v2
& "C:\Users\35516\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe" .\check_scope_regression.py
```

此前 AI 审核的 69 条开发样例全部符合本轮提取预期；公告原帖从仅提取 24 字标题改为 208 字正文。差异队列从 150 条减少到 27 条，其中包括列表页退出文章对比的影响。上述数字是开发回归与算法差异，不是独立准确率。新模板仍可能不适配，未知页面沿用旧长度规则并返回警告。

当前浏览器复核页和静态提取器仍使用不同算法。本轮改进通过上述新报告查看，刷新 `visual_review.html` 不会自动获得本轮范围判断。下一步应在未参与规则修改的同站新页面验证，并单独处理新版 27 条差异中的格式、推荐模块和真实漏提，再考虑同步浏览器检测。

### 第三轮：审核剩余差异并验证新页面

最新入口是 `reports/scope_v3/progress.html`，可查看全部现有页面的第三轮正文、每条差异的审核理由，以及 3 个新帖子上的验证结果。`output/scoped_results_v3.json` 是对应的开发样本提取结果。旧报告保留作为前后对照。

当前对话 AI 已审核第二轮剩余的 27 条差异，结果保存在 `reports/scope_v2/difference_audit.json`，绑定原队列哈希与样本快照：

- 一条真实误提：文章容器内的独立「专题：…」链接。规则仅排除链接独占的专题段落，保留叙述中讨论专题的文字。
- 四条格式差异：基线添加 `- ` 等列表前缀。比较时归一化，不修改保存的网页或原始正文；真正缺失的列表项仍报告差异。
- 剩余 22 条是有审核依据的算法分歧，包括基线漏正文、删改段落内容、拼入打赏控件、保留推荐入口或元数据。保留当前提取，不为追求两算法完全一致而补入杂质。

`build_iteration_report.py` 按同文件、同快照、同差异类型、同归一化文本对照已保存审核；新出现或已变更的内容会标为未审核，不会自动继承旧结论。它重放当前对话的判断，不会在后台调用 AI。输出中的“0 条无审核依据”只针对当前这 22 条差异，不表示整页已经没有错误。

另从既有页面链接中选择 `/forum/t/93`、`/forum/t/92`、`/forum/t/91`，与原 5 个开发帖子 URL 不重合。采集配置在 `config/collection_holdout.json`，快照、来源清单、提取代码哈希、当前对话 AI 的逐页审核分别保存在 `validation_holdout/` 下，未覆盖开发样本。帖子 92 首次请求超时，重试成功；初次和重试记录分别保留。三个新帖子均符合本轮 AI 对原帖边界的判断，正文和文内来源保留，返回/引用/举报/打赏/收藏控件排除。它们仅覆盖同一论坛模板，不能当作跨站准确率或人工真值。

重新生成最新报告：

```powershell
$env:PYTHONPATH = ".deps"
& "C:\Users\35516\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe" .\compare_extractors.py --reports-dir .\reports\scope_v3
& "C:\Users\35516\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe" .\build_iteration_report.py
```

新页面验证使用冻结的提取代码哈希和快照。代码变化后脚本会拒绝沿用旧“冻结验证”的说法，需要建立新一轮验证记录。下一阶段应扩展新闻站或不同论坛模板，并让浏览器复核页使用同一份正文范围结果，以减少两套算法造成的展示差异。

### 正文优先显示的修正

正文主容器与正文标签是两个独立概念。旧版只显示主容器内区域，会隐藏论坛列表其他行中已标为正文的内容；现已改为“正文优先（含区外正文）”，保留主区内区域，以及任何位置标为 `body`/`missing` 的区域。它只改变框和卡片筛选，不改变正文预览/保存内容的筛选。正文预览仍按最终正文标签拼接。

当前浏览器正文判断已统一（2026-10-30）：`GET /api/extraction/<文件名>` 直接调用 `extract.py`，使用 `content_scope.py` 选择目标正文。正文高亮、预览和导出以这份结果的文本及顺序为起点，不再在浏览器内通过80字阈值或主容器评分另判正文。`review_source.py` 在内存副本中为每个原始 DOM 节点赋予稳定 ID，让静态区域映射回快照，包括开放 Shadow DOM；不改写样本文件。框显示受页面可见性限制：隐藏节点标记 `hidden`，不可定位（例如关闭的 Shadow DOM）标记 `unmapped`，正文仍留在预览和导出中，不假装它们不存在。

浏览器仍为其他可见区域细分广告、导航、侧栏等标签，但不能因此新增正文。默认“正文优先”展示共享预测的正文和最终被保留的区域；取消勾选后可查看其他区域。列表页 `listing` 的正文为空属于正常结果；应采集其链接指向的详情页。

应用顺序是：共享静态预测 → 本文件的 XPath 规则（后写优先）→ 同快照、同定位链且同文本的已确认修正。`predicted_label` 保留规则后的预测，`label` 是最终标注。右侧预览及导出使用最终标注，因此应用规则或人工修正后可以与基础提取结果不同。修正继续自动保存至 `reports/annotations.json`；这些浏览器修正不会自动覆盖基础 `output/results.json`，训练与批量规则发布仍需独立验证。未重新运行提取脚本的历史报告也不会自动更新。

运行新版界面：

```powershell
cd "D:\codex project\web_extract_demo"
powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\start_review.ps1 -Port 8769
```

打开本次终端打印的 `Open http://127.0.0.1:端口/visual_review.html`。端口被占用时程序会另选端口；必须打开新地址，单纯刷新旧服务不会加载新的 Python 接口。接口不可用时页面明确报错，不会退回另一套正文判断。

本轮验证：`tests/test_review_source.py` 检查静态区域和快照身份一致、重复段落不合并、源文件不变；`tests/browser_review.cjs` 检查共享正文一致、隐藏/不可定位正文、Shadow DOM、XPath 规则、保存恢复和接口失败；`tests/smoke_samples.cjs` 在禁止外部资源的浏览器中逐页检查现有样本，输出 `reports/browser_sync/regression.json`。这些是功能与一致性回归，不是正文准确率或视觉还原度评测。

下一步优先扩展一个新闻模板的详情页样本，给新样本保存快照与 AI 审核依据，再比较漏提/误提并验证可复用规则。旧 `validation_holdout` 保持冻结；本轮修改代码后不能沿用旧代码哈希作为新版本的独立验证结论。

### 新闻站点扩展与可重复回归（2026-10-30）

已根据 `config/collection_news.json` 从中新网国内频道、新浪财经首页发现并采集各3篇详情页，遵循站点 robots、域名白名单、请求间隔及抓取上限。原始快照、来源 URL、采集日志、改进前后对比均位于 `news_validation/`；通过审核预期检查的6页已复制到主项目 `samples/`，总计17页，可在复核页下拉框中切换。

当前对话 AI 阅读原始正文与35条算法差异，保存 `news_validation/reports/ai_audit.json` 和 `difference_audit.json`。前者记录完整正文段落、顺序、排除内容与样本哈希；后者记录逐条分歧的判定依据。它们是本轮 AI 开发预期，不是人工真值、训练结果或独立测试集。后续运行不会自动生成新的 AI 审核判断；新页面标记为 `unreviewed`，变更快照标记为 `stale`，均禁止发布。

本轮修复：中新网使用唯一 `.left_zw` 容器及标题中的站点标识限定正文，排除页脚版权并保留短提示、反馈步骤、截止日期；独立记者署名及括号内“文章来源”单列，不把叙述句里提及记者的内容误删。新浪正文内的股票链接和短小标题保持完整；Trafilatura 的遗漏及推广混入不作为真值照抄。

重跑保存样本的比较和审核回归：

```powershell
cd "D:\codex project\web_extract_demo"
$env:PYTHONPATH = ".deps"
& "C:\Users\35516\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe" .\run_news_validation.py
```

加 `--collect` 会按配置尝试发现新文章，执行去重并保存来源；新文章需要新审核记录后才能通过检查。加 `--publish` 只会将全部匹配现有审核预期的批次加入主项目，拒绝覆盖不同内容的同名文件。

查看 `news_validation/reports/progress.html` 可展开每页正文及回归细节，并进入改进前后对比；`regression.json` 保存6页的逐页结果，`legacy_regression.json` 保存此前69条开发样例的回归结果。重新启动复核服务才会载入新的 Python 正文规则。
# 最新开发回归入口

运行现有样本测试并打开报告：

~~~powershell
cd 'D:\codex project\web_extract_demo'
powershell.exe -NoProfile -ExecutionPolicy Bypass -File '.\test_project.ps1' -OpenReport
~~~

报告位于 reports/development_cases/progress.html，数据位于同目录 results.json。
该入口运行功能测试，然后复用已审核页面检查修改效果，不联网、不代表独立验证准确率。
正文末尾连续的制作署名会作为元数据排除，正文中间出现的同类文本保留。
提取结果新增 body_images、needs_ocr_candidate、content_completeness；正文图片尚未经过 OCR。
needs_ocr_candidate 使用“至少三张图片且正文少于300字”的启发式，只提示风险，不证明图片一定包含正文。

旧冻结验证报告仍在 validation_blind/reports/progress.html，保留修改前结论。
提取代码已变化，新冻结批次使用以下命令；旧批次不能直接重新生成：

~~~powershell
$env:PYTHONPATH='.deps'
& 'C:\Users\35516\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe' run_blind_validation.py --batch validation_blind_round2 --collect
~~~

下一步是补充未参与本次规则调整的新文章做独立验证，以及评估图片文字识别。

## 图片正文 OCR 与合成候选

可选依赖与运行方式（在项目目录执行）：

~~~powershell
.\.venv\Scripts\python.exe -m pip install -r requirements-ocr.txt
.\.venv\Scripts\python.exe ocr_validation_images.py --profile chinanews_quote_card_v1
$env:PYTHONPATH = '.deps'
.\.venv\Scripts\python.exe compose_ocr_candidate.py
~~~

默认读取第二批已下载的图片；其他批次可传入 --batch 和 --file。ocr_validation_images.py 保留逐行坐标、置信度与原图画框；ocr_layout.py 中的可选版式规则仅适用于匹配的中新网引语卡片，默认不启用。未匹配图片保留待判断。

compose_ocr_candidate.py 按网页快照顺序交错排列 DOM 文字与 OCR 正文候选，检查快照、图片来源、顺序和哈希，生成独立的 *_combined_candidate.json 和 HTML。默认报告在 validation_blind_round2/reports/ 下。合成结果尚未校对，不改写 output/results.json，也不改变独立验证通过率；存在缺图、过期结果或无法确定顺序时拒绝或标为 blocked。

## XPath 实验的当前入口

这部分用于学习“抽取 -> 审核 -> 受限修正 -> 回归”的工程闭环，不会把 AI 意见冒充人工真值。运行命令：

    .\.venv\Scripts\python.exe -X utf8 .\xpath_batch.py

报告在 output/xpath_practice/summary.html，结构化结果在同目录的 results.json。报告同时显示原始提取块、结构检查、当前对话 AI 的语义审核、清理后的正文和自动署名候选。原始结果仍用于回归基准，清理结果是派生投影。

当前三篇练习页的原始块数为 7、27、34。已确认的两条独立署名分别进入作者字段，生成 7、26、33 个正文/图说块；访谈中的“中新社记者：……”问题、图说和受访者简介保持不变。候选扫描器只减少审核范围，不能单独决定删除或移动。

完整检查命令：

    powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\test_project.ps1

项目当前自动化测试合计 70 项，包含真实练习样本的署名修正、原始结果不变、访谈问题保留、图说保留和冻结基准一致性检查。测试通过表示这些已编码行为及已保存样本回归一致，不表示对所有网页的准确率。岗位学习的分步实操与验收清单见 [INTERNSHIP_PRACTICUM.md](INTERNSHIP_PRACTICUM.md)。
