import unittest
import tempfile
from pathlib import Path
from run_news_validation import check_audit
from extract import extract_file


class NewsValidationTests(unittest.TestCase):
    def test_trailing_credits_are_metadata(self):
        result = self.run_page('<article><p>正常正文。</p><p>｜策划：张三</p><p>｜审校：李四</p><p>｜工作室出品</p></article>')
        self.assertEqual(result['content'], '正常正文。')

    def test_credit_words_and_mid_article_line_are_preserved(self):
        result = self.run_page('<article><p>本文讨论策划：如何审校。</p><p>｜策划：张三</p><p>随后开展新工作。</p></article>')
        self.assertIn('｜策划：张三', result['content'])
        self.assertIn('本文讨论策划', result['content'])

    def test_image_heavy_article_is_flagged(self):
        result = self.run_page('<article><p>导语。</p><img src="1.png"><img data-src="2.png"><img src="3.png"></article>')
        self.assertTrue(result['needs_ocr_candidate'])
        self.assertEqual(len(result['body_images']), 3)

    def test_sidebar_images_are_excluded(self):
        result = self.run_page('<article><p>正文。</p><aside><img src="ad.png"></aside></article>')
        self.assertEqual(result['body_images'], [])

    def run_page(self, source):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / 'page.html'
            path.write_text(source, encoding='utf-8')
            return extract_file(path)

    def test_snapshot_order_duplicates_and_contamination_are_checked(self):
        audit = {'snapshot': 'abc', 'body_blocks': ['甲', '甲', '乙'], 'excluded_blocks': ['广告']}
        self.assertEqual(check_audit({'content': '甲\n甲\n乙'}, 'abc', audit)['status'], 'pass')
        for text in ('甲\n乙', '乙\n甲\n甲', '甲\n甲\n乙\n广告'):
            self.assertEqual(check_audit({'content': text}, 'abc', audit)['status'], 'fail')
        self.assertEqual(check_audit({'content': '甲\n甲\n乙'}, 'new', audit)['status'], 'stale')
        self.assertEqual(check_audit({'content': '甲'}, 'abc', None)['status'], 'unreviewed')

    def test_news_scope_preserves_short_instructions_and_excludes_footer(self):
        result = self.run_page('<title>征求意见-中新网</title><div class="left_zw"><p>短正文</p><p>1、反馈意见。</p></div><div>' + '版权声明。'*40 + '</div>')
        self.assertEqual(result['content'], '短正文\n1、反馈意见。')

    def test_standalone_byline_and_source_do_not_drop_reporter_narrative(self):
        result = self.run_page('<article><p>21世纪经济报道记者 程雪溶</p><p>记者 李明 在现场了解到新的进展，居民仍在继续等待处理。</p><p>（文章来源：上海证券报）</p></article>')
        self.assertEqual(result['content'], '记者 李明 在现场了解到新的进展，居民仍在继续等待处理。')
