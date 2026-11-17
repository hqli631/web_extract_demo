# 用项目一改进项目二的固定执行层

2026-11-17。参考源为独立项目 web-body-extractor；已阅读其 README、extractor.py、四种布局规则、抽取测试和 Trafilatura 对照实现。本轮不改项目一，复制参考样例后不依赖它的运行目录。底层对照不调用模型；最后另用新引擎进行一次真实API复验。

## 对照后采用的改进

| 项目一能力 | 项目二原有问题 | 本轮落地 |
|---|---|---|
| 原始节点定位、清洗副本 | 直接删除原DOM节点可能改变位置XPath | 原始DOM不修改，clean_text在副本上去脚本/样式/导航锚点，原始节点生成XPath |
| 细分页面信息 | 只识别少数作者链接和date | 新增可选metadata_fields，支持author/editor/source/published_at/production_credit与meta content证据 |
| 文档内容类型 | pre/li/dt/dd等缺少类型或漏检查 | 增加code_block/list_item/list/definition_term/definition_description/footnote，代码块保留换行缩进 |
| 旧博客br/text/tail | 只按p等元素选块，无法表达旧博客分段 | 新增显式block_mode=br_segments，保留容器XPath、段索引和分段证据；表格/代码/图片拒绝扁平化 |
| 规则与证据检查分开 | 主要依赖生成时正确选择节点 | 增加独立validate_result，对照原始字节验证文字、属性、顺序、分段与表格行列 |
| 不按文件名识别布局 | 摘要和评测都局限article | 摘要默认支持article或main，也可用任务自有scope；未知/歧义结构明确失败 |
| 回归对照 | 已有成功数字无法揭示执行层变化 | 引入3个曝光样例与项目一输出，记录正文文字及顺序差异，不当作新泛化测试 |

项目二仍由Agent生成XPath规则；没有把项目一站点规则替换为Agent输出。参考清单 config/project2_foundation_reference.json 中的规则是人工参考配方，有明确标签和来源文件哈希。参考HTML与结果已复制到本仓库，复验不依赖旁边的项目一目录。

## 新协议（兼容旧五字段）

五个必填XPath字段保持不变。可选新增：

~~~json
{
  "metadata_fields": {
    "author": "//meta[@property='article:author']",
    "editor": "//*[@class='article-editor']",
    "source": "//*[@class='source']",
    "published_at": "//time"
  },
  "block_mode": "elements"
}
~~~

示例仅解释协议，真实class匹配通常应使用class token，不应把单个站点表达式视为通用规则。metadata_fields选择元素而非属性；meta节点由固定执行器读取content，并保留attribute证据。未能确定类别时保留metadata。type继续兼容项目二，新增相同值的kind便于和项目一对照；date统一为published_at。

对于非article布局，在任务JSON中设置：

~~~json
{
  "summary_scope_xpath": "//div[@id='artibody']",
  "evaluation_scope_xpath": "//div[@id='artibody']"
}
~~~

summary_scope_xpath用于生成/开发样本摘要；evaluation_scope_xpath用于独立检查。后者由任务登记，不接受模型缩小范围以隐藏漏提。最终测试内容仍不进入提示。摘要依然有28000字符上限，超限会报错，不静默截断；长文档尚需进一步摘要策略。

## 实际对照结果

| 已曝光样例 | 项目一正文块 | 项目二固定执行层 | 文字与顺序 |
|---|---:|---:|---|
| sina_01 | 43 | 43 | 一致 |
| chinanews_03 | 33 | 33 | 一致 |
| pydoc_interpreter | 32 | 32 | 一致 |

正文比较忽略空白格式，保留块顺序；代码原文另以证据检查验证。元数据不是正文，不纳入正文块差异。新浪4个、中新网2个分类/排除判断保留待审核，Python文档0个；这些不是正文漏提。参考规则与参考输出一致也不能证明语义准确率。

旧真实flash规则在新引擎上的5页复验仍是21/19/19/21/33块，没有新增结构问题，作者和日期类型变为author/published_at。新检查还发现旧mock修复配方未选择开发页的4个pre代码块；本轮修正mock配方并增加检查。历史API候选原本已选择pre，未受此遗漏影响。旧报告和旧引擎副本保留，不回写成新的测量结果。

新执行器真实API复验：output/project2/live_flash_foundation_v2/index.html，qwen3.8-flash单次生成通过，6972输入+154输出=7126 tokens；5页仍为21/19/19/21/33块。此次是已曝光同任务复验，不作为新的独立泛化成绩。新的规则、提示、全文、元数据和执行器副本单独保存。

## 查看与亲手运行

先打开 output/project2/foundation_v2_final/index.html 看三个样例对照；查看各页JSON中的blocks、metadata和issues。再打开 output/project2/foundation_agent_v2/index.html，观察新引擎的mock反馈和修复流程。这次mock仍不是千问调用。

~~~powershell
Set-Location 'D:/codex project/web_extract_demo'
./.venv/Scripts/python.exe -X utf8 project2_foundation_check.py --output output/project2/my_foundation_01
Start-Process './output/project2/my_foundation_01/index.html'
./.venv/Scripts/python.exe -X utf8 project2_agent.py --provider mock --output output/project2/my_agent_v2_01
~~~

也可直接复用参考配方（无需API），先将config中某页的rules保存为独立JSON，再给project2_extract.py传入--rules与--scope-xpath。参考配方不会自动转为模型规则。

学习时重点查看：为什么原DOM不能直接删节点；为什么署名归metadata而访谈问题仍属正文；为什么pre不能压成一行；为什么有正文的父节点不能因某个子段落被选中就算全覆盖；为什么评估scope不能等同模型选中的container。

## 验证与后续边界

本轮项目二22项测试、全仓236项测试通过。10项新增控制覆盖原始位置、代码缩进、元数据属性、采访问题、br尾文本与段序、独立scope、父节点自有文字、伪装metadata、篡改顺序/表格及3页真实参考回归。

Trafilatura是项目一有价值的外部诊断工具，但不是gold。本轮未额外添加依赖或把外部差异分数当作Agent奖励。下一步可以把它作为独立差异诊断接入更多布局；需要语义审核的分类、排除仍保持pending。部分块内清洗、动态渲染、OCR、任意布局自动适配均未宣称实现。
