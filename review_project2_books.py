"""Post-freeze source checks; never sends feedback to the Agent."""
import json
import time
from html import escape
from pathlib import Path
from urllib.parse import urlsplit
from project2_engine import digest, extract, norm, parse, validate_result
from project2_report import CSS, render_report

ROOT = Path(__file__).resolve().parent
OUT = ROOT/'output/project2/books_product_27b'

def main():
    trace = json.loads((OUT/'trace.json').read_text(encoding='utf8'))
    assert trace['frozen_before_holdout']
    assert digest((OUT/'extractor.py').read_bytes()) == trace['frozen_candidate_sha256']
    assert digest((ROOT/'project2_engine.py').read_bytes()) == trace['engine_sha256']
    rules = json.loads((OUT/'rules.json').read_text(encoding='utf8'))
    sources = {p['id']:p for p in trace['input_pages']}
    rows = []
    cpu_started = time.perf_counter()
    for row in trace['rounds'][-1]['pages'] + trace['holdout']:
        source = sources[row['id']]
        raw = (ROOT/source['path']).read_bytes()
        assert digest(raw) == source['sha256']
        tree = parse(raw)
        result = json.loads((OUT/row['result']).read_text(encoding='utf8'))
        assert extract(rules, raw) == result, 'Frozen rule CPU replay changed: ' + row['id']
        article = tree.xpath('//article')[0]
        description = article.xpath('./div[@id="product_description"]/following-sibling::p[1]')[0]
        main = article.xpath('./div[1]/div[contains(@class,"product_main")]')[0]
        table = article.xpath('./table')[0]
        expected_table = [[norm(c) for c in tr.xpath('./th|./td')] for tr in table.xpath('./tr')]
        selected = {b['xpath']:b for b in result['blocks']}
        path = tree.getroottree().getpath
        retained = lambda n: path(n) in selected and selected[path(n)]['text'] == norm(n)
        facts = next((b for b in result['blocks'] if b['type']=='table'), {})
        headings = article.xpath('./div[@id="product_description"]/h2 | ./div[@class="sub-header"]/h2[normalize-space(.)="Product Information"]')
        heading_types = [b['type'] for b in result['blocks'] if b['text'] in [norm(n) for n in headings]]
        checks = dict(title_matches=result['title']==norm(main.xpath('./h1')[0]),
                      description_matches=retained(description),
                      price_matches=retained(main.xpath('./p[@class="price_color"]')[0]),
                      stock_matches=retained(main.xpath('./p[contains(@class,"availability")]')[0]),
                      table_cells_match=facts.get('rows')==expected_table,
                      evidence_and_order_valid=not validate_result(result,raw),
                      cart_or_recommendations_in_body=any('Add to basket' in b['text'] or 'Products you recently viewed' in b['text'] for b in result['blocks']),
                      heading_text_retained=all(any(b['text']==norm(n) for b in result['blocks']) for n in headings),
                      heading_types_correct=heading_types==['subheading','subheading'])
        assert all(checks[k] for k in ('title_matches','description_matches','price_matches','stock_matches','table_cells_match','evidence_and_order_valid','heading_text_retained')), row['id']
        assert not checks['cart_or_recommendations_in_body'], row['id']
        rows.append(dict(id=row['id'],role=row['role'],title=result['title'],url=source['url'],
                         checks=checks,blocks=len(result['blocks']),table_rows=len(expected_table),
                         excluded_review=[dict(xpath=b['xpath'],assessment='Appropriate exclusion: recently viewed products are recommendations, not current book content.') for b in result['excluded']],
                         remaining=['Product headings retained as paragraph, not subheading.',
                                    'Position-based div selectors are fragile under layout changes.',
                                    'Cover pixels not extracted; overall image completeness unknown.']))
    holdout = [p for p in trace['input_pages'] if p['role']=='final_holdout']
    for p in OUT.glob('prompt_round_*.json'):
        for m in json.loads(p.read_text(encoding='utf8')):
            if m['role'] == 'user':
                payload = json.loads(m['content'])
                ids = [s['id'] for k in ('generation_samples','development_samples') for s in payload.get(k,[])]
                assert not set(ids) & {s['id'] for s in holdout}
    exposure = []
    for source in [p for p in trace['input_pages'] if p['role']=='generation']:
        tree = parse((ROOT/source['path']).read_bytes())
        links = tree.xpath('//article/ul//h3/a/@href')
        for target in holdout:
            if any(urlsplit(target['url']).path.split('/')[-2] in link for link in links):
                exposure.append(dict(generation_page=source['id'],related_target=target['id']))
    review = dict(scope='Post-freeze checks against downloaded DOM, plus current-chat AI review of exclusion semantics. Not human gold or independent accuracy.',
                  model=trace['model'],pages=rows,
                  holdout_target_documents_in_prompt=False,related_target_links_in_generation=exposure,
                  limitations=['Same-site, same-template sample only; no cross-layout accuracy claim.',
                               'Recently-viewed widgets expose some other target titles/prices in generation input. Target descriptions/tables were not separately supplied as holdout documents.',
                               'XPath data interpreted by trusted lxml engine; not arbitrary Python generation or model weight training.'],
                  cpu_replay_seconds=round(time.perf_counter()-cpu_started,4),
                  cpu_timing_scope='In-process re-extraction plus source checks; includes file reads and parsing, not an industrial throughput benchmark.',
                  summary='10/10 页的标题、描述、价格、库存及 7 行表格与原始 DOM 对应；正文未混入购物按钮或最近浏览推荐。10/10 页的小标题仍被标为 paragraph，图片完整性 unknown。自动检查状态保留 needs_review。')
    (OUT/'review.json').write_text(json.dumps(review,ensure_ascii=False,indent=2),encoding='utf8')
    render_report(OUT,trace)
    overview = ROOT/'output/project2/books_experiment'
    overview.mkdir(exist_ok=True)
    runs = [('books_product_v1','Flash：初次任务'),('books_product_v2','Flash：开发反馈澄清'),('books_product_27b','27B：相同澄清任务')]
    run_rows = []
    for directory, name in runs:
        run = json.loads((ROOT/'output/project2'/directory/'trace.json').read_text(encoding='utf8'))
        run_rows.append('<tr><td><a href="../'+directory+'/index.html">'+name+'</a></td><td>'+run['model']+'</td><td>'+str(len(run['api_attempts']))+'</td><td>'+str(sum(a.get('usage',{}).get('total_tokens',0) for a in run['api_attempts']))+'</td><td>'+run['final_status']+'</td></tr>')
    roles = {'generation':'生成样本','development_feedback':'开发反馈','final_holdout':'留出测试'}
    page_rows = []
    for source in trace['input_pages']:
        row = next(p for p in rows if p['id']==source['id'])
        original = '../../..' + '/' + source['path']
        page_rows.append('<tr><td>'+source['id']+'</td><td>'+escape(row['title'])+'</td><td>'+roles[source['role']]+'</td><td><a href="'+escape(source['url'],quote=True)+'">原站</a> · <a href="'+original+'">本地网页</a></td><td>6 块 / 7 行表格</td></tr>')
    content = '<!doctype html><html lang="zh-CN"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>项目二 · 10 页新类型实验</title><style>'+CSS+'</style><div class="wrap"><header class="hero"><h1>10 个新类型网页：图书详情提取</h1><p>从 Python 发布博客切换到商品详情布局；3 页生成、2 页开发反馈、5 页冻结后测试。</p><p><a href="../books_product_27b/index.html">打开完整提取报告 →</a></p></header><section class="panel"><h2>实际运行流程</h2><p>低频下载 HTML 和 22 个样式/图片资源 → 固定角色与 SHA256 → 将 3 页 DOM 摘要发给千问 → 开发检查与最多 2 次反馈修复 → 冻结规则 → CPU 执行 5 页留出测试 → 当前对话 AI 复核并保存证据。</p><p>这里的样本用于提示生成规则，没有更新模型权重。Flash 两次实验失败记录均保留；27B 在澄清任务上一次生成可执行规则。</p></section><section class="panel"><h2>调用与修复对比</h2><table><tr><th>实验报告</th><th>模型</th><th>调用次数</th><th>tokens</th><th>自动状态</th></tr>'+''.join(run_rows)+'</table><p>合计 7 次 API 调用、178129 tokens（含返回的缓存 tokens；不是账单金额）。不同实验的任务说明、检查器版本存在变化，不能当作受控模型排名。</p></section><section class="panel"><h2>抽取效果</h2><p>'+escape(review['summary'])+'</p><p>每页输出：价格、库存、描述标题、描述段落、信息标题、7 行信息表。两个标题文字保留，但类型仍需细化；封面未做 OCR。</p><p>规则含 div 位置索引，布局变化后可能失效。同站推荐组件使部分其他目标书名/价格出现在生成页内；目标页未作为输入文档提供，但这不构成严格无交叉暴露的独立测试。</p><p><a href="../books_product_27b/review.json">逐页专项复核 JSON</a> · <a href="../../../docs/PROJECT2_NEW10_EXPERIMENT.md">操作与学习说明</a></p></section><section class="panel"><h2>10 个下载网页</h2><table><tr><th>编号</th><th>书名</th><th>用途</th><th>查看网页</th><th>结果</th></tr>'+''.join(page_rows)+'</table></section></div></html>'
    (overview/'index.html').write_text(content,encoding='utf8')
    print(review['summary'])
    print('Related-target link exposures:',len(exposure))

if __name__ == '__main__':
    main()
