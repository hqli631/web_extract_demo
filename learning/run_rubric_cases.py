"""4.1 controlled rubric examples, not fresh model judgments or accuracy."""
import copy
import json
import sys
from html import escape
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from lxml import html
from learning.run_cluster_generation import digest

OUT=ROOT/'output/stage4/specification'


SOURCE='''<meta charset="utf-8"><h1>访谈：社区如何使用人工智能</h1>
<div id="article">
<p id="byline">记者 张三</p>
<p id="intro">社区在三个服务站试用人工智能辅助咨询，详情见<a href="/report">试点报告</a>。</p>
<p id="question">中新社记者：您如何评价人工智能对社区服务的影响？</p>
<p id="answer">受访者：它可以辅助查找资料，但重要决定仍需工作人员核实。</p>
<h2 id="heading">试点结果</h2>
<ul id="list"><li>保留人工核实环节。</li><li>定期检查服务效果。</li></ul>
<table id="table"><tr><th>项目</th><th>数量</th></tr><tr><td>服务站</td><td>3</td></tr></table>
<div id="caption" class="pictext">图为社区服务站试点现场。</div>
<div id="folded" style="display:none">补充说明：试点数据尚未覆盖所有居民。</div>
<p id="analysis">研究者指出，“来评论区说说”是一种常见互动引导语。</p>
<div id="menu" style="display:none"><a href="/">返回首页</a></div>
<p id="cta">对于这次试点，你怎么看？来评论区说说。</p>
<div id="promotion">扫码下载本平台APP，领取优惠券。</div>
</div>'''


def build():
    tree=html.document_fromstring(SOURCE)
    ids=['byline','intro','question','answer','heading','list','table','caption','folded','analysis','menu','cta','promotion']
    records={}
    kinds={'heading':'subheading','list':'list','table':'table','caption':'caption'}
    for key in ids:
        node=tree.xpath('//*[@id=$key]',key=key)[0]
        row={'id':key,'kind':kinds.get(key,'paragraph'),'text':' '.join(node.text_content().split()),
             'xpath':tree.getroottree().getpath(node)}
        if key=='table':
            row['rows']=[[' '.join(c.text_content().split()) for c in tr.xpath('./th|./td')] for tr in node.xpath('.//tr')]
        records[key]=row
    keep=['intro','question','answer','heading','list','table','caption','folded','analysis']
    title='访谈：社区如何使用人工智能'
    baseline={'title':title,'blocks':[copy.deepcopy(records[k]) for k in keep],
              'metadata':[dict(records['byline'],kind='author')],
              'excluded':[copy.deepcopy(records[k]) for k in ['menu','cta','promotion']]}
    cases=[]

    def add(key,label,output,failed=(),unknown=(),reason=''):
        cases.append({'case_id':key,'label':label,'synthetic':True,'output':output,
                      'expected_answers':{q:('unknown' if q in unknown else 'no' if q in failed else 'yes') for q in ['Q1','Q2','Q3','Q4','Q5']},
                      'reason':reason,'origin':'predefined controlled transformation; not model verdict'})

    add('correct','符合任务范围',copy.deepcopy(baseline),reason='访谈问句、折叠补充、图说表格保留；独立署名、菜单、互动和推广分流。analysis引用互动文案作分析，仍是正文。')
    for key,label,remove,q in [('missing_paragraph','漏叙述段','answer','Q2'),('missing_table','漏信息表','table','Q3'),('missing_list','漏信息列表','list','Q3'),
                               ('missing_caption','漏图说','caption','Q3'),('missing_folded','误删折叠叙述','folded','Q2')]:
        output=copy.deepcopy(baseline)
        output['blocks']=[r for r in output['blocks'] if r['id']!=remove]
        add(key,label,output,failed=[q],reason='缺失由对应完整性题主评；不因同一缺失再扣Q5。源节点：'+records[remove]['xpath'])
    for key,label,injected in [('promotion_in_body','推广混入','promotion'),('byline_in_body','独立署名混入','byline'),
                               ('cta_in_body','互动引导混入','cta'),('hidden_menu_in_body','隐藏菜单混入','menu')]:
        output=copy.deepcopy(baseline)
        output['blocks'].append(copy.deepcopy(records[injected]))
        order={k:i for i,k in enumerate(ids)}
        output['blocks'].sort(key=lambda r:order[r['id']])
        output['metadata']=[r for r in output['metadata'] if r['id']!=injected]
        output['excluded']=[r for r in output['excluded'] if r['id']!=injected]
        add(key,label,output,failed=['Q4'],reason='记录忠实且有序，问题是用途分类，不自动重复扣Q5。源节点：'+records[injected]['xpath'])
    output=copy.deepcopy(baseline)
    output['blocks'].insert(3,copy.deepcopy(records['answer']))
    add('duplicate','正文重复',output,failed=['Q5'],reason='同一回答出现两次；篇幅增加不代表质量提高。')
    output=copy.deepcopy(baseline)
    output['blocks'][1],output['blocks'][2]=output['blocks'][2],output['blocks'][1]
    add('reordered','问答乱序',output,failed=['Q5'],reason='原文均在但回答被放到问题前；完整性与顺序分别判断。')
    output=copy.deepcopy(baseline)
    output['title']='另一篇无关新闻'
    add('wrong_title','标题不符',output,failed=['Q1'],reason='正文未变但主标题错误，由Q1主评。')
    image_source='<meta charset="utf-8"><h1>图解：社区试点</h1><div id="article"><p id="lead">请看试点图解。</p><img src="diagram.png" alt=""></div>'
    image_output={'title':'图解：社区试点','blocks':[{'id':'lead','kind':'paragraph','text':'请看试点图解。','xpath':'/html/body/div/p'}],'metadata':[],'excluded':[]}
    add('image_unknown','图解内容证据不足',image_output,unknown=['Q2','Q3'],reason='只有导语，图像可能承载主要信息；未提供图片像素，不虚构OCR也不把未知填yes或no。')
    cases[-1]['source_html_override']=image_source
    task={'unit':'4.1','fixture_type':'synthetic controlled cases, not new natural pages',
          'source_html':SOURCE,'source_records':records,'cases':cases,
          'rubric_sha256':digest((ROOT/'config/body_quality_rubric.json').read_bytes()),
          'review_status':'expected labels defined by construction, no model assessment run',
          'model_api_calls':0,'training_updates':0}
    return task


