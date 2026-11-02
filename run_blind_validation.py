"""Create a frozen, bounded validation batch from previously supplied URLs."""
import argparse
import hashlib
import json
from html import escape
from pathlib import Path
from urllib.parse import urlsplit, urlunsplit

from collect_pages import collect
from compare_extractors import analyze, write_reports
from extract import extract_file

ROOT = Path(__file__).resolve().parent
BATCH = ROOT / 'validation_blind'
CODE_FILES = ('extract.py', 'content_scope.py', 'compare_extractors.py')


def read(path):
    return json.loads(path.read_text(encoding='utf-8-sig'))


def write(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding='utf-8')


def code_hashes():
    return {name: hashlib.sha256((ROOT / name).read_bytes()).hexdigest() for name in CODE_FILES}


def canonical_url(url):
    parts = urlsplit(url or '')
    return urlunsplit((parts.scheme.lower(), parts.netloc.lower(), parts.path.rstrip('/'), '', ''))


def development_overlap(entry, snapshot, known):
    urls = {canonical_url(entry.get(key)) for key in ('url', 'seed_url')} - {''}
    for previous in known:
        previous_urls = {canonical_url(previous.get(key)) for key in ('url', 'seed_url')} - {''}
        if urls & previous_urls:
            return 'URL 已出现在开发集，不能计入独立验证'
        if entry.get('content_hash') and entry['content_hash'] == previous.get('content_hash'):
            return '页面文本哈希与开发集重复'
        if snapshot and snapshot == previous.get('snapshot'):
            return 'HTML 快照与开发集重复'
    return ''


def development_entries():
    known = []
    for folder in (ROOT, ROOT / 'news_validation'):
        manifest = folder / 'reports/collection_manifest.json'
        if manifest.exists():
            known.extend(read(manifest))
        for path in (folder / 'samples').glob('*.html'):
            known.append({'snapshot': hashlib.sha256(path.read_bytes()).hexdigest()})
    return known


def audit_page(result, snapshot, audit):
    if not audit:
        return 'pending_ai_review', {'reason': '没有对应样本的审核记录'}
    if audit.get('snapshot') != snapshot:
        return 'stale', {'reason': 'HTML 快照已经变化，旧审核不能复用'}
    if audit.get('requires_ocr'):
        return 'needs_ocr', {'reason': '主要内容位于图片，当前只审核 DOM 文本，完整性尚未验证'}
    actual = result['content'].splitlines()
    expected = audit['body_blocks']
    excluded = [text for text in audit.get('excluded_blocks', []) if text and text in result['content']]
    passed = actual == expected and not excluded
    return ('pass' if passed else 'fail'), {
        'exact_body_and_order_match': actual == expected,
        'missing': [text for text in expected if text not in actual],
        'extra': [text for text in actual if text not in expected],
        'excluded_content_leaked': excluded,
    }


