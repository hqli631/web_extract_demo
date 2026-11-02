# 自动抽取器对比

当前启发式抽取器与 Trafilatura 的差异候选。两者一致不等于正确，分歧也不自动代表错误。

| 页面 | 当前字符数 | 基线字符数 | 相似度估计 | 当前独有段落 | 基线独有段落 |
|---|---:|---:|---:|---:|---:|
| collected_5029464d5612ed80.html | 1208 | 1227 | 99.1% | 0 | 1 |
| collected_61b2572fd4c6cd0c.html | 112 | 124 | 0.0% | 1 | 4 |
| collected_c2d1dbf788829343.html | 403 | 430 | 96.6% | 0 | 1 |
| rendered_4b4fa7bd89532eaa.html | 243 | 266 | 95.4% | 0 | 2 |

相似度采用去空白后的字符五元组 Dice；它不是准确率。差异按单向文本包含判断，段落格式和标点差异仍可能产生分歧。

## collected_5029464d5612ed80.html（disagreement）


### collected_5029464d5612ed80.html：基线抽取独有

- 习言道｜近5000字公报，“严”字贯穿始终
## collected_61b2572fd4c6cd0c.html（disagreement）


### collected_61b2572fd4c6cd0c.html：当前抽取独有

- 8月21日，中共中央在中南海召开党外人士座谈会，就中共中央关于持之以恒推进全面从严治党若干重大问题的决定听取各民主党派中央、全国工商联负责人和无党派人士代表的意见建议。中共中央总书记习近平主持座谈会并发表重要讲话。他指出——

### collected_61b2572fd4c6cd0c.html：基线抽取独有

- 本网站所刊载信息，不代表中新社和中新网观点。 刊用本网站稿件，务经书面授权。
- 未经授权禁止转载、摘编、复制及建立镜像，违者将依法追究法律责任。
- copyright ©1999-2026
- chinanews.com. all rights reserved
## collected_c2d1dbf788829343.html（disagreement）


### collected_c2d1dbf788829343.html：基线抽取独有

- 公安部就修订《公安机关办理行政案件程序规定》公开征求意见
## rendered_4b4fa7bd89532eaa.html（disagreement）


### rendered_4b4fa7bd89532eaa.html：基线抽取独有

- 霍尔木兹海峡一艘油轮遇袭起火
- 责任编辑：欧阳文芊
