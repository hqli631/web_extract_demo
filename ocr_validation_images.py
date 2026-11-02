"""Run optional local OCR on previously downloaded validation images."""
import argparse
import hashlib
import html
import json
import re
from difflib import SequenceMatcher
from pathlib import Path

ROOT = Path(__file__).resolve().parent


def compare(reference, actual):
    if not reference:
        return None
    normalize = lambda text: re.sub(r'\s+', '', text)
    return round(SequenceMatcher(None, normalize(reference), normalize(actual), autojunk=False).ratio(), 4)


def run(batch, sample, engine):
    batch = Path(batch).resolve()
    if Path(sample).name != sample:
        raise ValueError('Invalid sample name')
    fetch_report = batch / 'reports' / (Path(sample).stem + '_image_fetch.json')
    fetch = json.loads(fetch_report.read_text(encoding='utf-8'))
    snapshot = batch / 'samples' / sample
    if fetch.get('sample') != sample or hashlib.sha256(snapshot.read_bytes()).hexdigest() != fetch.get('snapshot'):
        raise ValueError('Sample name or snapshot does not match image report')
    reference_path = batch / 'reports' / 'ai_visual_review.json'
    reference = json.loads(reference_path.read_text(encoding='utf-8')) if reference_path.exists() else {}
    blocks = reference.get('body_blocks', [])[1:] if (reference.get('sample') == sample and
              reference.get('snapshot') == fetch['snapshot']) else []
    records = []
    for item in sorted(fetch['images'], key=lambda entry: entry['image_order']):
        order = item['image_order']
        record = {'image_order': order, 'file': item.get('file'), 'status': 'failed'}
        try:
            if item.get('status') != 'downloaded':
                raise ValueError('Image was not downloaded')
            image = (batch / item['file']).resolve()
            if batch not in image.parents:
                raise ValueError('Image path outside batch')
            if hashlib.sha256(image.read_bytes()).hexdigest() != item.get('sha256'):
                raise ValueError('Image hash changed')
            lines, _ = engine(str(image))
            lines = lines or []
            text = '\n'.join(line[1] for line in lines)
            scores = [float(line[2]) for line in lines]
            ref = blocks[order - 1] if 0 < order <= len(blocks) else ''
            record.update(status='ok' if text else 'empty', text=text,
                          line_count=len(lines), min_confidence=round(min(scores), 4) if scores else None,
                          reference_similarity=compare(ref, text))
        except Exception as exc:
            record['reason'] = str(exc)
        records.append(record)
    result = {'sample': sample, 'snapshot': fetch['snapshot'], 'engine': 'RapidOCR ONNX',
              'note': 'OCR output is unverified and is not automatically merged into extracted body.',
              'reference_note': 'Similarity compares against uncorrected AI visual transcription; it is not ground-truth accuracy.',
              'images': records}
    output = batch / 'reports' / (Path(sample).stem + '_ocr.json')
    output.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding='utf-8')
    rows = []
    for item in records:
        rows.append('<section><h2>图片 %s · %s</h2><p>最低行置信度：%s；参考文本相似度：%s</p><pre>%s</pre></section>' % (
            item['image_order'], html.escape(item['status']), item.get('min_confidence'),
            item.get('reference_similarity'), html.escape(item.get('text', item.get('reason', '')))))
    report = output.with_suffix('.html')
    report.write_text('<!doctype html><html lang="zh-CN"><meta charset="utf-8"><title>图片 OCR 结果</title>'
                      '<style>body{max-width:960px;margin:2rem auto;font:16px/1.6 sans-serif;padding:0 1rem}'
                      'section{border-top:1px solid #aaa}pre{white-space:pre-wrap}</style>'
                      '<h1>图片 OCR 结果</h1><p>识别文字尚未校对，未自动合并到正文。相似度基于未经人工校对的 AI 视觉参考，不是准确率。</p>'
                      + ''.join(rows) + '</html>', encoding='utf-8')
    return result, report


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--batch', type=Path, default=ROOT / 'validation_blind_round2')
    parser.add_argument('--file', default='collected_61b2572fd4c6cd0c.html')
    args = parser.parse_args()
    try:
        from rapidocr_onnxruntime import RapidOCR
    except ImportError:
        parser.exit(2, 'Install optional OCR dependency: python -m pip install -r requirements-ocr.txt\n')
    result, report = run(args.batch, args.file, RapidOCR())
    print('Images:', len(result['images']), 'successful:', sum(i['status'] == 'ok' for i in result['images']))
    print(report)