def run(do_collect=False, batch=BATCH):
    context_path = batch / 'evaluation_context.json'
    current_hashes = code_hashes()
    configured_urls = [seed for target in read(ROOT / 'config/collection_blind.json')['targets']
                       for seed in target['seeds']]
    if context_path.exists():
        context = read(context_path)
        if context['frozen_code_sha256'] != current_hashes:
            raise ValueError('提取代码已变化。请保留本批旧结果，并使用新的 validation_blind_round 目录开始新批次。')
        if not set(configured_urls).issubset(set(context.get('urls', []))):
            context['urls'] = list(dict.fromkeys(context.get('urls', []) + configured_urls))
            write(context_path, context)
    else:
        context = {
            'frozen_code_sha256': current_hashes,
            'note': '冻结提取代码后采集；在审核结论记录前不要依据本批页面修改规则。',
            'urls': configured_urls,
        }
        write(context_path, context)

    if do_collect:
        config = read(ROOT / 'config/collection_blind.json')
        for target in config['targets']:
            result = collect(target, root=batch, excluded_entries=development_entries())
            write(batch / 'reports' / ('collection_' + target['name'] + '.json'), result)
            print(target['name'], 'added:', len(result['added']), 'errors:', len(result['errors']))

    samples = sorted((batch / 'samples').glob('*.html'))
    if not samples:
        statuses = []
        for path in sorted((batch / 'reports').glob('collection_*.json')):
            report = read(path)
            statuses.append('<section><h2>' + escape(path.stem) + '</h2><pre>'
                            + escape(json.dumps(report, ensure_ascii=False, indent=2)) + '</pre></section>')
        document = ('<!doctype html><html lang="zh-CN"><meta charset="utf-8"><title>冻结验证采集状态</title>'
                    '<style>body{max-width:900px;margin:32px auto;font:16px/1.7 system-ui}pre{white-space:pre-wrap}</style>'
                    '<h1>尚未获得可用于解析的样本</h1><p>查看下方采集记录。若页面需要浏览器渲染，请运行对应的动态页面捕获步骤；若 robots 拒绝访问，应更换来源，不要绕过限制。</p>'
                    + ''.join(statuses) + '</html>')
        (batch / 'reports/progress.html').write_text(document, encoding='utf-8')
        print('No usable samples; collection state saved to', batch / 'reports/progress.html')
        return

    comparisons = [analyze(path) for path in samples]
    write_reports(comparisons, batch / 'reports/comparison')
    manifest = read(batch / 'reports/collection_manifest.json')
    audit_path = batch / 'reports/ai_review.json'
    audits = {item['file']: item for item in read(audit_path)['pages']} if audit_path.exists() else {}
    visual_path = batch / 'reports/ai_visual_review.json'
    visual_audits = read(visual_path) if visual_path.exists() else {}
    pages = []
    known = development_entries()
    for path, comparison in zip(samples, comparisons):
        result = extract_file(path)
        snapshot = hashlib.sha256(path.read_bytes()).hexdigest()
        audit = audits.get(path.name)
        review_status, review_result = audit_page(result, snapshot, audit)
        entry = next((item for item in manifest if item['file'] == path.name), {})
        overlap = development_overlap(entry, snapshot, known)
        if overlap:
            review_status, review_result = 'development_overlap', {'reason': overlap}
        elif visual_audits.get('sample') == path.name and visual_audits.get('snapshot') == snapshot:
            review_status, review_result = 'needs_ocr', {
                'reason': 'AI 视觉审核确认图片承载正文；提取器当前只输出 DOM 导语，需 OCR 或图像文字合并后才能完整通过',
                'visual_body_blocks': len(visual_audits.get('body_blocks', [])),
            }
        pages.append({
            'file': path.name,
            'snapshot': snapshot,
            'url': next((entry['url'] for entry in manifest if entry['file'] == path.name), ''),
            'title': result['title'],
            'page_type': result['page_type'],
            'scope_method': result['scope_method'],
            'content': result['content'],
            'body_images': result.get('body_images', []),
            'needs_ocr_candidate': result.get('needs_ocr_candidate', False),
            'content_completeness': result.get('content_completeness', ''),
            'visual_review_status': ('complete' if visual_audits.get('sample') == path.name
                                     and visual_audits.get('snapshot') == snapshot else 'not_reviewed'),
            'comparison_status': comparison['status'],
            'review_status': review_status,
            'review_result': review_result,
            'warnings': result['warnings'],
        })
    write(batch / 'reports/pending_review.json', {
        'code_sha256': current_hashes,
        'note': '逐页审核绑定 HTML 快照；提取器分歧不是正确性标签。此批不自动修改规则或主 samples。',
        'pages': pages,
    })
    image_inventory = []
    for page in pages:
        for index, image in enumerate(page.get('body_images', []), 1):
            image_inventory.append({
                'file': page['file'], 'snapshot': page['snapshot'], 'url': page['url'],
                'image_order': index, 'src': image['src'], 'alt': image.get('alt', ''),
                'ocr_status': 'not_run',
                'note': '图片属于提取范围；图中文字尚未识别，不能视为正文已完整提取。',
            })
    write(batch / 'reports/image_inventory.json', {
        'note': '仅登记正文范围内的图片，不下载图片、不执行 OCR。',
        'images': image_inventory,
    })
    cards = []
    for page in pages:
        body = page['content'] or ('识别为列表页，未输出单篇正文。' if page['page_type'] == 'listing' else '正文为空，需重点审核。')
        cards.append(
            '<section><h2>' + escape(page['title'] or page['file']) + '</h2>'
            + '<p><a href="' + escape(page['url'], quote=True) + '">' + escape(page['url']) + '</a></p>'
            + '<p>' + escape(page['file']) + ' · ' + escape(page['page_type']) + ' · ' + escape(page['scope_method'])
            + ' · ' + escape(page['comparison_status']) + ' · 审核：' + escape(page['review_status']) + '</p>'
            + '<p>' + escape(page['review_result'].get('reason', '')) + '</p>'
            + '<p>图像审核：' + escape(page.get('visual_review_status', 'not_reviewed')) + '</p>'
            + '<p>' + escape('；'.join(page['warnings'])) + '</p>'
            + ('<p>正文图片：' + str(len(page.get('body_images', []))) + ' 张（当前不执行 OCR）</p><ol>'
               + ''.join('<li><a href="' + escape(image['src'] if image['src'].startswith(('https://', 'http://')) else 'https:' + image['src'], quote=True)
                         + '">' + escape(image.get('alt') or image['src']) + '</a></li>'
                         for image in page.get('body_images', [])) + '</ol>'
               if page.get('body_images') else '')
            + '<pre>' + escape(body) + '</pre></section>'
        )
    html = (
        '<!doctype html><html lang="zh-CN"><meta charset="utf-8"><title>陌生页面冻结验证</title>'
        '<style>body{max-width:1000px;margin:32px auto;padding:20px;font:16px/1.7 system-ui;color:#203040}'
        'section{border-top:1px solid #ccd3db;padding:20px 0}pre{white-space:pre-wrap;overflow-wrap:anywhere;font:inherit}</style>'
        '<h1>陌生页面冻结验证</h1><p>当前代码哈希已冻结。逐页审核状态显示在各页面标题下；不要先根据结果改规则。差异比较只提示分歧，不代表哪方正确。审核后再决定是否开新开发轮次。</p>'
        + ''.join(cards) + '</html>'
    )
    (batch / 'reports/progress.html').write_text(html, encoding='utf-8')
    print('Pages:', len(pages), '; audited pass:', sum(p['review_status'] == 'pass' for p in pages),
          '; pending:', sum(p['review_status'] == 'pending_ai_review' for p in pages),
          '; stale:', sum(p['review_status'] == 'stale' for p in pages),
          '; development overlap excluded:', sum(p['review_status'] == 'development_overlap' for p in pages),
          '; needs OCR:', sum(p['review_status'] == 'needs_ocr' for p in pages),
          '; fail:', sum(p['review_status'] == 'fail' for p in pages))
    print(batch / 'reports/progress.html')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--collect', action='store_true', help='按固定网址白名单采集两个此前提供的页面')
    parser.add_argument('--batch', type=Path, default=BATCH, help='独立验证批次目录；代码变化时请使用新目录')
    args = parser.parse_args()
    run(args.collect, args.batch.resolve())
