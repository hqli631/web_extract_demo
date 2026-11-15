import re
from lxml import etree

def extract(data: bytes) -> dict:
    # Parse the XML data
    root = etree.fromstring(data)
    
    # Extract title
    title = root.find('.//title').text.strip()
    
    # Extract blocks
    blocks = []
    for child in root.findall('.//div[@class="fancy"]'):
        kind = child.find('.//span[@class="kind"]').text.strip()
        text = child.find('.//span[@class="text"]').text.strip()
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
    for child in root.findall('.//div[@class="fancy_toc"]'):
        kind = child.find('.//span[@class="kind"]').text.strip()
        text = child.find('.//span[@class="text"]').text.strip()
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
    for child in root.findall('.//div[@class="fancy-toc1"]'):
        kind = child.find('.//span[@class="kind"]').text.strip()
        text = child.find('.//span[@class="text"]').text.strip()
        if kind == 'author':
            excluded['author'] = text.strip()
        elif kind == 'editor':
            excluded['editor'] = text.strip()
        elif kind == 'source':
            excluded['source'] = text.strip()
        elif kind == 'production_credit':
            excluded['production_credit'] = text.strip()
    
    # Extract warnings
    warnings = {}
    for child in root.findall('.//div[@class="fancy-toc2"]'):
        kind = child.find('.//span[@class="kind"]').text.strip()
        text = child.find('.//span[@class="text"]').text.strip()
        if kind == 'author':
            warnings['author'] = text.strip()
        elif kind == 'editor':
            warnings['editor'] = text.strip()
        elif kind == 'source':
            warnings['source'] = text.strip()
        elif kind == 'production_credit':
            warnings['production_credit'] = text.strip()
    
    return {
        'title': title,
        'blocks': blocks,
        'metadata': metadata,
        'excluded': excluded,
        'warnings': warnings
    }