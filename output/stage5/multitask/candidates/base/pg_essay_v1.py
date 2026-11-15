import re
from lxml import etree

def extract(data: bytes) -> dict:
    # Parse the XML data
    root = etree.fromstring(data)
    
    # Extract title
    title = root.find('.//title').text.strip()
    
    # Extract blocks
    blocks = []
    for child in root.findall('.//block'):
        kind = child.tag
        text = child.text.strip()
        if kind == 'paragraph':
            blocks.append({'kind': kind, 'text': text})
        elif kind == 'subheading':
            blocks.append({'kind': kind, 'text': text})
        elif kind == 'caption':
            blocks.append({'kind': kind, 'text': text})
        elif kind == 'table':
            rows = []
            for row in child.findall('.//row'):
                cells = []
                for cell in row.findall('.//cell'):
                    cells.append(cell.text.strip())
                rows.append(cells)
            blocks.append({'kind': kind, 'text': text, 'rows': rows})
    
    # Extract metadata
    metadata = {}
    for child in root.findall('.//metadata'):
        kind = child.tag
        text = child.text.strip()
        if kind == 'author':
            metadata['author'] = text
        elif kind == 'editor':
            metadata['editor'] = text
        elif kind == 'source':
            metadata['source'] = text
        elif kind == 'production_credit':
            metadata['production_credit'] = text
    
    # Extract excluded entries
    excluded = {}
    for child in root.findall('.//excluded'):
        kind = child.tag
        text = child.text.strip()
        if kind == 'author':
            excluded['author'] = text
        elif kind == 'editor':
            excluded['editor'] = text
        elif kind == 'source':
            excluded['source'] = text
        elif kind == 'production_credit':
            excluded['production_credit'] = text
    
    # Extract warnings
    warnings = {}
    for child in root.findall('.//warning'):
        kind = child.tag
        text = child.text.strip()
        if kind == 'author':
            warnings['author'] = text
        elif kind == 'editor':
            warnings['editor'] = text
        elif kind == 'source':
            warnings['source'] = text
        elif kind == 'production_credit':
            warnings['production_credit'] = text
    
    return {
        'title': title,
        'blocks': blocks,
        'metadata': metadata,
        'excluded': excluded,
        'warnings': warnings
    }