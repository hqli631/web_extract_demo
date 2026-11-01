# 自动抽取器对比

当前启发式抽取器与 Trafilatura 的差异候选。两者一致不等于正确，分歧也不自动代表错误。

| 页面 | 当前字符数 | 基线字符数 | 相似度估计 | 当前独有段落 | 基线独有段落 |
|---|---:|---:|---:|---:|---:|
| blog_01.html | 3914 | 3388 | 87.4% | 9 | 8 |
| blog_02.html | 1744 | 1724 | 100.0% | 0 | 0 |
| collected_07299d33c58922ca.html | 278 | 292 | 98.1% | 0 | 1 |
| collected_47c9a44f1ccc3dfa.html | 290 | 304 | 98.1% | 0 | 1 |
| collected_5b4a5a3b46bc6f7f.html | 308 | 322 | 98.2% | 0 | 1 |
| collected_855c0d89cc5b8f45.html | 312 | 326 | 98.2% | 0 | 1 |
| collected_911f560fdd154136.html | 204 | 219 | 90.3% | 0 | 5 |
| forum_01.html | 0 | 159 | 0.0% | 0 | 2 |
| forum_02.html | 0 | 2169 | 0.0% | 0 | 30 |
| news_01.html | 3047 | 3077 | 99.5% | 0 | 1 |
| news_02.html | 857 | 855 | 100.0% | 0 | 0 |

相似度采用去空白后的字符五元组 Dice；它不是准确率。差异按单向文本包含判断，段落格式和标点差异仍可能产生分歧。

## blog_01.html（disagreement）


### blog_01.html：当前抽取独有

- 专题：a股已体现性价比 长期配置价值凸显
- 10月26日，物理ai概念延续强势， 宇树科技 （688836.sh）收盘涨7.69%报672元，总市值达2718亿元。自10月16日盘中低点407.01元至26日收盘，宇树科技在7个交易日内累计上涨65.1%。
- 行情的触发点在10月下旬的两场会议。10月21日，英伟达ceo黄仁勋在柏林gtc大会上称“下一波浪潮是物理ai”，并宣布扩容isaac 机器人 开发平台；10月22日，2026世界物理ai大会暨宇树合作伙伴生态大会在杭州举行，宇树科技创始人王兴兴在演讲中表示，随着gpt-6发布，“物理ai已经看到被击穿的苗头，很可能最近1到2年或者2到3年”。
- 21世纪经济报道记者根据wind收录的电话会议纪要统计，10月19日至25日这一周内，可查到纪要的物理ai及人形机器人相关电话会至少有18场，覆盖16家券商研究所， 东吴证券 更是有计算机、传媒互联网行业两场电话会。
- 从参会阵容看，这轮路演大致分为三类。一类是对话产业方，直接请上市公司或数据服务商高管上会。以 海天瑞声 （688787.sh）为对象的有三场，涉及 国泰海通 计算机、东吴计算机、华创计算机，均由公司董秘出席；开源证券计算机团队请到 当虹科技 （688039.sh）代表； 国海证券 的具身智能研究团队请到 慈星股份 （维权） （300307.sz）董秘与数采专家同场； 国联民生 计算机则把仙工智能（06106.hk）相关人员请上会议。
- 另有 4 段，见 JSON 报告。

### blog_01.html：基线抽取独有

- 从参会阵容看，这轮路演大致分为三类。一类是对话产业方，直接请上市公司或数据服务商高管上会。以海天瑞声国泰海通当虹科技国海证券慈星股份（维权）（300307.sz）董秘与数采专家同场；国联民生
- （声明：文章内容仅供参考，不构成投资建议。投资者据此操作，风险自担。）
- 责任编辑：石秀珍 sf183
- 新浪财经声明：此消息系转载自合作媒体，新浪财经登载此文出于传递更多信息之目的，文章内容仅供参考，不构成投资建议。
- app专享直播
- 另有 3 段，见 JSON 报告。
## blog_02.html（agreement）

## collected_07299d33c58922ca.html（disagreement）


### collected_07299d33c58922ca.html：基线抽取独有

- - the sleep framework: a new way for llms to retain knowledge in continual learning google research 提出在持续学习中引入「睡眠阶段」，使大语言模型能持续整合新事实、增强推理，同时缓解灾难性遗忘或静态知识截止问题。现有模型部署后基本静态，而直接持续更新参数会严重损害旧任务表现，仅依赖上下文学习又会在会话结束后遗忘信息，该框架试图在两极之间提供新路径。 站内资讯页：/news/20
## collected_47c9a44f1ccc3dfa.html（disagreement）


### collected_47c9a44f1ccc3dfa.html：基线抽取独有

