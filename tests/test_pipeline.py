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
from compare_extractors import compare_page, write_reports
from extract import extract_file
from dom_evidence import build_index, find_evidence, make_queue


class PipelineTests(unittest.TestCase):
    def test_dom_evidence_preserves_shadow_boundaries_and_duplicate_matches(self):
        source = '<html><body><x-story><template shadowrootmode="open"><article><p>同一个段落正文</p><p>同一个段落正文</p></article></template></x-story><template><p>隐藏模板</p></template></body></html>'
        index = build_index(source)
        evidence = find_evidence('同一个段落正文', index)
        self.assertEqual(len(evidence), 2)
        self.assertEqual(len(evidence[0]['locator']), 2)
        self.assertNotIn('template', evidence[0]['locator'][1])
        self.assertIn('template', evidence[0]['source_xpath'])
        self.assertEqual(find_evidence('隐藏模板', index), [])
        result = {'file':'test.html','snapshot':'hash','current_chars':20,'baseline_chars':10,
                  'current_only':['同一个段落正文'],'baseline_only':[]}
        queue = make_queue(result, source)
        self.assertEqual(queue[0]['match_status'], 'ambiguous')
        self.assertFalse(queue[0]['enabled'])
        self.assertFalse(queue[0]['reviewed'])
        result['baseline_chars'] = 0
        self.assertEqual(make_queue(result, source)[0]['action'], 'diagnose_extractor')

    def test_captured_nested_shadow_templates_expose_article_text(self):
        from extract import prepare_html
        from bs4 import BeautifulSoup
        text = '这是实际保存的文章段落。' * 20
        html = f'<html><body><custom-app><template shadowrootmode="open"><article><custom-text><template shadowrootmode="open"><p>{text}</p></template></custom-text></article></template></custom-app><template><p>未启用的模板不可抽取</p></template></body></html>'
        prepared = prepare_html(html)
        self.assertIn(text, BeautifulSoup(prepared, 'lxml').get_text())
        self.assertNotIn('未启用的模板不可抽取', prepared)
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / 'shadow.html'
            path.write_text(html, encoding='utf-8')
            self.assertIn(text, extract_file(path)['content'])

    def test_navigation_ancestor_excluded_without_dropping_article_header(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / 'article.html'
            navigation = '导航链接内容' * 30
            body = '这里是文章正文内容。' * 20
            path.write_text(f'<html><body class="sidebar-enabled"><header><div>{navigation}</div></header><nav><div>{navigation}</div></nav><article><header><h1>文章标题</h1></header><p>{body}</p></article></body></html>', encoding='utf-8')
            result = extract_file(path)
            self.assertNotIn(navigation, result['content'])
            self.assertNotIn('文章标题', result['content'])
            self.assertTrue(any(r['text'] == '文章标题' and r['auto_label'] == '元数据' for r in result['regions']))
            self.assertIn(body, result['content'])

    def test_partial_matches_do_not_hide_missing_text_and_similarity_is_symmetric(self):
        a = compare_page('a', ['short sentence'], 'short sentence followed by missing article paragraphs')
        b = compare_page('b', ['short sentence followed by missing article paragraphs'], 'short sentence')
        self.assertTrue(a['baseline_only'])
        self.assertTrue(b['current_only'])
        self.assertEqual(a['similarity_estimate'], b['similarity_estimate'])
        self.assertLessEqual(a['similarity_estimate'], 1)

    def test_list_markers_are_formatting_but_real_missing_items_remain(self):
        result = compare_page('list.html', ['第一项', '第二项', '-10摄氏度'], '- 第一项\n* 第二项\n-10摄氏度\n- 第三项')
        self.assertEqual(result['current_only'], [])
        self.assertEqual(result['baseline_only'], ['第三项'])

    def test_error_reports_render_and_html_escapes_source_text(self):
        with tempfile.TemporaryDirectory() as folder:
            result = compare_page('a.html', ['<script>unsafe</script>'], 'different')
            result['current_text'] = '<script>unsafe</script>'
            result['baseline_text'] = 'different'
            write_reports([{'file':'bad.html','error':'failed'}, result], Path(folder))
            document = (Path(folder) / 'extractor_comparison.html').read_text(encoding='utf-8')
            self.assertIn('failed', document)
            self.assertNotIn('<script>unsafe</script>', document)
            self.assertIn('&lt;script&gt;', document)

    def test_extractor_comparison_reports_page_level_disagreements(self):
        result = compare_page(
            'article.html',
            ['the actual article paragraph', 'a recommendation block'],
            'the actual article paragraph\n\na missing final paragraph',
        )
        self.assertEqual(result['current_only'], ['a recommendation block'])
        self.assertEqual(result['baseline_only'], ['a missing final paragraph'])
        self.assertGreater(result['similarity_estimate'], 0)

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
                root=Path(folder)/'new_collection_root'
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