def run():
    task=build()
    OUT.mkdir(parents=True,exist_ok=True)
    path=OUT/'cases.json'
    if path.exists() and json.loads(path.read_text(encoding='utf-8'))!=task:
        raise ValueError('controlled examples changed; create version rather than overwrite')
    path.write_text(json.dumps(task,ensure_ascii=False,indent=2),encoding='utf-8')
    (OUT/'source.html').write_text(SOURCE,encoding='utf-8')
    parts=['<!doctype html><meta charset="utf-8"><title>4.1 评价依据与受控错例</title>',
           '<style>body{font:16px/1.8 sans-serif;max-width:1150px;margin:30px auto}pre{white-space:pre-wrap}td,th{border:1px solid #ccc;padding:8px}table{border-collapse:collapse}details{margin:15px 0}</style>',
           '<h1>4.1 评价依据与受控错例</h1><p>本页是构造错例及预先约定标签，不是AI新审核结果、准确率或reward。旧第三阶段评价和抽取器均未修改。</p>',
           '<p>用固定源内容，只改变候选输出中的一个因素，观察应该影响哪项判断。问句不等于噪声，隐藏不等于删除，含互动引导词也不等于互动组件。</p>',
           '<h2>源内容完整清单</h2><pre>'+escape(json.dumps(task['source_records'],ensure_ascii=False,indent=2))+'</pre>',
           '<h2>错例与预期影响</h2><table><tr><th>案例</th><th>Q1—Q5预期</th><th>依据</th></tr>']
    for case in task['cases']:
        values=' / '.join(case['expected_answers'].values())
        print(f"{case['case_id']}: expected {values}")
        parts+=['<tr><td>'+escape(case['case_id']+' '+case['label'])+'</td><td>'+values+'</td><td>'+escape(case['reason'])+'</td></tr>']
    parts+=['</table>']
    for case in task['cases']:
        parts+=['<details><summary>'+escape(case['case_id']+'：完整候选输出')+'</summary><pre>'+escape(json.dumps(case,ensure_ascii=False,indent=2))+'</pre></details>']
    (OUT/'index.html').write_text('\n'.join(parts),encoding='utf-8')
    print(f"UNIT4.1: {len(task['cases'])} controlled examples; no new AI judgments; no scores; API calls=0")
    print(OUT/'index.html')


if __name__=='__main__':
    run()
