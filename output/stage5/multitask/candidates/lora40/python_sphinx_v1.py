import re
from lxml import etree

def extract(data):
    # Parse the XML data
    root = etree.fromstring(data)
    
    # Extract title
    title = root.xpath('//title/text()')[0]
    
    # Extract blocks
    blocks = []
    for node in root.xpath('//div[@class="body"]/following-sibling::*'):
        if node.tag == 'h1':
            kind = 'paragraph'
        elif node.tag == 'h2':
            kind = 'subheading'
        elif node.tag == 'caption':
            kind = 'caption'
        elif node.tag == 'table':
            kind = 'table'
        else:
            kind = 'unknown'
        
        text = node.text.strip()
        if text:
            blocks.append({
                'kind': kind,
                'text': text,
                'xpath': node.get('xpath', None)
            })
    
    # Extract metadata
    metadata = {}
    for node in root.xpath('//div[@class="body"]/following-sibling::*'):
        if node.tag == 'p':
            kind = 'paragraph'
        elif node.tag == 'h2':
            kind = 'subheading'
        elif node.tag == 'caption':
            kind = 'caption'
        elif node.tag == 'table':
            kind = 'table'
        else:
            kind = 'unknown'
        
        text = node.text.strip()
        if text:
            metadata[node.get('xpath', None)] = {
                'kind': kind,
                'text': text,
                'xpath': node.get('xpath', None)
            }
    
    # Extract excluded
    excluded = []
    for node in root.xpath('//div[@class="body"]/following-sibling::*'):
        if node.tag == 'p':
            kind = 'paragraph'
        elif node.tag == 'h2':
            kind = 'subheading'
        elif node.tag == 'caption':
            kind = 'caption'
        elif node.tag == 'table':
            kind = 'table'
        else:
            kind = 'unknown'
        
        text = node.text.strip()
        if text:
            excluded.append({
                'kind': kind,
                'text': text,
                'xpath': node.get('xpath', None)
            })
    
    # Extract warnings
    warnings = []
    for node in root.xpath('//div[@class="body"]/following-sibling::*'):
        if node.tag == 'p':
            kind = 'paragraph'
        elif node.tag == 'h2':
            kind = 'subheading'
        elif node.tag == 'caption':
            kind = 'caption'
        elif node.tag == 'table':
            kind = 'table'
        else:
            kind = 'unknown'
        
        text = node.text.strip()
        if text:
            warnings.append({
                'kind': kind,
                'text': text,
                'xpath': node.get('xpath', None)
            })
    
    return {
        'title': title,
        'blocks': blocks,
        'metadata': metadata,
        'excluded': excluded,
        'warnings': warnings
    }