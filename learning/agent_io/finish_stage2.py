"""第二阶段固定四课收尾：有限新页采集和离线重放。"""
import argparse
import hashlib
import json
import re
import sys
import time
from datetime import datetime, timezone
from html import escape
from pathlib import Path
from urllib.parse import urlsplit, urlunsplit, parse_qs
from urllib.request import build_opener, ProxyHandler, Request
from urllib.robotparser import RobotFileParser

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
from lxml import html
from learning.agent_io.review_pipeline import digest, read, validate_review

OUT = ROOT / 'output/agent_io/final'
SNAPSHOTS = OUT / 'snapshots'
UA = 'WebExtractLearning/1.0'
FROZEN = ['output/agent_io/candidate.json', 'config/agent_review_rubric.json']


def write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding='utf-8')


def now():
    return datetime.now(timezone.utc).isoformat()


def normalized(node):
    return ' '.join(node.text_content().split())


def canonical(url):
    p = urlsplit(url)
    return urlunsplit(('https', p.netloc.lower(), p.path, '', ''))


def article_url(href):
    parts = urlsplit(href)
    if parts.hostname == 'cj.sina.cn' and parts.path == '/article/norm_detail':
        href = parse_qs(parts.query).get('url', [''])[0]
    url = canonical(href)
    return url if re.match(r'^https://finance\.sina\.com\.cn/.*/doc-[a-z0-9]+\.shtml$', url) else None


def frozen():
    return {p: hashlib.sha256((ROOT / p).read_bytes().replace(b'\r\n', b'\n')).hexdigest() for p in FROZEN}


def request(opener, url):
    with opener.open(Request(url, headers={'User-Agent': UA}), timeout=20) as response:
        data = response.read(5_000_001)
        if len(data) > 5_000_000:
            raise ValueError('response exceeds 5MB')
        return data, response.geturl(), response.status


def discover():
    OUT.mkdir(parents=True, exist_ok=True)
    if (OUT / 'protocol.json').exists():
        raise ValueError('本批协议已存在，禁止重新挑页；使用默认命令离线重放。')
    protocol = {'frozen_at': now(), 'target': 'https://finance.sina.com.cn/roll/', 'count': 2,
                'selection': '列表DOM顺序前2个未在项目历史中出现的新浪文章URL；不按抽取结果挑页，失败也不替换。',
                'scope': '新浪文章模板复用观察；固定规则，模板不符也记录。', 'frozen': frozen(),
                'quality': '核对标题、正文完整性、杂质和元数据；记录图片/动态内容局限；AI审核不是独立人工金标。'}
    write(OUT / 'protocol.json', protocol)
    opener = build_opener(ProxyHandler({'http': 'http://127.0.0.1:7897', 'https': 'http://127.0.0.1:7897'}))
    for url, filename in [('https://finance.sina.com.cn/robots.txt', 'robots.txt'),
                          (protocol['target'], 'discovery.html')]:
        data, final, status = request(opener, url)
        (OUT / filename).write_bytes(data)
        print(filename, status, len(data))


def select():
    if (OUT / 'manifest.json').exists():
        raise ValueError('已经采集，禁止重新选页')
    if (OUT / 'selection.json').exists() and read(OUT / 'selection.json')['pages']:
        raise ValueError('已经选页，禁止替换')
    known_urls = set()
    for folder in ['samples', 'reports', 'config', 'news_validation', 'validation_blind',
                   'validation_blind_round2', 'validation_holdout', 'docs', 'output']:
        for path in (ROOT / folder).rglob('*'):
            if not path.is_file() or OUT in path.parents or path.suffix not in {'.json', '.html', '.md'}:
                continue
            for url in re.findall(r'https?://finance\.sina\.com\.cn/[^\s"<>]+?\.shtml', path.read_text(encoding='utf-8', errors='ignore')):
                known_urls.add(canonical(url))
    listing = html.document_fromstring((OUT / 'discovery.html').read_bytes())
    selected = []
    for node in listing.xpath('//a[@href]'):
        url = article_url(node.get('href'))
        if url and url not in known_urls and url not in [p['url'] for p in selected]:
            selected.append({'id': 'new_' + str(len(selected) + 1), 'url': url,
                             'listing_title': normalized(node), 'previous_url_match': False})
            if len(selected) == 2:
                break
    write(OUT / 'selection.json', {'selected_at': now(), 'known_url_count': len(known_urls),
                                 'known_urls': sorted(known_urls), 'pages': selected})
    print(json.dumps(selected, ensure_ascii=False, indent=2))
    if len(selected) != 2:
        raise ValueError('列表没有足够候选；不改采样规则强行凑数。')


