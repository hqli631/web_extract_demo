# 项目二：单 Agent 代码生成提取器

2026-11-17新增：[参考项目一的底层改进说明](PROJECT2_FOUNDATION_UPGRADE.md)。当前协议兼容五个必填字段，并增加metadata_fields和block_mode两个可选字段；新增独立summary/evaluation scope、原始DOM证据验证及丰富正文类型。旧报告保留旧引擎，当前参考对照见output/project2/foundation_v2_final/index.html。

本项目实现岗位 V6 思路的小型闭环：2篇同布局网页 → 千问生成 XPath → 固定 Python 执行器生成可复用模块 → CPU批量执行 → 根据实际检查反馈有限修复 → 冻结后验证。

## 先看已经完成的真实效果

- [正常生成报告](../output/project2/live_flash_final/index.html)：真实 qwen3.8-flash 调用，首轮规则通过。
- [真实修复报告](../output/project2/live_repair_v4/index.html)：人为设置仅取段落的漏提规则，程序发现小标题/列表遗漏，千问依据反馈修复。受控实验，不计作新泛化结果。
- [完成记录与限制](PROJECT2_COMPLETION.md)。GitHub通常显示HTML源码，克隆后用浏览器打开本地报告。

报告展示原网页URL、本地HTML快照、每篇完整标题/正文/作者/日期、块XPath、本轮规则、反馈及token用量。快照不包含所有站点资源，不能保证原网页视觉还原。

## 安装与离线学习

在项目目录执行；已有虚拟环境可跳过前两条安装命令：

~~~powershell
Set-Location 'D:/codex project/web_extract_demo'
py -m venv .venv
./.venv/Scripts/python.exe -m pip install -r requirements-project2.txt
./.venv/Scripts/python.exe -X utf8 project2_agent.py --provider mock --output output/project2/my_mock_01
Start-Process './output/project2/my_mock_01/index.html'
~~~

默认任务是 config/project2_python_blog.json。mock 首轮只取段落，第二轮补齐小标题和列表，实际覆盖检查触发反馈。它不调用模型、不收费。输出目录不可复用，以免覆盖旧实验；再次运行换成 my_mock_02 等新名称。

## 真实千问调用

先在本机用户环境变量配置 QWEN_API_KEY，重新打开终端或应用使其继承。不要把值写入代码、命令示例、截图或Git。已继承的终端可以直接运行：

~~~powershell
./.venv/Scripts/python.exe -X utf8 project2_agent.py --provider dashscope --model qwen3.8-flash --max-repairs 2 --output output/project2/my_live_01
~~~

密钥优先级：QWEN_API_KEY → DASHSCOPE_API_KEY。模型优先级：--model → PROJECT2_MODEL → QWEN_MODEL → qwen3.8-flash。支持用户推荐的 qwen3.8-flash、qwen3.8-27b、qwen4-max；后三者均已做连通性检查，完整工作流验收使用flash。

默认官方北京兼容接口；QWEN_BASE_URL仅允许北京或国际官方DashScope completions地址。单次最多1500输出tokens，默认90秒网络超时，最多3次修复；网络失败不自动重试，记录一次失败尝试并停止。此前旧版大段HTML输入曾超时，见 api_connectivity.json；客户端超时不能证明服务端没有计费。

## 不再调用API，直接复用代码

~~~powershell
./.venv/Scripts/python.exe -X utf8 project2_extract.py 'data/project2/python_blog/page_*.html' --rules output/project2/live_flash_final/rules.json --output output/project2/my_cpu_01
~~~

该命令仅在CPU执行规则。每篇结果保存为JSON，summary.json保留汇总、检查与失败信息。也可导入报告目录的 extractor.py 并调用 extract(html_bytes)，该模块依赖同目录保存的 project2_engine.py；直接导入不提供进程超时，批量入口提供每页8秒超时。

## 受控修复实验

~~~powershell
./.venv/Scripts/python.exe -X utf8 project2_agent.py --provider dashscope --initial-rules config/project2_ablation.json --output output/project2/my_repair_01
~~~

初始规则故意只有 .//p，程序会提出 uncovered_article_node 证据。你观察首轮与修复后的 block_xpath、issues 和正文块数即可，不需要逐个手工改代码。此命令会调用API。这个实验复用已曝光的任务，不是新的独立测试。

## 各文件负责什么

| 文件 | 作用 |
|---|---|
| project2_agent.py | 单Agent编排、官方API适配、有限反馈循环、候选冻结、报告 |
| project2_engine.py | 五字段XPath校验、lxml提取、结构覆盖探针、Python模块导出 |
| project2_worker.py | 固定子进程，接收规则数据与原始HTML字节，执行并返回结果 |
| project2_extract.py | 已生成规则的CPU批量复用入口 |
| config/project2_python_blog.json | 2生成/1开发/2最终测试任务及原始HTML哈希 |
| config/project2_ablation.json | 受控漏提实验的初始规则 |
| data/project2/python_blog/ | 5份HTML快照及来源清单 |
| output/project2/live_flash_final/ | 正式真实生成证据、代码、规则、逐页全文 |
| output/project2/live_repair_v4/ | 真实API修复的前后规则、反馈和全文 |
| output/project2/cpu_reuse_final/ | 冻结规则在5篇上的CPU复用记录 |
| tests/test_project2_agent.py | 12项新入口及边界测试 |

历史 project2_task.json、output/project2/final 是早期新浪/mock实验，不是当前正式入口。LoRA、GRPO、RSI资料为历史拓展，不影响本项目二基本功能验收。

## 理解本次学习的三个重点

1. 神经侧与符号侧分工：模型生成规则只需少数调用，同一份代码可以在CPU上重复使用。CPU仍有成本，不能称为零成本。
2. 修复必须有证据：本项目给出漏选节点XPath和文字预览。没有发现问题就停止，不为演示而强迫模型改规则。
3. 开发与测试分开：最终测试页内容不进入提示或修复；冻结后才执行。复验相同页面不是新的独立泛化实验。结构检查通过也不等于正文语义100%正确。

## 执行与评估边界

模型仅返回五个字符串字段的JSON，不提供可执行Python；Python由可信模板和固定解释器生成。不执行模型eval/exec。每页HTML限制2MB、XPath各1000字符、子进程超时8秒。这是受限解释与超时边界，没有操作系统级内存/网络隔离；不要对外宣称为恶意代码沙箱。

当前DOM摘要和独立检查针对单一 semantic article 布局，未覆盖任意网页、动态渲染或OCR。结构探针检查段落/列表/标题/表格/图说的节点覆盖和header/nav/footer混入。未知杂质语义、图片文字和完整性不自动判定；排除节点保留 exclusion_requires_review，不允许靠任意排除绕过检查。选中块内的部分排除暂不支持，明确报错要求改选更细节点。

验证命令：

~~~powershell
./.venv/Scripts/python.exe -X utf8 -m unittest discover -s tests -p test_project2_agent.py -v
$env:PYTHONPATH='.;.deps'
./.venv/Scripts/python.exe -X utf8 -m unittest discover -s tests
~~~
