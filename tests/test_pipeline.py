import hashlib
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
from pathlib import Path
import sys
import tempfile
import threading
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from collect_pages import collect
from evaluate import evaluate


class PipelineTests(unittest.TestCase):
    def test_evaluation_requires_review_and_matching_snapshot(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            (root/'samples').mkdir()
            (root/'samples/a.html').write_bytes(b'example')
            page = {'snapshot':hashlib.sha256(b'example').hexdigest(), 'regions':[
                {'label':'body','auto_label':'noise','predicted_label':'body','reviewed':True},
                {'label':'noise','auto_label':'body','predicted_label':'body','reviewed':True},
                {'label':'body','auto_label':'body','predicted_label':'body','reviewed':False},
                {'label':'pending','auto_label':'body','predicted_label':'body','reviewed':True}]}
            report = evaluate({'a.html':page},root)
            self.assertEqual(report['reviewed'],2)
            self.assertEqual(report['baseline']['fn'],1)
            self.assertEqual(report['rules']['fp'],1)
            self.assertEqual(report['rules']['recall'],1)
            page['snapshot']='stale'
            self.assertEqual(evaluate({'a.html':page},root)['reviewed'],0)

    def test_collection_bounds_discovery_dedup_and_repeated_seed(self):
        visited=[]
        class Site(BaseHTTPRequestHandler):
            def log_message(self,*args): pass
            def do_GET(self):
                visited.append(self.path)
                self.send_response(200)
                self.send_header('Content-Type','text/plain' if self.path=='/robots.txt' else 'text/html')
                self.end_headers()
                content='User-agent: *\nDisallow: /blocked' if self.path=='/robots.txt' else ('<a href="/story/1">one</a><a href="/story/2">dup</a><a href="/blocked">blocked</a><a href="https://outside.invalid/a">outside</a>' if self.path=='/' else '<article><p>'+('body paragraph '*40)+'</p></article>')
                self.wfile.write(content.encode())
        server=ThreadingHTTPServer(('127.0.0.1',0),Site)
        thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
        try:
            with tempfile.TemporaryDirectory() as folder:
                root=Path(folder)
                config={'seeds':[f'http://127.0.0.1:{server.server_port}/'],'allowed_domains':['127.0.0.1'],'article_url_pattern':'/story/','max_pages':5,'max_fetches':10,'max_depth':1,'delay_seconds':0.1}
                report=collect(config,root)
                self.assertEqual(len(report['added']),1)
                self.assertNotIn('/blocked',visited)
                self.assertEqual(report['attempts'],4)
                self.assertTrue((root/'samples'/report['added'][0]['file']).exists())
                self.assertEqual(len(collect(config,root)['added']),0)
                self.assertEqual(len(collect(config,root,dry_run=True)['seeds']),1)
                config['discovery_url_pattern']='/story/'
                focused=collect(config,root)
                self.assertEqual(focused['attempts'],3)
                self.assertEqual(len(focused['added']),0)
                self.assertTrue(any(x['reason']=='duplicate_content' for x in focused['skipped']))
        finally:
            server.shutdown();server.server_close();thread.join()


if __name__ == '__main__': unittest.main()