def collect():
    protocol = read(OUT / 'protocol.json')
    if protocol['frozen'] != frozen():
        raise ValueError('冻结规则变化')
    if (OUT / 'manifest.json').exists():
        raise ValueError('本批已采集，禁止覆盖；默认命令离线重放。')
    opener = build_opener(ProxyHandler({'http': 'http://127.0.0.1:7897', 'https': 'http://127.0.0.1:7897'}))
    robots = RobotFileParser()
    robots.parse((OUT / 'robots.txt').read_text(encoding='utf-8', errors='replace').splitlines())
    manifest = []
    SNAPSHOTS.mkdir(parents=True, exist_ok=True)
    for selected in read(OUT / 'selection.json')['pages']:
        record = {**selected, 'attempted_at': now()}
        try:
            if not robots.can_fetch(UA, selected['url']):
                raise ValueError('robots disallows this URL')
            data, final, status = request(opener, selected['url'])
            if urlsplit(final).hostname != 'finance.sina.com.cn':
                raise ValueError('redirect outside selected host')
            path = SNAPSHOTS / (selected['id'] + '.html')
            path.write_bytes(data)
            record.update(status='fetched', http_status=status, final_url=final,
                          file=path.relative_to(ROOT).as_posix(), snapshot_sha256=hashlib.sha256(data).hexdigest())
        except Exception as exc:
            record.update(status='fetch_failed', error=str(exc))
        manifest.append(record)
        write(OUT / 'manifest.json', manifest)
        print(selected['id'], record['status'], record.get('error', ''))
        time.sleep(1)


def extraction_task():
    protocol = read(OUT / 'protocol.json')
    if protocol['frozen'] != frozen():
        raise ValueError('冻结规则或Rubrics已经变化，不沿用旧批次结论')
    selection = read(OUT / 'selection.json')
    manifest = read(OUT / 'manifest.json')
    if [p['url'] for p in manifest] != [p['url'] for p in selection['pages']] or len(manifest) != 2:
        raise ValueError('采集清单与预选的2页不一致')
    rules = read(ROOT / FROZEN[0])['rules']
    pages, evidence = [], []
    for record in manifest:
        if canonical(record['url']) in selection['known_urls']:
            raise ValueError('所选URL已出现在历史记录')
        if record['status'] != 'fetched':
            evidence.append({**record, 'extraction_status': 'fetch_failed'})
            continue
        path = ROOT / record['file']
        if hashlib.sha256(path.read_bytes()).hexdigest() != record['snapshot_sha256']:
            raise ValueError('原始快照变化：' + record['id'])
        tree = html.document_fromstring(path.read_bytes())
        titles = tree.xpath(rules['title_xpath'])
        containers = tree.xpath(rules['container_xpath'])
        page_evidence = {**record, 'title_count': len(titles), 'container_count': len(containers)}
        if len(titles) != 1 or len(containers) != 1:
            page_evidence['extraction_status'] = 'title_or_container_mismatch'
            evidence.append(page_evidence)
            continue
        container = containers[0]
        nodes = container.xpath(rules['block_xpath'])
        blocks = []
        for node in nodes:
            text = normalized(node)
            if text:
                blocks.append({'index': len(blocks) + 1, 'text': text,
                               'xpath': tree.getroottree().getpath(node), 'attributes': dict(node.attrib),
                               'links': [{'text': normalized(a), 'href': a.get('href') or ''} for a in node.xpath('.//a')]})
        page = {'file': record['id'] + '.html', 'title': normalized(titles[0]),
                'source_sha256': record['snapshot_sha256'], 'blocks': blocks}
        pages.append(page)
        # 从原DOM另存未被p规则选中的结构证据，不能只看提取结果自证完整。
        tables = [{'xpath': tree.getroottree().getpath(n), 'text': normalized(n),
                   'rows': [[normalized(cell) for cell in row.xpath('./th|./td')] for row in n.xpath('.//tr')]}
                  for n in container.xpath('.//table') if normalized(n)]
        widgets = [{'xpath': tree.getroottree().getpath(n), 'text': normalized(n)}
                   for n in container.xpath("./div[contains(concat(' ', normalize-space(@class), ' '), ' appendQr_wrap ')]")]
        page_evidence.update(title=page['title'], raw_count=len(blocks), tables=tables, widgets=widgets,
                             extraction_status='raw_extracted' if blocks else 'empty_blocks')
        evidence.append(page_evidence)
    task = {'schema_version': 1, 'rubric': read(ROOT / FROZEN[1]), 'pages': pages,
            'candidate_sha256': digest(read(ROOT / FROZEN[0])),
            'protocol_sha256': digest(protocol), 'manifest_sha256': digest(manifest),
            'scope': '预先固定规则的两页新快照；先保留原始p，质量另行审核。'}
    task['review_task_id'] = 'sina-final-' + digest(task)[:16]
    return task, evidence


