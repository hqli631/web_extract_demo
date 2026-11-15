"""Current-conversation AI candidate v1; static Sina article shell only."""
import re
from lxml import html


def extract(data):
    tree = html.document_fromstring(data)
    titles = tree.xpath("//h1[contains(concat(' ',normalize-space(@class),' '),' main-title ')]")
    bodies = tree.xpath("//div[@id='artibody']")
    if len(titles) != 1 or len(bodies) != 1:
        raise ValueError('expected one main-title and one artibody')
    body = bodies[0]
    result = dict(title=' '.join(titles[0].text_content().split()), blocks=[], metadata=[], excluded=[], warnings=[])

    def record(node, kind):
        clone = html.fromstring(html.tostring(node))
        for junk in clone.xpath('.//script|.//style|.//noscript'):
            junk.drop_tree()
        return dict(kind=kind, text=' '.join(clone.text_content().split()), xpath=tree.getroottree().getpath(node))

    def visit(node):
        if not isinstance(node.tag, str) or node.tag in {'script','style','noscript'}:
            return
        classes = set((node.get('class') or '').split())
        item = record(node, 'paragraph')
        text = item['text']
        if 'appendQr_wrap' in classes or node.get('id') == 'app-kaihu-stock':
            item['kind'] = 'promotion'
            result['excluded'].append(item)
            return
        if 'article-editor' in classes:
            item['kind'] = 'editor'
            result['metadata'].append(item)
            return
        if node.tag == 'p' and text.startswith('专题：') and node.xpath('.//a'):
            item['kind'] = 'topic_navigation'
            result['excluded'].append(item)
            return
        if node.tag == 'p' and re.fullmatch(r'[（(]?文章来源[:：].+?[）)]?', text):
            item['kind'] = 'source'
            result['metadata'].append(item)
            return
        if node.tag == 'table':
            rows = [[' '.join(c.text_content().split()) for c in r.xpath('./td|./th')]
                    for r in node.xpath('.//tr')]
            if text:
                item.update(kind='table', rows=rows)
                result['blocks'].append(item)
            return
        if node.tag in {'p','h2','h3','h4','li','figcaption'} or 'pictext' in classes:
            if text:
                item['kind'] = ('caption' if node.tag=='figcaption' or 'pictext' in classes else
                                'subheading' if node.tag.startswith('h') or 'align-Center' in (node.get('cms-style') or '').split() else 'paragraph')
                result['blocks'].append(item)
            return
        for child in node:
            visit(child)
        if text and not len(node):
            result['warnings'].append('unhandled_text_node:'+item['xpath'])

    for node in body:
        visit(node)
    result['warnings'].append('static_dom_only_no_css_visibility_javascript_or_ocr')
    if body.xpath('.//img'):
        result['warnings'].append('images_present_pixels_not_extracted')
    return result
