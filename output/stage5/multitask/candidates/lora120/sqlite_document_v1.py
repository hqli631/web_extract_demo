"""Reviewed teaching reference for SQLite static fancy-document layout."""
from lxml import html

def extract(data):
    tree = html.document_fromstring(data)
    bodies = tree.xpath("//div[contains(concat(' ',normalize-space(@class),' '),' fancy ')]")
    if len(bodies) != 1:
        raise ValueError('expected one SQLite fancy body')
    body = bodies[0]
    clean = lambda node: ' '.join(node.text_content().split())
    title = tree.xpath('//title')
    result = dict(title=clean(title[0]) if title else '', blocks=[], metadata=[], excluded=[], warnings=[])
    for node in body.xpath('.//p|.//h1|.//h2|.//h3|.//h4|.//pre|.//table|.//ul|.//ol|.//dl'):
        if node.xpath("ancestor::*[contains(concat(' ',normalize-space(@class),' '),' nosearch ')]|ancestor::pre|ancestor::table|ancestor::ul|ancestor::ol|ancestor::dl"):
            continue
        text = clean(node)
        if not text:
            continue
        item = dict(kind='subheading' if node.tag in {'h1','h2','h3','h4','dt'} else 'paragraph', text=text, xpath=tree.getroottree().getpath(node))
        if text.startswith('This page was last updated on '):
            item['kind'] = 'updated_at'
            result['metadata'].append(item)
            continue
        if node.tag == 'table':
            item.update(kind='table', rows=[[' '.join(cell.text_content().split()) for cell in row.xpath('./th|./td')] for row in node.xpath('.//tr')])
        result['blocks'].append(item)
    result['warnings'].append('static_dom_only_no_ocr_or_javascript; code_and_lists_classified_as_paragraph; whitespace_normalized')
    if body.xpath('.//img'):
        result['warnings'].append('images_present_pixels_not_extracted_completeness_unknown')
    return result