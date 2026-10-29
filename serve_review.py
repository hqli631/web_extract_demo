"""Serve frozen saved pages with their styles and a DOM-linked review overlay."""
from http.server import ThreadingHTTPServer, SimpleHTTPRequestHandler
from pathlib import Path
from urllib.parse import unquote, urlsplit, quote
import json
from bs4 import BeautifulSoup

ROOT = Path(__file__).resolve().parent

def snapshot(path):
    soup = BeautifulSoup(path.read_bytes(), 'html.parser')
    # Saved while scrolled: the site's JS would normally reset this sticky state
    # at scrollTop=0. Frozen snapshots must reset it explicitly instead.
    for node in soup.select('#top_bar.top-bar-fixed'):
        node['class'] = [c for c in node.get('class', []) if c != 'top-bar-fixed']
        node['data-isfix'] = '0'
    # Browser-saved MSN files encode Chinese download suffixes differently in
    # HTML and on disk (e.g. .���� vs .下载). Repair local resource URLs so
    # custom elements can render instead of leaving an empty skeleton.
    asset_dir = path.parent / (path.stem + '_files')
    if asset_dir.is_dir():
        files = list(asset_dir.iterdir())
        def repair(value):
            if not value or not value.startswith('./'):
                return value
            name = Path(value[2:]).name
            exact = asset_dir / name
            if exact.exists():
                return '/samples/' + quote(asset_dir.name) + '/' + quote(exact.name)
            prefix = name.split('.')[0]
            candidates = [f for f in files if f.name.split('.')[0] == prefix]
            return '/samples/' + quote(asset_dir.name) + '/' + quote(candidates[0].name) if len(candidates) == 1 else value
        for node in soup.find_all(['script', 'link', 'img', 'source']):
            for attr in ('src', 'href'):
                if node.get(attr): node[attr] = repair(node[attr])
    # Keep saved application bundles: MSN's custom elements and layout are
    # created by these local scripts. The review overlay is injected later.
    for node in soup.find_all('iframe'):
        # Embedded saved widgets must not restart their original application JS.
        node['sandbox'] = ''
    for node in soup.find_all('meta'):
        if node.get('http-equiv', '').lower() in ('content-security-policy', 'refresh'):
            node.decompose()
    for node in soup.find_all(True):
        for key in list(node.attrs):
            if key.lower().startswith('on'):
                del node[key]
    old_base = soup.find('base')
    source_base = old_base.get('href', '') if old_base else ''
    for node in soup.find_all('base'):
        node.decompose()
    head = soup.head
    if head is None:
        head = soup.new_tag('head')
        soup.insert(0, head)
    base = soup.new_tag('base', href=source_base if source_base.startswith(('https://', 'http://')) else '/samples/')
    head.insert(0, base)
    # BeautifulSoup preserves template contents; the browser instantiates shadow roots.
    script = soup.new_tag('script', src='/region_overlay.js')
    (soup.body or soup).append(script)
    return str(soup).encode('utf-8')

class Handler(SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=str(ROOT), **kwargs)

    def do_GET(self):
        path = unquote(urlsplit(self.path).path)
        if path == '/api/pages':
            data = json.dumps([p.name for p in sorted((ROOT / 'samples').glob('*.html'))]).encode()
            return self.send_bytes(data, 'application/json')
        if path.startswith('/snapshot/'):
            name = path[len('/snapshot/'):]
            if Path(name).name != name or not name.endswith('.html'):
                return self.send_error(400)
            page = ROOT / 'samples' / name
            if not page.is_file():
                return self.send_error(404)
            return self.send_bytes(snapshot(page), 'text/html; charset=utf-8')
        return super().do_GET()

    def do_POST(self):
        if urlsplit(self.path).path != '/api/annotations':
            return self.send_error(404)
        try:
            size = int(self.headers.get('Content-Length', '0'))
            payload = json.loads(self.rfile.read(size))
            if not isinstance(payload, dict) or not isinstance(payload.get('file'), str):
                raise ValueError('file is required')
            path = ROOT / 'reports' / 'annotations.json'
            path.parent.mkdir(exist_ok=True)
            data = json.loads(path.read_text(encoding='utf-8')) if path.exists() else {}
            data[payload['file']] = payload
            path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding='utf-8')
            return self.send_bytes(json.dumps({'ok': True}).encode(), 'application/json')
        except Exception as exc:
            return self.send_error(400, str(exc))

    def send_bytes(self, data, content_type):
        self.send_response(200)
        self.send_header('Content-Type', content_type)
        self.send_header('Content-Length', str(len(data)))
        self.send_header('Cache-Control', 'no-store')
        self.end_headers()
        self.wfile.write(data)

if __name__ == '__main__':
    print('Open http://127.0.0.1:8765/visual_review.html ; Ctrl+C to stop', flush=True)
    ThreadingHTTPServer(('127.0.0.1', 8765), Handler).serve_forever()