def article_text(data):
    tree = html.document_fromstring(data)
    containers = tree.xpath("//div[@id='artibody'] | //div[contains(concat(' ', normalize-space(@class), ' '), ' left_zw ')]")
    if not containers:
        return ''
    clone = html.fromstring(html.tostring(containers[0]))
    for node in clone.xpath('.//script|.//style'):
        node.drop_tree()
    return ''.join(normalized(clone).split())


def shingles(text):
    return {text[i:i+5] for i in range(max(0, len(text)-4))}


def duplicate_check(evidence):
    history = []
    for folder in ['samples', 'news_validation', 'validation_blind', 'validation_blind_round2', 'validation_holdout']:
        for path in (ROOT / folder).rglob('*.html'):
            if path.name in {'index.html', 'progress.html'} or 'samples' not in path.parts:
                continue
            body = article_text(path.read_bytes())
            if len(body) >= 100:
                history.append((path.relative_to(ROOT).as_posix(), body, shingles(body)))
    records = []
    for page in evidence:
        if page['status'] != 'fetched':
            continue
        body = article_text((ROOT / page['file']).read_bytes())
        grams = shingles(body)
        closest, score, exact = None, 0, False
        for name, old, oldgrams in history:
            similarity = len(grams & oldgrams) / len(grams | oldgrams) if grams or oldgrams else 0
            if similarity > score:
                closest, score = name, similarity
            exact = exact or old == body
        records.append({'id': page['id'], 'exact_body_duplicate': exact, 'nearest_file': closest,
                        'char5_jaccard': round(score, 6), 'near_duplicate_threshold': .85,
                        'near_duplicate': score >= .85, 'body_characters': len(body)})
        history.append((page['file'], body, grams))
    return {'scanned_article_snapshots': len(history) - len(records), 'pages': records,
            'scope': '当前工作区历史URL、文章容器文本精确与字符5gram近重复；不能证明工作区外使用史。'}


def regression():
    from learning.agent_io.review_pipeline import build_task
    from learning.agent_io.repair_review import feedback_for, apply_plan
    from learning.agent_io.evaluate_batch import evaluate, CONFIG
    task = build_task()
    reviewed = validate_review(task, read(ROOT / 'output/agent_io/review_ai.json'))
    bad = read(ROOT / 'output/agent_io/review_bad_link.json')
    feedback = feedback_for(task, bad)
    _, repaired = apply_plan(task, bad, feedback, read(ROOT / 'output/agent_io/repair_plan.json'))
    boundaries = evaluate(read(CONFIG))
    return {'known_review_pass': reviewed['accepted'], 'bad_review_rejected': not feedback['accepted'],
            'repair_pass': repaired['accepted'], 'boundary_expectations_met': boundaries['experiment_checks_pass'],
            'known_raw_counts': [len(p['raw_blocks']) for p in reviewed['pages']]}


