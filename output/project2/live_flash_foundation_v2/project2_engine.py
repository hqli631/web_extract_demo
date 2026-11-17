"""Trusted interpreter for model-generated XPath data; never executes model Python."""
import hashlib
import json
import copy
from lxml import etree, html

FIELDS = {'title_xpath', 'container_xpath', 'block_xpath', 'exclude_xpath', 'metadata_xpath'}
OPTIONAL_FIELDS = {'metadata_fields', 'block_mode'}
METADATA_TYPES = {'author', 'editor', 'source', 'published_at', 'production_credit'}
SKIP_TAGS = {'script', 'style', 'svg', 'noscript'}

def clean_text(node, preserve_lines=False):
    # Clean a copy: deleting nodes in the evidence DOM changes positional XPath.
    clone = copy.deepcopy(node)
    for junk in clone.xpath('.//script|.//style|.//svg|.//noscript|.//a[contains(concat(" ",normalize-space(@class)," ")," headerlink ")]'):
        junk.drop_tree()
    text = clone.text_content()
    return text.strip('\r\n') if preserve_lines else ' '.join(text.split())

def norm(node):
    return clean_text(node)

def parse(data):
    if not isinstance(data, bytes):
        raise TypeError('Input must be HTML bytes')
    if not data.strip():
        raise ValueError('Empty HTML input')
    return html.document_fromstring(data)

def validate_rules(rules):
    if not isinstance(rules, dict) or not FIELDS <= set(rules) or set(rules) - FIELDS - OPTIONAL_FIELDS:
        raise ValueError('Expected five XPath fields and optional metadata_fields/block_mode')
    for key in FIELDS:
        value = rules[key]
        if not isinstance(value, str) or len(value) > 1000:
            raise ValueError('XPath must be a string of at most 1000 characters')
        if not value and key not in {'exclude_xpath', 'metadata_xpath'}:
            raise ValueError('Required nonempty XPath: ' + key)
        if value:
            etree.XPath(value)
    if rules.get('block_mode', 'elements') not in {'elements', 'br_segments'}:
        raise ValueError('block_mode must be elements or br_segments')
    typed = rules.get('metadata_fields', {})
    if not isinstance(typed, dict) or set(typed) - METADATA_TYPES:
        raise ValueError('Unsupported metadata_fields categories')
    for value in typed.values():
        if not isinstance(value, str) or not value or len(value) > 1000:
            raise ValueError('Typed metadata must use nonempty element XPath <=1000 characters')
        etree.XPath(value)
    return rules

def elements(context, expression):
    nodes = context.xpath(expression) if expression else []
    if not isinstance(nodes, list) or any(not isinstance(n, etree._Element) for n in nodes):
        raise ValueError('XPath must return HTML elements, not scalar values or attributes')
    return nodes

def within(node, parent):
    return node is parent or parent in node.iterancestors()

def default_scopes(tree):
    articles = tree.xpath('//article')
    if articles:
        return articles
    return tree.xpath('//*[@role="main"] | //main[not(.//*[@role="main"])]')

def block_type(node):
    classes = node.get('class', '').split()
    if 'footnote' in classes or node.get('role') == 'doc-footnote':
        return 'footnote'
    if node.tag in {'h2','h3','h4','h5','h6'}:
        return 'subheading'
    if node.tag == 'figcaption' or 'pictext' in classes:
        return 'caption'
    if node.tag == 'table':
        return 'table'
    return {'pre':'code_block', 'li':'list_item', 'ul':'list', 'ol':'list',
            'dt':'definition_term', 'dd':'definition_description'}.get(node.tag, 'paragraph')

def metadata_type(node):
    classes = set(node.get('class', '').split())
    prop = (node.get('property','') + ' ' + node.get('name','')).lower()
    if node.tag == 'time' or classes & {'date','published','pubtime'} or 'published_time' in prop:
        return 'published_at'
    if classes & {'article-editor','adEditor','editor'}:
        return 'editor'
    if 'source' in classes or prop.strip() in {'source','og:site_name'}:
        return 'source'
    if '/authors/' in node.get('href','') or node.get('rel') == 'author' or 'author' in prop:
        return 'author'
    return 'metadata'

