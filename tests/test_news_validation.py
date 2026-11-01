import unittest
import tempfile
from pathlib import Path
from run_news_validation import check_audit
from extract import extract_file


class NewsValidationTests(unittest.TestCase):
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
