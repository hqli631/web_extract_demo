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
evaluate.py           评估抽取结果
capture_page.js       在浏览器中重新保存当前渲染页面
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

选择网页后，点击原网页中的检测框或文字可定位右侧卡片；点击卡片可滚动回原位置。用下拉框修改标签，使用“全宽对照”检查网页布局。

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
