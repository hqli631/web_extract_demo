"""Reviewed teaching reference for static Python Sphinx document layout."""
from lxml import html

def extract(data):
    tree = html.document_fromstring(data)
    bodies = tree.xpath("//div[@role='main' and contains(concat(' ',normalize-space(@class),' '),' body ')]")
    if len(bodies) != 1:
        raise ValueError('expected one Sphinx main body')
    body = bodies[0]
    titles = body.xpath('.//h1')
    if len(titles) != 1:
        raise ValueError('expected one h1')
    clean = lambda node: ' '.join(node.text_content().replace('¶','').split())
    result = dict(title=clean(titles[0]), blocks=[], metadata=[], excluded=[], warnings=[])
    for node in body.xpath('.//p|.//h2|.//h3|.//h4|.//pre|.//table|.//ul|.//ol|.//dl'):
        if node.xpath('ancestor::pre|ancestor::table|ancestor::ul|ancestor::ol|ancestor::dl'):
            continue
        text = clean(node)
        if not text:
            continue
        item = dict(kind='subheading' if node.tag in {'h2','h3','h4','dt'} else 'paragraph', text=text, xpath=tree.getroottree().getpath(node))
        if node.tag == 'table':
            item.update(kind='table', rows=[[' '.join(cell.text_content().split()) for cell in row.xpath('./th|./td')] for row in node.xpath('.//tr')])
        result['blocks'].append(item)
    result['warnings'].append('static_dom_only_no_ocr_or_javascript; code_and_lists_classified_as_paragraph; whitespace_normalized')
    if body.xpath('.//img'):
        result['warnings'].append('images_present_pixels_not_extracted_completeness_unknown')
    return result