def segments(node):
    """Legacy br/text/tail segmentation adapted from project one's essay rule."""
    chunks, values = [], []
    def flush():
        value = ' '.join(''.join(chunks).split())
        if value:
            values.append(value)
        chunks.clear()
    def visit(current):
        if current.tag in SKIP_TAGS:
            return
        if current.tag in {'p','blockquote','br','hr'}:
            flush()
        if current.text:
            chunks.append(current.text)
        for child in current:
            if isinstance(child.tag, str):
                visit(child)
            if child.tail:
                chunks.append(child.tail)
        if current.tag in {'p','blockquote'}:
            flush()
    visit(node)
    flush()
    return values

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
    typed_metadata = {}
    for kind, expression in rules.get('metadata_fields', {}).items():
        for node in elements(tree, expression):
            if node in typed_metadata and typed_metadata[node] != kind:
                raise ValueError('Conflicting metadata types for one source node')
            typed_metadata[node] = kind
            if node not in metadata:
                metadata.append(node)
    if any(not within(n, container) or n is container for n in selected + excluded):
        raise ValueError('Blocks and exclusions must be descendants of the body container')
    selected = [n for n in selected if norm(n) and not any(within(n, e) for e in excluded + metadata)]
    if any(n.tag in SKIP_TAGS or any(a.tag in SKIP_TAGS for a in n.iterancestors()) for n in selected):
        raise ValueError('Non-content elements cannot be selected as body blocks')
    if any(within(e, n) for n in selected for e in excluded + metadata):
        raise ValueError('Partial exclusion inside a selected block is unsupported; select smaller nonoverlapping blocks')
    if any(a is not b and within(a, b) for a in selected for b in selected):
        raise ValueError('Overlapping body selections would duplicate content')
    order = {n: i for i, n in enumerate(tree.iter())}
    selected.sort(key=lambda n: order[n])
    def record(node, kind):
        return {'type': kind, 'kind': kind, 'text': norm(node), 'xpath': tree.getroottree().getpath(node)}
    blocks = []
    for node in selected:
        kind = block_type(node)
        row = record(node, kind)
        if rules.get('block_mode') == 'br_segments':
            if node.xpath('.//table|.//pre|.//img'):
                raise ValueError('br_segments does not flatten tables, code or images; select element blocks instead')
            for index, text in enumerate(segments(node)):
                blocks.append(dict(row, text=text, segment_index=index, evidence='container_segment'))
            continue
        if kind == 'code_block':
            row['text'] = clean_text(node, preserve_lines=True)
        if node.tag == 'table':
            row['rows'] = [[norm(c) for c in tr.xpath('./th|./td')] for tr in node.xpath('.//tr')]
        blocks.append(row)
    meta_rows, seen = [], set()
    for node in sorted(metadata, key=lambda n: order[n]):
        row = record(node, typed_metadata.get(node, metadata_type(node)))
        if node.tag == 'meta' and node.get('content'):
            row.update(text=' '.join(node.get('content').split()), attribute='content')
        if row['text'] and (row['type'], row['text']) not in seen:
            meta_rows.append(row)
            seen.add((row['type'], row['text']))
    warnings = ['Text-only extraction; image pixels and semantic completeness are not evaluated.',
                'static_dom_only_no_css_visibility_javascript_or_ocr']
    if container.xpath('.//img'):
        warnings.append('images_present_pixels_not_extracted_completeness_unknown')
    result = {'title': norm(titles[0]), 'container_xpath': tree.getroottree().getpath(container),
            'title_xpath': tree.getroottree().getpath(titles[0]), 'blocks': blocks,
            'metadata': meta_rows,
            'excluded': [record(n, 'excluded') for n in excluded if norm(n)],
            'warnings': warnings}
    issues = validate_result(result, data)
    if issues:
        raise ValueError('Evidence validation failed: ' + ', '.join(issues))
    return result

def validate_result(result, data):
    """Independent raw-DOM evidence/order/table checks, adapted from project one."""
    tree = parse(data)
    order = {n:i for i,n in enumerate(tree.iter())}
    issues, last, seen_paths, segment_order = [], -1, set(), {}
    for key in ('blocks','metadata','excluded'):
        for row in result[key]:
            nodes = elements(tree, row['xpath'])
            if len(nodes) != 1:
                issues.append('xpath_not_unique_element')
                continue
            node = nodes[0]
            if row.get('evidence') == 'container_segment':
                values = segments(node)
                index = row.get('segment_index', -1)
                if not 0 <= index < len(values) or row['text'] != values[index]:
                    issues.append('segment_missing_in_source')
                if key == 'blocks' and index != segment_order.get(row['xpath'], -1) + 1:
                    issues.append('segment_order_changed')
                segment_order[row['xpath']] = index
            elif row.get('attribute'):
                if row['text'] != ' '.join(node.get(row['attribute'],'').split()):
                    issues.append('metadata_attribute_missing_in_source')
            elif ' '.join(row['text'].split()) != norm(node):
                issues.append('text_missing_in_source')
            if key == 'blocks':
                if order[node] < last:
                    issues.append('body_order_changed')
                if row['xpath'] in seen_paths and row.get('evidence') != 'container_segment':
                    issues.append('duplicate_body_node')
                last = order[node]
                seen_paths.add(row['xpath'])
            if row['type'] == 'table':
                expected = [[norm(c) for c in tr.xpath('./td|./th')] for tr in node.xpath('.//tr')]
                if row.get('rows') != expected:
                    issues.append('table_structure_changed')
    return sorted(set(issues))