def finish():
    task, evidence = extraction_task()
    write(OUT / 'new_task.json', task)
    write(OUT / 'source_evidence.json', evidence)
    duplicates = duplicate_check(evidence)
    write(OUT / 'duplicate_check.json', duplicates)
    audit = read(OUT / 'new_ai_review.json')
    reviewed = validate_review(task, audit)
    if not reviewed['accepted']:
        raise ValueError('新页审核记录无效：' + '; '.join(reviewed['issues']))
    quality = read(OUT / 'quality_review.json')
    if quality.get('review_task_id') != task['review_task_id'] or quality.get('source_evidence_sha256') != digest(evidence):
        raise ValueError('质量审核与当前原DOM证据不对应')
    if [p['id'] for p in quality['pages']] != [p['id'] for p in evidence]:
        raise ValueError('质量审核页面不完整')
    for source, judgment in zip(evidence, quality['pages']):
        actual_tables = [t['xpath'] for t in source.get('tables', [])]
        if judgment.get('missing_table_xpaths') != actual_tables:
            raise ValueError('质量审核漏表证据与源DOM不一致：' + source['id'])
        if actual_tables and judgment.get('adoption') != 'do_not_adopt_as_complete_article':
            raise ValueError('存在未提取正文表格，不能判为完整文章采用')
    reg = regression()
    if not all(reg[k] for k in ['known_review_pass', 'bad_review_rejected', 'repair_pass', 'boundary_expectations_met']):
        raise ValueError('已知回归不再通过')
    if any(p['exact_body_duplicate'] or p['near_duplicate'] for p in duplicates['pages']):
        raise ValueError('新页与历史内容重复，不计为未见页')
    result = {'operations_complete': True, 'learning_mastery': '由用户亲自运行解释后确认',
              'quality_audit_sha256': digest(quality), 'paragraph_audit_sha256': digest(audit),
              'new_page_count': len(evidence), 'newly_evaluated_under_frozen_rules': True,
              'evaluation_exposed_after_this_run': True, 'general_accuracy': None,
              'regression': reg, 'duplicate_check': duplicates, 'quality': quality,
              'reviewed_pages': reviewed['pages'], 'published': False, 'ai_calls_during_replay': 0,
              'decision': '仅限定采用段落型新浪模板；含表格、图片正文、嵌套或模板异常的页面暂不直接采用；不在本阶段追加修复。'}
    write(OUT / 'results.json', result)
    render(result, evidence)
    print('STAGE 2 OPERATIONS: COMPLETE; original four lessons only.')
    print('KNOWN REGRESSION: PASS; NEW PAGES: 2; generic accuracy: NOT CLAIMED.')
    for page, q in zip(reviewed['pages'], quality['pages']):
        print(f"{page['file']}: raw={len(page['raw_blocks'])} content={len(page['content_blocks'])} editor={len(page['editor_blocks'])}; {q['adoption']}")
    print('REPORT: ' + str(OUT / 'index.html'))
    return result


