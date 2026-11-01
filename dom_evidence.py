"""Map extraction disagreements to original saved DOM, including shadow boundaries."""
import re
from lxml import html


def key(text):
    return re.sub(r'\s+', '', text).casefold()


def segment(node):
    index = 1 + sum(sibling.tag == node.tag for sibling in node.itersiblings(preceding=True))
    return f'*[local-name()="{node.tag}"][{index}]'


def locator(node):
    chain, parts = [], []
    for ancestor in [*reversed(list(node.iterancestors())), node]:
        if not isinstance(ancestor.tag, str):
            continue
        if ancestor.tag == 'template' and ancestor.get('shadowrootmode'):
            chain.append('./' + '/'.join(parts))
            parts = []
        else:
            parts.append(segment(ancestor))
    chain.append('./' + '/'.join(parts))
    return chain


def build_index(source):
    root = html.fromstring(source, parser=html.HTMLParser(huge_tree=True))
    candidates = []
    for node in root.iter():
        if node.tag not in {'p', 'li', 'h1', 'h2', 'h3', 'div', 'section', 'article', 'main', 'td', 'blockquote'}:
            continue
        if any(a.tag in {'script', 'style', 'noscript'} or (a.tag == 'template' and not a.get('shadowrootmode')) for a in node.iterancestors()):
            continue
        # Most specific readable blocks avoid mapping a sentence to an entire page.
        if any(n.tag in {'p', 'li', 'h1', 'h2', 'h3', 'div', 'section', 'article', 'main', 'td', 'blockquote'} for n in node.iterdescendants()):
            continue
        text = ' '.join(node.xpath('.//text()[not(ancestor::script) and not(ancestor::style)]')).strip()
        if not key(text):
            continue
        candidates.append((key(text), node, text))
    return candidates


def find_evidence(text, index):
    target = key(text)
    matches = [(value, node, original) for value, node, original in index if target and target in value]
    matches.sort(key=lambda item: len(item[0]))
    return [{
        'locator': locator(node),
        'source_xpath': node.getroottree().getpath(node),
        'tag': node.tag,
        'id': node.get('id', ''),
        'class': node.get('class', ''),
        'expected_text': original,
        'containers': [{'tag': a.tag, 'id': a.get('id', ''), 'class': a.get('class', '')}
                       for a in list(node.iterancestors())[:4]],
    } for _, node, original in matches[:3]]


def make_queue(result, source):
    if not result['current_chars'] or not result['baseline_chars']:
        return [{'file': result['file'], 'snapshot': result['snapshot'],
                 'kind': 'extractor_empty', 'action': 'diagnose_extractor', 'enabled': False,
                 'reason': '至少一个提取器为空，不把另一方的全部正文当作标签错误。'}]
    index = build_index(source)
    queue = []
    for field, kind, action in [('current_only', 'possible_extra', 'exclude_candidate'),
                                ('baseline_only', 'possible_missing', 'include_candidate')]:
        for text in result[field]:
            evidence = find_evidence(text, index)
            queue.append({'file': result['file'], 'snapshot': result['snapshot'], 'kind': kind,
                          'action': action, 'text': text, 'evidence': evidence,
                          'match_status': 'unique' if len(evidence) == 1 else 'ambiguous' if evidence else 'unresolved',
                          'enabled': False, 'label_source': 'algorithm_disagreement',
                          'reviewed': False})
    return queue