- - microsoft just shared azure’s actual revenue in dollars: $33.2 billion 微软此前从未以美元金额直接披露 azure 的单季收入，通常仅分享增长百分比或模糊的里程碑描述。在周三发布的财报中，微软首次披露 azure 在 7 至 9 月季度实现营收 332 亿美元，同比增长 48%。该披露使投资者能够将 azure 的业绩与亚马逊 aws 和谷歌云的季度美元收入进行直接对比。 参考合并： techcrunc
## collected_5b4a5a3b46bc6f7f.html（disagreement）


### collected_5b4a5a3b46bc6f7f.html：基线抽取独有

- - gemini 4 carbon: our next frontier model google deepmind 宣布推出新一代旗舰模型 gemini 4 carbon，主打前沿网络安全与长程智能体任务能力。该模型在最新 artificial analysis intelligence index v5.0 榜单中拿下 59 分登顶全球第一，并在 sec-bench pro、exploitgym 及 cwe-bench 等安全基准上均取得领先。目前该模型仅向选定的网络安全
## collected_855c0d89cc5b8f45.html（disagreement）


### collected_855c0d89cc5b8f45.html：基线抽取独有

- - nvidia nemotron 3.5 transcribe and granary v2: intelligent multilingual transcription you can prompt and adapt 英伟达正式在 hugging face 与 modelscope 开源开放权重语音模型 nemotron 3.5 transcribe。该模型将语音转录、说话人识别、翻译与音频问答统一在单一检查点内，支持 40 种语言转录与 31 种语言对英语的双向翻译
## collected_911f560fdd154136.html（disagreement）


### collected_911f560fdd154136.html：基线抽取独有

- - 本次更新：论坛的点赞、点踩（亮/灭）与打赏已移除 lv.1 等级门槛——注册即可使用。
- - 频率限制依然存在（点赞 30 次/分、100 次/日；新注册账号 30 次/日），滥用会被记录并按论坛规则处理；
- - 打赏仍消耗你自己的积分：最低 1 分、同一帖子每人一次、平台抽成 10%，被打赏所得计入每日归集上限；
- - 积分不足仍无法打赏——本调整只是去掉「等级门槛」，不改变积分账本。
- 其余规则见「文档 → 论坛规则」。 本帖收到打赏打赏 0
## forum_01.html（not_article）


### forum_01.html：基线抽取独有

- 魔塔社区（modelscope）
- 魔塔社区，即modelscope，是一个开源的模型魔塔社区（modelscope）即服务共享平台，旨在为泛ai开发者提供灵活、易用、低成本的一站式模型服务产品。这个社区汇集了业界最新最热的模型、数据集以及创空间应用，提供简洁高效的模型服务及算力平台，支持模型微调、部署、推理及应用搭建。
## forum_02.html（not_article）


### forum_02.html：基线抽取独有

- | 免费ai生图做视频工具分享！完全免费的ai生图视频工具 最近找了一些ai免费生图做视频工具，目前都可以正常使用，效果也不错，下面就为大家盘点一下！ 免费ai生图、生视频，一站式ai短剧漫剧创作 地址：https://pixtv.ai 免费视频ai：seedance ai 地址：https… 阅读更多 | | 29 | 28.1k | 1 天 |
- | workbuddy使用集合贴！workbuddy内容汇总 workbuddy有出色的办公能力，能帮大家做很多事情，不过很多朋友装好以后不知道怎么使用，于是这里为大家做了workbuddy玩法汇总，大家可以一键跳转！ 免费ai生图视频工具： workbuddy可用skills下载地址 下载地址… 阅读更多 | | 10 | 8.7k | 9月 25 日 |
- | codex使用教程集合贴，codex使用教程汇总（持续更新ing） codex有强大的能力，能帮大家做很多事情，不过很多朋友装好以后不知道怎么使用，于是这里为大家做了codex玩法汇总，大家可以一键跳转！ 免费ai生图视频工具： gpt-image 2.5使用地址: codex可以mcp地址 1、p… 阅读更多 | | 17 | 8.3k | 9月 25 日 |
- | claude使用手册集合贴，claude玩法汇总（持续更新ing） claude有强大的能力，能帮大家做很多事情，不过很多朋友装好以后不知道怎么使用，于是这里为大家做了claude玩法汇总，大家可以一键跳转！ 免费ai生图视频工具： claude可以mcp地址 1、pixpix mcp — claud… 阅读更多 | | 10 | 7.2k | 7月 21 日 |
- | 想把聊天记录导出来存档 结果拿到一堆乱码和废话 | | 6 | 2.7k | 1 分钟 |
- 另有 25 段，见 JSON 报告。
## news_01.html（disagreement）


### news_01.html：基线抽取独有

- 姆巴佩就“中国独裁者”迷因道歉：风波背后的资讯真空与“毛泽东热”
## news_02.html（agreement）