def render(result, evidence):
    lines = ['<!doctype html><html lang=zh-CN><meta charset=utf-8><title>第二阶段四课验收</title>',
             '<style>body{font:16px/1.7 system-ui;max-width:1150px;margin:30px auto;padding:16px}',
             'table{border-collapse:collapse;width:100%}td,th{border:1px solid #ddd;padding:10px;vertical-align:top}',
             'code{overflow-wrap:anywhere}li{margin:8px 0}</style>',
             '<h1>第二阶段：四课操作已完成</h1>',
             '<p>固定方案后采集两页，成功与失败均保留。当前对话AI审核静态源DOM，未进行浏览器渲染视觉核验；重放不调用AI。两页不是统计代表样本，不能报告通用准确率。</p>',
             '<h2>四课与证据</h2><ol><li>准备任务：task.json / task.md。</li>',
             '<li>候选规则与独立检查：candidate.json / check.html。</li>',
             '<li>Rubrics与错误反馈：review/review.html / repair/index.html。</li>',
             '<li>复用和采用条件：本报告的新页质量审核与采用结论。</li></ol>',
             '<p><a href="../check.html">候选检查</a> · <a href="../review/review.html">已知审核</a> · ',
             '<a href="../repair/index.html">反馈修正</a> · <a href="../evaluation/index.html">补充结构实验</a></p>',
             '<h2>新页与采用条件</h2><table><tr><th>新页</th><th>原始/正文/编辑</th><th>质量证据</th><th>结论</th></tr>']
    for p, q, source in zip(result['reviewed_pages'], result['quality']['pages'], evidence):
        lines.append('<tr><td>' + escape(p['title']) + '<br><a href="' + escape(source['url'], quote=True)
                     + '">在线来源</a> · <a href="snapshots/' + source['id'] + '.html">原始快照</a></td><td>'
                     + f"{len(p['raw_blocks'])}/{len(p['content_blocks'])}/{len(p['editor_blocks'])}"
                     + '</td><td>' + escape(q['finding']) + '</td><td>' + escape(q['adoption']) + '</td></tr>')
    lines += ['</table><p>' + escape(result['decision']) + '</p>',
              '<p>“审核记录检查通过”与“文章完整”是不同结果。第二篇原始p记录通过，但漏表格，因此不能作为完整文章输出。</p>',
              '<h2>新页审核详情</h2>']
    for p, q, source in zip(result['reviewed_pages'], result['quality']['pages'], evidence):
        lines += ['<h3>' + escape(p['title']) + '</h3><p>' + escape(q['semantic_note']) + '</p>',
                  '<ul>'] + ['<li>' + escape(s) + '</li>' for s in q['limits']] + ['</ul>']
        for table in source.get('tables', []):
            lines += ['<p>原DOM表格位置：<code>' + escape(table['xpath']) + '</code>；当前规则未提取：</p><table>']
            for row in table['rows']:
                lines.append('<tr>' + ''.join('<td>' + escape(cell) + '</td>' for cell in row) + '</tr>')
            lines.append('</table>')
        lines.append('<details><summary>查看正文与编辑元数据</summary>')
        for b in p['content_blocks']:
            lines.append('<p>' + escape(b['text']) + '</p>')
        lines.append('<p>编辑元数据：' + escape('；'.join(b['text'] for b in p['editor_blocks'])) + '</p></details>')
    lines += ['<h2>去重与回归</h2><p>历史URL匹配未发现；容器正文精确/近重复检查未发现重复。已知两页原始45/23段、审核及反馈修正回归通过。</p>',
              '<p><a href="duplicate_check.json">内容去重详情</a> · <a href="protocol.json">预先冻结协议</a> · ',
              '<a href="manifest.json">采集清单与哈希</a> · <a href="results.json">结构化验收结果</a></p>',
              '<h2>操作收尾</h2><p>本阶段到此结束。失败项已记录，未为了通过而修改规则、重采样或追加课程。学习掌握仍需用户运行并解释关键结果。</p></html>']
    (OUT / 'index.html').write_text('\n'.join(lines), encoding='utf-8')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--discover', action='store_true')
    parser.add_argument('--collect', action='store_true')
    parser.add_argument('--select', action='store_true')
    parser.add_argument('--prepare', action='store_true')
    args = parser.parse_args()
    if args.discover:
        discover()
        select()
    elif args.select:
        select()
    elif args.collect:
        collect()
    elif args.prepare:
        task, evidence = extraction_task()
        write(OUT / 'new_task.json', task)
        write(OUT / 'source_evidence.json', evidence)
        print(task['review_task_id'], [(p['file'], len(p['blocks'])) for p in task['pages']])
    else:
        try:
            finish()
        except (OSError, ValueError, KeyError, TypeError) as exc:
            write(OUT / 'results.json', {'operations_complete': False, 'error': str(exc)})
            (OUT / 'index.html').write_text('<meta charset=utf-8><h1>验收中止</h1><p>' + escape(str(exc)) + '</p>', encoding='utf-8')
            print('STAGE 2 REJECTED: ' + str(exc))
            sys.exit(1)
