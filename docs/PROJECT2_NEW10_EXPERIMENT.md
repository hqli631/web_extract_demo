# 项目二：10 个新类型网页实验

## 本次任务与结论

2026-11-17 新下载 Books to Scrape 的 10 个图书商品详情页，与已有 5 个 Python Insider 发布博客不同。本站是抓取练习站，价格等数据为演示数据。因 HTTPS 连接中断，使用公开 HTTP 入口；未传账号、密钥，页面原始字节与 SHA256 已保存。

打开 [实验总览](../output/project2/books_experiment/index.html)，再进入 [27B 完整提取报告](../output/project2/books_product_27b/index.html)。总览列出全部 10 个网页的书名、原站、本地网页、角色和模型实验对比；完整报告保留正文、表格、规则、XPath、模型、调用次数、tokens 及排除记录。

结果：10/10 页标题、描述、价格、库存和 7 行信息表与快照 DOM 对得上；购物按钮及最近浏览推荐未混入提取块。每页 6 个块，分别为价格、库存、描述标题、描述段落、信息标题、表格。两个小标题的文字保留，但类型被标成 paragraph，10 页都存在这一问题。图片像素没有抽取，图片完整性保持 unknown。

这不是模型权重训练。这里由模型根据少量样本生成共享 XPath 配置，固定 Python 执行层在 CPU 上复用规则。

## 实际运行过程及意义

1. 下载首页前 10 个详情链接，抓取前按位置分配 3 个 generation、2 个 development_feedback、5 个 final_holdout。保存原 HTML、22 个样式/图片资源、下载回执和哈希，便于回放并保留原网页布局。
2. 只把生成页 DOM 摘要发给千问，要求输出统一 XPath 配置。这检验“少量样本生成可复用代码”，而非逐页调用模型直接输出正文。
3. 用生成页和开发页做独立结构检查，将错误反馈给模型，最多修复两次。开发页是调试材料，不能算独立测试。
4. 候选通过阻断性检查后，冻结规则及执行层哈希，再在 5 个留出页上执行。留出结果没有用于继续修改规则。
5. 冻结后进行专项 DOM 对照与当前对话 AI 语义复核，独立写入 review.json，不修改原 trace 或模型输出。保存的结果可用同一冻结规则重新执行并对照。

| 实验 | 模型 | API 次数 | 总 tokens | 结果 |
|---|---|---:|---:|---|
| books_product_v1 | qwen3.8-flash | 3 | 81443 | 首轮空元数据 XPath 不合协议；后续遗漏独立价格/库存块，开发未通过，留出未运行 |
| books_product_v2 | qwen3.8-flash | 3 | 81177 | 澄清任务后仍选中大容器再部分排除，三轮未有效修复，留出未运行 |
| books_product_27b | qwen3.8-27b | 1 | 15509 | 一轮生成可执行规则，冻结后执行全部 5 个留出页；自动状态 needs_review |

合计 7 次调用、178129 tokens，包含 API 返回的缓存 tokens，不能据此直接计算账单。27B 使用与第二次 Flash 相同的澄清任务，但执行错误提示进一步增加了源 XPath 诊断；这些不是完全同条件的模型排名实验。

本轮改进了检查器：执行错误、漏提等属于 failed；单靠结构不能证明的排除/元数据分类属于 needs_review；没有已知检查问题才是 pass。待审核可以冻结后做留出诊断，但最终状态仍保留 needs_review，不能自动升级成语义准确。

## 你现在可以亲手操作

在 VS Code 终端执行：

~~~powershell
Set-Location -LiteralPath 'D:/codex project/web_extract_demo'
Start-Process './output/project2/books_experiment/index.html'
~~~

先打开 Tipping the Velvet 的“本地网页”，找到商品描述与 Product Information 表格；再打开完整报告对应页面。对照价格、库存、描述结尾、UPC、表格行数和推荐栏。这次你不需要逐块重做标注，只需理解哪些证据支持结果、哪些证据不支持。

不调用 API，重放冻结规则并更新专项复核与报告：

~~~powershell
./.venv/Scripts/python.exe -X utf8 review_project2_books.py
~~~

只重建完整报告外观，不重新提取、不调用 API：

~~~powershell
./.venv/Scripts/python.exe -X utf8 project2_report.py output/project2/books_product_27b
~~~

需要亲自发起真实 API 重跑时，确保 QWEN_API_KEY 已在当前进程环境中配置，使用新的输出目录保护历史证据：

~~~powershell
./.venv/Scripts/python.exe -X utf8 project2_agent.py --provider dashscope --model qwen3.8-27b --task config/project2_books_product_v2.json --max-repairs 2 --output output/project2/books_my_run
~~~

程序最终打印 needs_review 时会返回非零退出码，因为尚未达到全部通过；结果与报告仍已生成。这既不是 API 失败，也不代表没有抽取内容。

## 文件用途

| 路径 | 用途 |
|---|---|
| collect_project2_books.py | 低频固定 10 页采集；已有 manifest 时拒绝覆盖 |
| data/project2/books_product_v1/site/ | 原始详情 HTML、CSS、封面等本地资源 |
| data/project2/books_product_v1/manifest.json | 固定 URL、角色、页面哈希；初版任务 |
| data/project2/books_product_v1/collection_receipt.json | 获取时间、robots.txt 404 记录及 22 个资源的回执 |
| config/project2_books_product_v1.json | 初版实验任务 |
| config/project2_books_product_v2.json | 依据开发页澄清的任务，复用相同快照与角色 |
| output/project2/books_product_v1/、books_product_v2/ | 两次 Flash 失败证据，未伪造留出成绩 |
| output/project2/books_product_27b/ | 真实成功生成记录、冻结规则、全部结果和专项复核 |
| review_project2_books.py | 冻结后的专项源对照、CPU 复放及总览生成，不给模型反馈 |

## 结果边界与下一步来源

- 这是一个站点同布局的 10 页实验，不是跨站或跨布局准确率。
- 原站有最近浏览组件，生成页中出现了一些其他目标书名和价格；5 个目标文档没有作为输入提供，但不能声称全部内容严格独立无交叉暴露。专项复核记录了 5 对相关链接。之后做严格评测，应在划分样本前隔离推荐组件，并重新采样新的测试页。
- 小标题选成 div 包装器，执行层将其归成 paragraph。下一轮可在开发集上改进分类或让模型选择 h2；不能修改后继续把这批已看过页面称为新测试。
- 模型规则含 div 位置索引，虽然当前 10 页可运行，结构改变后可能脆弱。应使用新的布局变体测试规则鲁棒性。
- 封面像素、CSS 隐藏状态和动态脚本未评估；不能声称完整视觉还原或图片内容完整。
- 本轮回归测试 243 项通过；测试通过只证明已覆盖工程行为，不能替代内容质量评估。
