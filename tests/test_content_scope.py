import tempfile
import unittest
from pathlib import Path
from extract import extract_file


class ContentScopeTests(unittest.TestCase):
    def run_page(self, source):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / 'page.html'
            path.write_text(source, encoding='utf-8')
            return extract_file(path)

    def test_short_op_list_excludes_replies_and_signature(self):
        result = self.run_page('<main><h1>帖子</h1><div id="floor-1"><div class="md-body"><p>短原帖。</p><ul><li>第一项</li><li>第二项</li></ul></div><div class="md-body signature-md">签名</div></div><div id="floor-2"><div class="md-body"><p>回复不能混入。</p></div></div></main>')
        self.assertEqual(result['page_type'], 'forum_post')
        self.assertEqual(result['content'].splitlines(), ['短原帖。', '第一项', '第二项'])

    def test_target_title_selects_article_not_longest_other_story(self):
        result = self.run_page('<title>目标文章</title><consumption-page><h1>其他文章</h1><article><p>' + '其他长文。'*100 + '</p></article></consumption-page><consumption-page><h1>目标文章</h1><article><p>目标短文。</p></article></consumption-page>')
        self.assertEqual(result['content'], '目标短文。')

    def test_ambiguous_multiple_articles_abstain(self):
        result = self.run_page('<title>站点</title><article><h1>文章甲</h1><p>甲</p></article><article><h1>文章乙</h1><p>乙</p></article>')
        self.assertEqual(result['content'], '')
        self.assertTrue(result['warnings'])

    def test_listing_not_empty_article(self):
        result = self.run_page('<h1 id="topic-list-heading">所有话题</h1><div>'+'话题摘要'*100+'</div>')
        self.assertEqual(result['extraction_status'], 'not_article')
        self.assertEqual(result['content'], '')

    def test_read_break_is_not_an_ad_but_ad_container_is(self):
        result = self.run_page('<article><p class="continue-read-break">续读正文不能丢失。</p><div class="ad-slot"><p>广告内容</p></div></article>')
        self.assertIn('续读正文不能丢失。', result['content'])
        self.assertNotIn('广告内容', result['content'])

    def test_topic_link_inside_article_is_not_narrative(self):
        result = self.run_page('<div id="artibody"><p><a href="/topic">专题：相关聚合页</a></p><p>专题：这里讨论专题的形成过程，属于叙述。</p></div>')
        self.assertNotIn('相关聚合页', result['content'])
        self.assertIn('专题的形成过程', result['content'])

    def test_editorial_blocks_preserve_short_text_exclude_recommendations(self):
        result = self.run_page('<main><p data-sticky-nav-anchor="true">短正文</p><h2>正文小标题</h2><section><h2>推荐文章</h2><p>推荐摘要</p></section></main>')
        self.assertEqual(result['content'].splitlines(), ['短正文', '正文小标题'])
