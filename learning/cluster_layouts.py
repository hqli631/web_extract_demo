"""3.1: offline structural inventory. Historical pages never become holdout data."""
import hashlib
import json
import re
from collections import Counter
from html import escape
from pathlib import Path
from urllib.parse import urlsplit

from lxml import html

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'output' / 'stage3' / 'layout'
REGIONS = [
    "//div[@id='artibody']",
    "//div[contains(concat(' ', normalize-space(@class), ' '), ' left_zw ')]",
    '//article', '//main',
]
THRESHOLD = 0.60


def signature(node):
    # Ignore text, sibling indices and generated numeric attribute values.
    attrs = []
    for key in ['id', 'class']:
        values = sorted(set((node.get(key) or '').split()))
        values = [v for v in values if len(v) < 45 and not re.search(r'\d', v)]
        if values:
            attrs.append(key + '=' + '.'.join(values))
    return str(node.tag) + ('[' + ';'.join(attrs) + ']' if attrs else '')


def features(region):
    result = set()
    def visit(node, path, depth):
        if not isinstance(node.tag, str) or node.tag in {'script', 'style', 'noscript'}:
            return
        path = path + (signature(node),)
        result.add('/'.join(path))
        if depth < 4:
            for child in node:
                visit(child, path, depth + 1)
    visit(region, (), 0)
    return result


def similarity(left, right):
    return len(left & right) / len(left | right) if left | right else 1.0


def assign_clusters(pages):
    """Deterministic complete-link grouping: all members must meet threshold."""
    clusters = []
    for page in pages:
        for group in clusters:
            if all(similarity(set(page['features']), set(other['features'])) >= THRESHOLD
                   for other in group):
                group.append(page)
                break
        else:
            clusters.append([page])
    for index, group in enumerate(clusters, 1):
        for page in group:
            page['cluster_id'] = f'layout_{index:02d}'
    return clusters


def source_map():
    result = {}
    for entry in json.loads((ROOT / 'reports/collection_manifest.json').read_text(encoding='utf-8-sig')):
        result['samples/' + entry['file']] = entry.get('url')
    for entry in json.loads((ROOT / 'output/agent_io/final/manifest.json').read_text(encoding='utf-8-sig')):
        result[entry['file']] = entry['url']
    return result


def inspect(path, urls):
    data = path.read_bytes()
    tree = html.document_fromstring(data)
    region, selected = tree, 'document-fallback'
    for xpath in REGIONS:
        nodes = tree.xpath(xpath)
        if len(nodes) == 1:
            region, selected = nodes[0], xpath
            break
    rel = path.relative_to(ROOT).as_posix()
    saved = re.search(rb'saved from url=\(\d+\)(https?://[^\s<>]+)', data[:12000])
    url = urls.get(rel) or (saved.group(1).decode('utf-8', errors='replace') if saved else None)
    return {
        'file': rel, 'url': url, 'domain': urlsplit(url).netloc if url else None,
        'sha256': hashlib.sha256(data).hexdigest(), 'bytes': len(data),
        'title': ' '.join(tree.xpath('string(//title)').split()),
        'region_xpath': selected, 'region_signature': signature(region),
        'features': sorted(features(region)),
        'direct_tags': dict(Counter(n.tag for n in region if isinstance(n.tag, str))),
        'descendant_tags': {tag: len(region.xpath('.//' + tag)) for tag in ['p', 'table', 'img']},
        'exposure': 'historical_exposed',
        'role': 'non_article_navigation' if rel == 'samples/index.html' else 'development_pool_only',
    }


def build():
    paths = sorted((ROOT / 'samples').glob('*.html'))
    paths += sorted((ROOT / 'output/agent_io/final/snapshots').glob('*.html'))
    urls = source_map()
    pages = [inspect(p, urls) for p in paths]
    groups = assign_clusters(pages)
    targets = []
    for label, marker, seeds in [
        ('sina', 'artibody', ['blog_01.html', 'collected_14a028de299edfab.html', 'collected_af5904c15d1deebc.html']),
        ('chinanews', 'left_zw', ['xpath_practice.html', 'xpath_practice_02.html', 'xpath_practice_03.html']),
    ]:
        members = [p for p in pages if marker in p['region_xpath']]
        cluster_ids = sorted(set(p['cluster_id'] for p in members))
        targets.append({
            'target_template': label, 'candidate_cluster_ids': cluster_ids,
            'historical_pages': len(members),
            'generation_files': ['samples/' + name for name in seeds],
            'repair_pool': [p['file'] for p in members if Path(p['file']).name not in seeds],
            'fresh_test_files': [], 'fresh_test_gap': 6,
            'fresh_repair_gap': max(0, 3 - (len(members) - 3)),
            'status': 'provisional_requires_fresh_test_collection_and_cluster_review',
        })
    duplicates = []
    for i, page in enumerate(pages):
        for other in pages[:i]:
            if page['sha256'] == other['sha256'] or (page['url'] and page['url'] == other['url']):
                duplicates.append([other['file'], page['file']])
    return {
        'unit': '3.1', 'status': 'inventory_ready_sample_protocol_provisional',
        'method': 'known-region-assisted, depth-4 signature-set Jaccard, deterministic complete-link',
        'threshold': THRESHOLD, 'visual_layout_verified': False,
        'notes': ['候选区域使用历史模板定位，不是通用无监督网页聚类。',
                  '局部DOM相似度是布局代理，不执行JS或测量视觉版式。',
                  '样本路径排序影响贪心分组；阈值是教学配置，未校准。',
                  '历史页面一律不可升格为新测试页；待补采并登记封存数据。',
                  '重复URL/字节仅作初筛，尚未完成正文近重复排查。'],
        'pages': pages, 'cluster_count': len(groups),
        'targets': targets, 'duplicate_pairs': duplicates,
        'pairwise': [{'left': a['file'], 'right': b['file'],
                      'similarity': round(similarity(set(a['features']), set(b['features'])), 6)}
                     for i, a in enumerate(pages) for b in pages[:i]],
    }


