# 新布局任务登记与检查

本脚手架不采集网页、不填充虚构 URL，也不宣布新测试已经就绪。它先规定后续采集材料必须提供什么，防止模型/规则调试后再把同一批网页称作未见测试。

入口：learning/prepare_next_layout_tasks.py。配置：config/next_layout_tasks.json。当前配置包含3个待填新布局簇，状态todo、pages为空。

~~~powershell
cd "D:\codex project\web_extract_demo"
.\.venv\Scripts\python.exe -X utf8 .\learning\prepare_next_layout_tasks.py
~~~

预期status=PASS，但ready_clusters=0、unseen_page_test_registration_allowed=false、cross_layout_generalization_claim_allowed=false。这里PASS仅说明草案结构可读取，不是数据完成。

每一条page需要以下字段：

|字段|含义|
|---|---|
|role|train、dev或test|
|exposure|new、historical_exposed或pending；test必须new|
|path|仓库内保存的HTML路径|
|url|真实http(s)来源|
|sha256|保存HTML原始字节的SHA256|

每个簇ready前，至少要有2篇train、1篇dev、1篇test，并提供经过复核的target_code路径及SHA256。这个配额只是最小协议门槛，不代表足够进行可靠模型训练。

检查器会拒绝跨任务重复路径、重复URL、相同内容哈希、越界路径、哈希不符、历史test和ready缺字段。近重复和同布局判断还需要额外结构/语义复核，本脚本没有声称自动解决全部泄漏。

本协议中的page.role支持同布局内的文章分工：一个簇内train供生成/修复，test是未调试文章。它只能注册“已知布局新文章”评估，不能据此声称跨布局泛化。跨布局模型训练实验必须另将整个cluster task分成train/dev/test，保留全新布局簇；报告字段cross_layout_generalization_claim_allowed因此固定为false。

实际采集后先登记来源与暴露状态，再生成目标/调参；测试材料交评测者保管。已看过或用于修复的test必须降级为历史材料，并另外冻结新test。

本工具离线运行，不调用模型、不联网、不执行候选抽取代码。测试入口为python -m unittest tests.test_next_layout_tasks。
