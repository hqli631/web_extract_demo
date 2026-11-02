"""Compose a separate DOM + OCR candidate with source provenance, never a pass label."""
import argparse
import hashlib
import json
from html import escape
from pathlib import Path

from bs4 import BeautifulSoup
from extract import extract_file, prepare_html
from review_source import marked_source

ROOT = Path(__file__).resolve().parent


def compose(sample, extracted, soup, ocr, fetched):
    digest = hashlib.sha256(sample.read_bytes()).hexdigest()
    if any(report.get('sample') != sample.name or report.get('snapshot') != digest
           for report in (ocr, fetched)):
        raise ValueError('HTML snapshot or sample mismatch; rerun OCR for this snapshot')
    orders = [item['image_order'] for item in ocr['images']]
    expected_orders = list(range(1, len(extracted['body_images']) + 1))
    if sorted(orders) != expected_orders or len(orders) != len(set(orders)):
        raise ValueError('OCR image coverage does not match extracted body images')
    downloads = {item['image_order']: item for item in fetched['images']}
    events = []
    issues = []
    for region in extracted['regions']:
        if region['auto_label'] not in {'正文候选', '标题/小标题'}:
            continue
        node = soup.find(attrs={'data-review-node': region['source_node']})
        if node is None:
            raise ValueError('Cannot locate extracted region in snapshot')
        if node.find('img'):
            issues.append('文本区域内含图片，区域内部先后顺序待确认：' + str(region['source_node']))
        events.append({'source': 'dom', 'source_node': region['source_node'],
                       'position': int(region['source_node']), 'text': region['text']})
    for order, image in enumerate(extracted['body_images'], 1):
        nodes = [node for node in soup.find_all('img') if (
            node.get('data-src') or node.get('data-original') or node.get('src')) == image['src']]
        if len(nodes) != 1:
            issues.append('正文图片不能唯一定位：' + str(order))
            continue
        item = next(item for item in ocr['images'] if item['image_order'] == order)
        download = downloads.get(order, {})
        # Bind order to the snapshot image URL and downloaded bytes, not just a filename.
        from urllib.parse import urljoin
        manifest_url = fetched.get('source_url', '')
        actual_url = download.get('url', '')
        expected_url = urljoin(manifest_url, image['src'])
        if expected_url.startswith('//'):
            expected_url = 'https:' + expected_url
        if actual_url != expected_url:
            raise ValueError('Image URL/order mismatch')
        local_path = (sample.parent.parent / download.get('file', '')).resolve()
        batch = sample.parent.parent.resolve()
        if (download.get('status') != 'downloaded' or batch not in local_path.parents
                or not local_path.is_file()):
            issues.append('图片文件不可用：' + str(order))
            continue
        image_hash = hashlib.sha256(local_path.read_bytes()).hexdigest()
        if image_hash != download.get('sha256') or image_hash != item.get('image_sha256'):
            issues.append('图片哈希或 OCR 来源失效：' + str(order))
            continue
        if item.get('status') != 'ok' or item.get('layout_status') != 'applied' or not item.get('body_candidate'):
            issues.append('图片尚无匹配版式的正文候选：' + str(order))
            continue
        node = nodes[0]
        events.append({'source': 'ocr', 'source_node': node['data-review-node'],
                       'position': int(node['data-review-node']), 'image_order': order,
                       'image_sha256': image_hash, 'text': item['body_candidate'],
                       'low_confidence_lines': len(item.get('low_confidence_body_lines', []))})
    events.sort(key=lambda event: event['position'])
    return {'sample': sample.name, 'snapshot': digest, 'status': 'blocked' if issues else 'candidate_unverified',
            'issues': issues, 'blocks': events,
            'content_candidate': '\n\n'.join(event['text'] for event in events),
            'note': '独立候选，未改写原提取正文；OCR 错字尚未校正，不能计为审核通过。'}


def run(batch, filename):
    batch = Path(batch).resolve()
    if Path(filename).name != filename:
        raise ValueError('Invalid sample name')
    sample = batch / 'samples' / filename
    read = lambda path: json.loads(path.read_text(encoding='utf-8'))
    ocr = read(batch / 'reports' / (sample.stem + '_ocr.json'))
    fetched = read(batch / 'reports' / (sample.stem + '_image_fetch.json'))
    manifest = read(batch / 'reports/collection_manifest.json')
    entry = next(item for item in manifest if item['file'] == filename)
    fetched = dict(fetched, source_url=entry['url'])
    soup = BeautifulSoup(prepare_html(str(marked_source(sample.read_text(encoding='utf-8')))), 'lxml')
    result = compose(sample, extract_file(sample), soup, ocr, fetched)
    output = batch / 'reports' / (sample.stem + '_combined_candidate.json')
    output.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding='utf-8')
    cards = ''.join('<section><h2>%s · 节点 %s</h2><pre>%s</pre></section>' % (
        escape(block['source']), escape(str(block['source_node'])), escape(block['text'])) for block in result['blocks'])
    report = output.with_suffix('.html')
    report.write_text('<!doctype html><html lang="zh-CN"><meta charset="utf-8"><title>DOM 与 OCR 正文候选</title>'
                      '<style>body{max-width:950px;margin:32px auto;padding:16px;font:16px/1.7 sans-serif}'
                      'pre{white-space:pre-wrap}section{border-top:1px solid #ccc}</style>'
                      '<h1>DOM 与 OCR 正文候选</h1><p>' + escape(result['status']) + '：' + escape(result['note'])
                      + '</p><p>' + escape('；'.join(result['issues'])) + '</p>'
                      + '<p><a href="' + escape(sample.stem + '_ocr.html', quote=True) + '">查看原图检测框与 OCR 明细</a></p>'
                      + cards + '</html>', encoding='utf-8')
    return result, report


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--batch', type=Path, default=ROOT / 'validation_blind_round2')
    parser.add_argument('--file', default='collected_61b2572fd4c6cd0c.html')
    args = parser.parse_args()
    result, report = run(args.batch, args.file)
    print(result['status'], 'blocks:', len(result['blocks']), 'issues:', len(result['issues']))
    print(report)
