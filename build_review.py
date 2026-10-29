from pathlib import Path

ROOT = Path(__file__).resolve().parent
OUTPUT = ROOT / 'output'
OUTPUT.mkdir(exist_ok=True)
ENTRY = '''<!doctype html><meta charset="utf-8"><title>区域复核入口</title>
<p>原网页定位复核需要本地服务。请运行 start_review.ps1 后打开
<a href="http://127.0.0.1:8765/visual_review.html">原网页区域复核</a>。</p>
<script>if(location.protocol!=="file:")location.replace("/visual_review.html");</script>'''
(OUTPUT / 'review.html').write_text(ENTRY, encoding='utf-8')
print('output/review.html ready: use http://127.0.0.1:8765/visual_review.html')
