"""Trusted interpreter for model-generated XPath data; never executes model Python."""
import hashlib
import json
from lxml import etree, html

FIELDS = {'title_xpath', 'container_xpath', 'block_xpath', 'exclude_xpath', 'metadata_xpath'}

def norm(node):
    return ' '.join(node.text_content().split())

def parse(data):
    tree = html.document_fromstring(data)
    for node in tree.xpath('//script|//style|//svg|//noscript'):
        node.drop_tree()
    return tree

def validate_rules(rules):
    if not isinstance(rules, dict) or set(rules) != FIELDS:
        raise ValueError('Expected exactly five XPath fields: ' + ', '.join(sorted(FIELDS)))
    for key, value in rules.items():
        if not isinstance(value, str) or len(value) > 1000:
            raise ValueError('XPath must be a string of at most 1000 characters')
        if not value and key not in {'exclude_xpath', 'metadata_xpath'}:
            raise ValueError('Required nonempty XPath: ' + key)
        if value:
            etree.XPath(value)
    return rules

def elements(context, expression):
    nodes = context.xpath(expression) if expression else []
    if not isinstance(nodes, list) or any(not isinstance(n, etree._Element) for n in nodes):
        raise ValueError('XPath must return HTML elements, not scalar values or attributes')
    return nodes

def within(node, parent):
    return node is parent or parent in node.iterancestors()

def extract(rules, data):
    validate_rules(rules)
    tree = parse(data)
    titles = elements(tree, rules['title_xpath'])
    containers = elements(tree, rules['container_xpath'])
    if len(titles) != 1 or len(containers) != 1:
        raise ValueError(f'Expected one title/container; got {len(titles)}/{len(containers)}')
    if not norm(titles[0]):
        raise ValueError('Title must not be empty')
    container = containers[0]
    selected = elements(container, rules['block_xpath'])
    excluded = elements(container, rules['exclude_xpath'])
    metadata = elements(tree, rules['metadata_xpath'])
    if any(not within(n, container) or n is container for n in selected + excluded):
        raise ValueError('Blocks and exclusions must be descendants of the body container')
    selected = [n for n in selected if norm(n) and not any(within(n, e) for e in excluded + metadata)]
    if any(within(e, n) for n in selected for e in excluded + metadata):
        raise ValueError('Partial exclusion inside a selected block is unsupported; select smaller nonoverlapping blocks')
    if any(a is not b and within(a, b) for a in selected for b in selected):
        raise ValueError('Overlapping body selections would duplicate content')
    order = {n: i for i, n in enumerate(tree.iter())}
    selected.sort(key=lambda n: order[n])
    def record(node, kind):
        return {'type': kind, 'text': norm(node), 'xpath': tree.getroottree().getpath(node)}
    blocks = []
    for node in selected:
        kind = ('subheading' if node.tag in {'h2','h3','h4','h5','h6'} else
                'caption' if node.tag == 'figcaption' or 'pictext' in node.get('class','').split() else
                'table' if node.tag == 'table' else 'paragraph')
        row = record(node, kind)
        if node.tag == 'table':
            row['rows'] = [[norm(c) for c in tr.xpath('./th|./td')] for tr in node.xpath('.//tr')]
        blocks.append(row)
    return {'title': norm(titles[0]), 'container_xpath': tree.getroottree().getpath(container),
            'blocks': blocks,
            'metadata': [record(n, 'date' if n.tag == 'time' else 'author' if '/authors/' in n.get('href','') else 'metadata') for n in metadata if norm(n)],
            'excluded': [record(n, 'excluded') for n in excluded if norm(n)],
            'warnings': ['Text-only extraction; image pixels and semantic completeness are not evaluated.']}

def structural_feedback(result, data):
    """Independent semantic-HTML probe, NOT a reference label or accuracy score."""
    tree = parse(data)
    articles = tree.xpath('//article')
    if len(articles) != 1:
        return [{'kind': 'unsupported_probe', 'message': 'Expected one semantic article for this task'}]
    paths = [b['xpath'] for b in result['blocks']]
    meta = [b['xpath'] for b in result['metadata']]
    issues = []
    # A selector is not semantic evidence that a paragraph is noise. Keep these
    # cases pending instead of letting arbitrary exclusions bypass coverage.
    for row in result['excluded']:
        issues.append({'kind': 'exclusion_requires_review', 'xpath': row['xpath'],
                       'message': 'This structure-only probe cannot certify exclusion semantics'})
    for node in articles[0].xpath('.//p|.//li|.//h2|.//h3|.//table|.//figcaption'):
        if not norm(node) or node.xpath('ancestor::header|ancestor::footer|ancestor::nav'):
            continue
        path = tree.getroottree().getpath(node)
        explicit_exclusions = [b['xpath'] for b in result['excluded']]
        if any(path == p or path.startswith(p + '/') for p in paths + meta + explicit_exclusions):
            continue
        # Containers whose children are selected are covered by those children.
        if any(p.startswith(path + '/') for p in paths):
            continue
        issues.append({'kind': 'uncovered_article_node', 'xpath': path, 'preview': norm(node)[:100]})
    for block in result['blocks']:
        node = tree.xpath(block['xpath'])[0]
        if node.xpath('ancestor-or-self::header|ancestor-or-self::footer|ancestor-or-self::nav'):
            issues.append({'kind': 'chrome_in_body', 'xpath': block['xpath'], 'preview': block['text'][:100]})
    if not result['blocks']:
        issues.append({'kind': 'empty_output'})
    return issues

def summarize(data):
    """Bounded structural input. Only call for generation/development pages."""
    tree = parse(data)
    articles = tree.xpath('//article')
    if len(articles) != 1:
        raise ValueError('This task expects a single semantic article; configure another task for other layouts')
    root = articles[0]
    rows = []
    for node in root.iter():
        if not isinstance(node.tag, str):
            continue
        if node.tag not in {'article','header','footer','div','h1','h2','h3','p','li','ul','ol','table','tr','td','th','figcaption','time','a'}:
            continue
        if node.tag == 'a' and not node.xpath('ancestor::header'):
            continue
        rows.append({'xpath': tree.getroottree().getpath(node), 'tag': node.tag,
                     'attrs': {k: v[:160] for k,v in node.attrib.items() if k in {'id','class','href','datetime'}},
                     'chars': len(norm(node)), 'preview': norm(node)[:65]})
    text = json.dumps(rows, ensure_ascii=False)
    if len(text) > 28000:
        raise ValueError('DOM summary exceeds 28000 chars; no silent truncation')
    return text

def export_python(rules):
    value = repr(json.dumps(validate_rules(rules), ensure_ascii=False))
    return ('"""Generated reusable XPath extractor; trusted engine interprets data."""\n'
            'import json\nfrom project2_engine import extract as _engine\n'
            'RULES = json.loads(' + value + ')\n'
            'def extract(data):\n    return _engine(RULES, data)\n')

def digest(data):
    return hashlib.sha256(data).hexdigest()
