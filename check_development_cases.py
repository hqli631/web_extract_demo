"""Recheck reviewed cases after changes; never overwrite frozen validation."""
import hashlib
from html import escape
from extract import extract_file
from run_blind_validation import ROOT, BATCH, read, write, audit_page, code_hashes


def run():
    pages = []
    for audit in read(BATCH / 'reports/ai_review.json')['pages']:
        path = BATCH / 'samples' / audit['file']
        result = extract_file(path)
        status, details = audit_page(result, hashlib.sha256(path.read_bytes()).hexdigest(), audit)
        pages.append(dict(file=path.name, status=status, details=details,
                          content=result['content'], warnings=result['warnings'],
                          body_images=result['body_images'], needs_ocr_candidate=result['needs_ocr_candidate']))
    destination = ROOT / 'reports/development_cases'
    write(destination / 'results.json', dict(note='开发回归，复用已审核页面，不是独立验证准确率',
                                            code_sha256=code_hashes(), pages=pages))
    cards = ''.join('<section><h2>' + escape(p['file']) + ' · ' + p['status'] + '</h2><p>'
                    + escape('；'.join(p['warnings'])) + '</p><p>正文图片数：' + str(len(p['body_images']))
                    + '</p><pre>' + escape(p['content']) + '</pre></section>' for p in pages)
    (destination / 'progress.html').write_text('<!doctype html><meta charset="utf-8"><title>开发回归</title>'
        '<style>body{max-width:1000px;margin:32px auto;font:16px/1.7 system-ui}pre{white-space:pre-wrap}section{border-top:1px solid #ccc}</style>'
        '<h1>开发回归</h1><p>使用已审核页面检查修改效果，不代表独立验证准确率。旧冻结报告保留。</p>' + cards, encoding='utf-8')
    for page in pages:
        print(page['file'], page['status'], 'images:', len(page['body_images']))
    if any(p['status'] in {'fail', 'stale', 'pending_ai_review'} for p in pages):
        raise SystemExit(1)


if __name__ == '__main__':
    run()