def write_report(result):
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / 'inventory.json').write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding='utf-8')
    content = ['<!doctype html><html lang="zh"><meta charset="utf-8"><title>3.1 布局分组</title>',
               '<style>body{font:16px/1.7 sans-serif;max-width:1200px;margin:30px auto}table{border-collapse:collapse;width:100%}td,th{border:1px solid #ddd;padding:8px;vertical-align:top}code{word-break:break-all}details{margin:15px 0}</style>',
               '<h1>3.1 布局分组与样本盘点</h1><p>当前为结构盘点，不是正文质量报告；无新测试页，未生成代码。</p>',
               '<h2>先看样本分工与缺口</h2><table><tr><th>目标模板</th><th>历史页</th><th>候选簇</th><th>生成页</th><th>修复池</th><th>新测试缺口</th></tr>']
    for t in result['targets']:
        content.append('<tr>' + ''.join('<td>' + escape(str(v)) + '</td>' for v in [t['target_template'], t['historical_pages'], t['candidate_cluster_ids'], ', '.join(t['generation_files']), len(t['repair_pool']), t['fresh_test_gap']]) + '</tr>')
    content += ['</table><p>目标模板不是最终布局簇。当前按容器子结构会拆出多个候选簇，分工仅为草案；生成提示尚未创建。分组核验、去重和新测试补采后才能冻结。</p>',
                '<h2>按结构分组（点击文件打开快照）</h2>']
    for cid in sorted(set(p['cluster_id'] for p in result['pages'])):
        members = [p for p in result['pages'] if p['cluster_id'] == cid]
        minimum = min([similarity(set(a['features']), set(b['features'])) for i,a in enumerate(members) for b in members[:i]] or [1.0])
        content.append(f'<h3>{cid}：{len(members)}页；簇内最低相似度 {minimum:.3f}</h3>')
        for p in members:
            source = ('<a href="' + escape(p['url'], quote=True) + '">原网址</a>') if p['url'] else '原网址未确认'
            content.append('<details><summary>' + escape(p['file']) + ' — ' + escape(p['title']) + '</summary><p><a href="' + escape((ROOT/p['file']).as_uri(), quote=True) + '">本地快照</a> | ' + source + '</p><p>候选区域：<code>' + escape(p['region_xpath']) + '</code></p><p>直接子标签：' + escape(str(p['direct_tags'])) + '</p><p>后代统计：' + escape(str(p['descendant_tags'])) + '</p><p>用途：' + escape(p['role']) + '；SHA256：<code>' + p['sha256'] + '</code></p><pre>' + escape('\n'.join(p['features'])) + '</pre></details>')
    content += ['<h2>亲手比较：目标模板内的相似度</h2><p>Jaccard = 共同路径特征数 / 两页路径特征并集数。数字不是正文质量，也不是规则复用成功率。</p><table><tr><th>页面A</th><th>页面B</th><th>结构相似度</th></tr>']
    target_files = {p for t in result['targets'] for p in t['generation_files']}
    for pair in result['pairwise']:
        if pair['left'] in target_files and pair['right'] in target_files:
            content.append('<tr>' + ''.join('<td>'+escape(str(pair[k]))+'</td>' for k in ['left','right','similarity'])+'</tr>')
    content += ['</table><h2>方法边界</h2><ul>'] + ['<li>'+escape(n)+'</li>' for n in result['notes']] + ['</ul><p>URL/字节重复候选：'+escape(str(result['duplicate_pairs']))+'</p></html>']
    (OUT/'index.html').write_text('\n'.join(content), encoding='utf-8')


if __name__ == '__main__':
    result = build()
    write_report(result)
    print(f"INVENTORY: pages={len(result['pages'])}; candidate_clusters={result['cluster_count']}")
    for t in result['targets']:
        print(f"{t['target_template']}: historical={t['historical_pages']}; generation=3; repair_pool={len(t['repair_pool'])}; fresh_test_gap={t['fresh_test_gap']}")
    print('UNIT 3.1: inventory ready; fresh test data and split freeze still pending')
    print(OUT/'index.html')
