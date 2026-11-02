"""Download images referenced by one frozen validation sample, with strict bounds."""
import argparse
import hashlib
import json
from PIL import Image, ImageOps, ImageDraw
from pathlib import Path
from urllib.parse import urljoin, urlsplit
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parent
MAX_IMAGES = 20
MAX_BYTES = 5_000_000
ALLOWED_HOSTS = {'i2.chinanews.com.cn'}


def fetch(batch, filename):
    batch = Path(batch).resolve()
    if ROOT not in batch.parents:
        raise ValueError('Batch directory must be inside the project.')
    manifest_path = batch / 'reports/collection_manifest.json'
    manifest = json.loads(manifest_path.read_text(encoding='utf-8'))
    entry = next((item for item in manifest if item['file'] == filename), None)
    if not entry:
        raise ValueError('Sample not found in this batch manifest.')
    snapshot_path = batch / 'samples' / filename
    if hashlib.sha256(snapshot_path.read_bytes()).hexdigest() != entry['snapshot']:
        raise ValueError('Snapshot hash mismatch; refusing to fetch images.')
    inventory_path = batch / 'reports/image_inventory.json'
    inventory = json.loads(inventory_path.read_text(encoding='utf-8'))
    images = [item for item in inventory['images'] if item['file'] == filename]
    if len(images) > MAX_IMAGES:
        raise ValueError('Image count exceeds configured bound.')
    output = batch / 'images' / Path(filename).stem
    output.mkdir(parents=True, exist_ok=True)
    results = []
    for item in images:
        url = urljoin(entry['url'], item['src'])
        parsed = urlsplit(url)
        if parsed.scheme != 'https' or parsed.hostname not in ALLOWED_HOSTS:
            results.append({'image_order': item['image_order'], 'url': url, 'status': 'rejected_host'})
            continue
        try:
            request = Request(url, headers={'User-Agent': 'WebExtractLearning/1.0'})
            with urlopen(request, timeout=20) as response:
                if urlsplit(response.geturl()).hostname not in ALLOWED_HOSTS:
                    raise ValueError('Redirect outside image host allowlist')
                content_type = response.headers.get_content_type()
                if not content_type.startswith('image/'):
                    raise ValueError('Response is not an image')
                data = response.read(MAX_BYTES + 1)
                if len(data) > MAX_BYTES:
                    raise ValueError('Image exceeds 5MB bound')
                suffix = Path(parsed.path).suffix.lower()
                if suffix not in {'.jpg', '.jpeg', '.png', '.webp', '.gif'}:
                    suffix = '.image'
                target = output / f"{item['image_order']:02d}{suffix}"
                target.write_bytes(data)
                results.append({'image_order': item['image_order'], 'url': url,
                                'file': str(target.relative_to(batch)), 'bytes': len(data),
                                'content_type': content_type, 'sha256': hashlib.sha256(data).hexdigest(),
                                'status': 'downloaded'})
        except Exception as exc:
            results.append({'image_order': item['image_order'], 'url': url,
                            'status': 'failed', 'reason': str(exc)})
    report = {'sample': filename, 'snapshot': entry['snapshot'], 'images': results}
    downloaded = [item for item in results if item['status'] == 'downloaded']
    if downloaded:
        cell_w, cell_h, label_h = 360, 260, 34
        columns = 2
        rows = (len(downloaded) + columns - 1) // columns
        sheet = Image.new('RGB', (columns * cell_w, rows * (cell_h + label_h)), 'white')
        draw = ImageDraw.Draw(sheet)
        for position, item in enumerate(downloaded):
            with Image.open(batch / item['file']) as source:
                thumb = ImageOps.contain(source.convert('RGB'), (cell_w - 12, cell_h - 12))
            x = (position % columns) * cell_w + (cell_w - thumb.width) // 2
            y = (position // columns) * (cell_h + label_h) + (cell_h - thumb.height) // 2
            sheet.paste(thumb, (x, y))
            draw.text(((position % columns) * cell_w + 10,
                       (position // columns) * (cell_h + label_h) + cell_h),
                      f"Image {item['image_order']} - {item['bytes']:,} bytes", fill='black')
        preview = output / 'contact_sheet.jpg'
        sheet.save(preview, quality=88)
        report['contact_sheet'] = str(preview.relative_to(batch))
    target = batch / 'reports' / (Path(filename).stem + '_image_fetch.json')
    target.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
    return report


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--batch', type=Path, default=ROOT / 'validation_blind_round2')
    parser.add_argument('--file', default='collected_61b2572fd4c6cd0c.html')
    args = parser.parse_args()
    print(json.dumps(fetch(args.batch, args.file), ensure_ascii=False, indent=2))
