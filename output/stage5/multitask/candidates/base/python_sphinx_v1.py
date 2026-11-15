import re
from lxml import etree

def extract(data: bytes) -> dict:
    # Parse the XML data
    root = etree.fromstring(data)
    
    # Extract title
    title = root.find('.//title').text.strip()
    
    # Extract blocks
    blocks = []
    for child in root.findall('.//div[@class="body"]/div'):
        kind = child.find('.//span[@class="section-number"]').text.strip()
        text = child.text.strip()
        if kind == 'paragraph':
            blocks.append({'kind': kind, 'text': text})
        elif kind == 'subheading':
            blocks.append({'kind': kind, 'text': text})
        elif kind == 'caption':
            blocks.append({'kind': kind, 'text': text})
        elif kind == 'table':
            rows = []
            for row in child.findall('.//tr'):
                cells = []
                for cell in row.findall('.//td'):
                    cells.append(cell.text.strip())
                rows.append(cells)
            blocks.append({'kind': kind, 'text': text, 'rows': rows})
    
    # Extract metadata
    metadata = {}
    for child in root.findall('.//div[@class="body"]/div'):
        kind = child.find('.//span[@class="section-number"]').text.strip()
        text = child.text.strip()
        if kind == 'author':
            metadata['author'] = text.strip()
        elif kind == 'editor':
            metadata['editor'] = text.strip()
        elif kind == 'source':
            metadata['source'] = text.strip()
        elif kind == 'production_credit':
            metadata['production_credit'] = text.strip()
    
    # Extract excluded
    excluded = {}
    for child in root.findall('.//div[@class="body"]/div'):
        kind = child.find('.//span[@class="section-number"]').text.strip()
        text = child.text.strip()
        if kind == 'navigation':
            excluded['navigation'] = text.strip()
        elif kind == 'promotions':
            excluded['promotions'] = text.strip()
        elif kind == 'widgets':
            excluded['widgets'] = text.strip()
    
    # Extract warnings
    warnings = {}
    for child in root.findall('.//div[@class="body"]/div'):
        kind = child.find('.//span[@class="section-number"]').text.strip()
        text = child.text.strip()
        if kind == 'warning':
            warnings['warning'] = text.strip()
    
    return {
        'title': title,
        'blocks': blocks,
        'metadata': metadata,
        'excluded': excluded,
        'warnings': warnings
    }