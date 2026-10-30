"""Serve frozen saved pages with their styles and a DOM-linked review overlay."""
from http.server import ThreadingHTTPServer, SimpleHTTPRequestHandler
from pathlib import Path
from urllib.parse import unquote, urlsplit, quote
import json
import hashlib
import threading
import argparse
from bs4 import BeautifulSoup

ROOT = Path(__file__).resolve().parent
SAVE_LOCK = threading.Lock()

def snapshot(path, origin='http://127.0.0.1:8765'):
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
    # A snapshot is review data: rerunning a site's JS may redirect, rewrite
    # document.body, insert ads or invalidate locators before detection starts.
    # Keep data scripts, styles and declarative shadow DOM, freeze executable JS.
    for node in soup.find_all('script'):
        if node.get('type', '').lower() not in ('application/json', 'application/ld+json'):
            node.decompose()
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
    head.append(soup.new_tag('meta', attrs={'name':'review-snapshot', 'content':hashlib.sha256(path.read_bytes()).hexdigest()}))
    # BeautifulSoup preserves template contents; the browser instantiates shadow roots.
    # An original <base href=https://...> also affects root-relative script URLs.
    script = soup.new_tag('script', src=origin+'/region_overlay.js')
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
        if path in ('/api/annotations', '/api/rules'):
            target = ROOT / ('reports/annotations.json' if path.endswith('annotations') else 'config/rules.json')
            with SAVE_LOCK:
                data = target.read_bytes() if target.exists() else (b'{}' if path.endswith('annotations') else b'[]')
            return self.send_bytes(data, 'application/json')
        if path.startswith('/snapshot/'):
            name = path[len('/snapshot/'):]
            if Path(name).name != name or not name.endswith('.html'):
                return self.send_error(400)
            page = ROOT / 'samples' / name
            if not page.is_file():
                return self.send_error(404)
            return self.send_bytes(snapshot(page, f'http://127.0.0.1:{self.server.server_port}'), 'text/html; charset=utf-8')
        return super().do_GET()

    def do_POST(self):
        endpoint = urlsplit(self.path).path
        if endpoint not in ('/api/annotations', '/api/rules'):
            return self.send_error(404)
        try:
            size = int(self.headers.get('Content-Length', '0'))
            if not 0 < size <= 20_000_000:
                raise ValueError('invalid payload size')
            payload = json.loads(self.rfile.read(size))
            if not isinstance(payload, dict) or not isinstance(payload.get('file'), str) or Path(payload['file']).name != payload['file']:
                raise ValueError('file is required')
            if not (ROOT / 'samples' / payload['file']).is_file():
                raise ValueError('unknown sample')
            if endpoint.endswith('rules'):
                if payload.get('label') not in ('body','noise') or not isinstance(payload.get('locator'), list) or not payload['locator'] or not all(isinstance(x,str) and x for x in payload['locator']):
                    raise ValueError('rule requires label body/noise and XPath locator array')
                targets = payload.get('files', [payload['file']])
                if not isinstance(targets, list) or not targets or any(not isinstance(n,str) or Path(n).name != n or not (ROOT/'samples'/n).is_file() for n in targets):
                    raise ValueError('files must list existing sample filenames')
            elif not isinstance(payload.get('regions'), list):
                raise ValueError('regions required')
            path = ROOT / ('config/rules.json' if endpoint.endswith('rules') else 'reports/annotations.json')
            path.parent.mkdir(exist_ok=True)
            with SAVE_LOCK:
                data = json.loads(path.read_text(encoding='utf-8')) if path.exists() else ([] if endpoint.endswith('rules') else {})
                if isinstance(data, list):
                    data.append(payload)
                else:
                    data[payload['file']] = payload
                temp = path.with_suffix('.tmp')
                temp.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding='utf-8')
                temp.replace(path)
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
    parser = argparse.ArgumentParser()
    parser.add_argument('--port', type=int, default=8765)
    args = parser.parse_args()
    try:
        server = ThreadingHTTPServer(('127.0.0.1', args.port), Handler)
    except OSError:
        # Leave existing services alone; a fresh port guarantees current code.
        server = ThreadingHTTPServer(('127.0.0.1', 0), Handler)
        print(f'Port {args.port} is occupied; using a new port.', flush=True)
    print(f'Open http://127.0.0.1:{server.server_port}/visual_review.html ; Ctrl+C to stop', flush=True)
    server.serve_forever()
