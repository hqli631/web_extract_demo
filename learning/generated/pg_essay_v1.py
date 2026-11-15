"""Reviewed teaching reference for legacy table/font essay HTML including br tails."""
from lxml import html

def extract(data):
    tree = html.document_fromstring(data)
    bodies = tree.xpath("//td[@width='435']/font[@size='2' and @face='verdana']")
    if len(bodies) != 1:
        raise ValueError('expected one legacy essay font container')
    body = bodies[0]
    title = tree.xpath('//title')
    result = dict(title=' '.join(title[0].text_content().split()) if title else '', blocks=[], metadata=[], excluded=[], warnings=[])
    chunks = []
    def flush():
        text = ' '.join(''.join(chunks).split())
        if text:
            result['blocks'].append(dict(kind='paragraph',text=text,xpath=tree.getroottree().getpath(body)))
        chunks.clear()
    def visit(node):
        if node.tag in {'script','style','table'}:
            text = ' '.join(node.text_content().split())
            if text:
                result['excluded'].append(dict(kind='promotion_or_widget',text=text,xpath=tree.getroottree().getpath(node)))
            return
        if node.tag in {'p','blockquote','br','hr'}:
            flush()
        if node.text:
            chunks.append(node.text)
        for child in node:
            if isinstance(child.tag,str):
                visit(child)
            if child.tail:
                chunks.append(child.tail)
        if node.tag in {'p','blockquote'}:
            flush()
    visit(body)
    flush()
    result['warnings'].append('static_dom_only_no_ocr_or_javascript; container_xpath_evidence_for_text_segments; dates_and_notes_kept_in_body; legacy_br_segmentation_heuristic')
    if body.xpath('.//img'):
        result['warnings'].append('images_present_pixels_not_extracted_completeness_unknown')
    return result