def structural_feedback(result, data, scope_xpath=None):
    """Independent semantic-HTML probe, NOT a reference label or accuracy score."""
    tree = parse(data)
    # A task-owned scope is independent of the generated container: the model
    # cannot shrink the evaluation area to make its omissions disappear.
    articles = elements(tree, scope_xpath) if scope_xpath else default_scopes(tree)
    if len(articles) != 1:
        return [{'kind': 'unsupported_probe', 'message': 'Configure one independent evaluation_scope_xpath for this layout'}]
    paths = [b['xpath'] for b in result['blocks']]
    meta = [b['xpath'] for b in result['metadata']]
    issues = []
    for row in result['metadata']:
        node = elements(tree,row['xpath'])[0]
        if within(node, articles[0]) and not node.xpath('ancestor-or-self::header'):
            issues.append({'kind':'metadata_requires_review', 'xpath':row['xpath'],
                           'message':'Body metadata classification requires semantic review, not automatic coverage credit'})
    # A selector is not semantic evidence that a paragraph is noise. Keep these
    # cases pending instead of letting arbitrary exclusions bypass coverage.
    for row in result['excluded']:
        issues.append({'kind': 'exclusion_requires_review', 'xpath': row['xpath'],
                       'message': 'This structure-only probe cannot certify exclusion semantics'})
    for node in articles[0].xpath('.//p|.//li|.//h2|.//h3|.//h4|.//h5|.//h6|.//table|.//figcaption|.//pre|.//dt|.//dd|.//div[contains(concat(" ",normalize-space(@class)," ")," pictext ")]'):
        if not norm(node) or node.xpath('ancestor::header|ancestor::footer|ancestor::nav|ancestor::script|ancestor::style|ancestor::noscript'):
            continue
        path = tree.getroottree().getpath(node)
        explicit_exclusions = [b['xpath'] for b in result['excluded']]
        if any(path == p or path.startswith(p + '/') for p in paths + meta + explicit_exclusions):
            continue
        # A selected descendant does not cover an unselected parent's own text.
        descendants = [p for p in paths if p.startswith(path + '/')]
        clone = copy.deepcopy(node)
        for child_path in descendants:
            relative = child_path[len(path):]
            for part in clone.xpath('.' + relative):
                part.drop_tree()
        if descendants and not norm(clone):
            continue
        issues.append({'kind': 'uncovered_article_node', 'xpath': path, 'preview': norm(node)[:100]})
    for block in result['blocks']:
        node = tree.xpath(block['xpath'])[0]
        if node.xpath('ancestor-or-self::header|ancestor-or-self::footer|ancestor-or-self::nav'):
            issues.append({'kind': 'chrome_in_body', 'xpath': block['xpath'], 'preview': block['text'][:100]})
    if not result['blocks']:
        issues.append({'kind': 'empty_output'})
    return issues

def summarize(data, scope_xpath=None):
    """Bounded structural input. Only call for generation/development pages."""
    tree = parse(data)
    candidates = elements(tree,scope_xpath) if scope_xpath else default_scopes(tree)
    if len(candidates) != 1:
        raise ValueError('Need one summary_scope_xpath or unique article/main; unknown layouts are not silently flattened')
    root = candidates[0]
    nodes = list(root.iter())
    # Include title/header metadata outside an editorial container as on news pages.
    nodes += tree.xpath('//h1 | //meta[@content and (@property="article:author" or @property="article:published_time" or @name="author")] | //time')
    nodes = list(dict.fromkeys(nodes))
    rows = []
    for node in nodes:
        if not isinstance(node.tag, str):
            continue
        if node.tag in SKIP_TAGS or any(a.tag in SKIP_TAGS for a in node.iterancestors()):
            continue
        if node.tag not in {'article','main','section','details','summary','header','footer','div','h1','h2','h3','h4','h5','h6','p','pre','dt','dd','li','ul','ol','table','tr','td','th','figcaption','time','a','meta','font','br','img'}:
            continue
        if node.tag == 'a' and not node.xpath('ancestor::header'):
            continue
        rows.append({'xpath': tree.getroottree().getpath(node), 'tag': node.tag,
                     'attrs': {k: v[:160] for k,v in node.attrib.items() if k in {'id','class','href','datetime','property','content','name','role','size','face','cms-style','hidden','style','src','alt'}},
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
