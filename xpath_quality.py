"""结构审核提供候选与证据，不代替语义审核。"""
from lxml import html

EXCLUDED_CLASSES = {'adInContent', 'adEditor'}


def inspect_page(path, rules, result):
    tree = html.document_fromstring(path.read_bytes())
    containers = tree.xpath(rules['container_xpath'])
    root = tree.getroottree()

    def text(node):
        return ' '.join(node.text_content().split())

    def excluded(node):
        return any(EXCLUDED_CLASSES.intersection(n.get('class', '').split())
                   for n in [node, *node.iterancestors()])

    def evidence(node, reason):
        return {'xpath': root.getpath(node), 'text': text(node), 'reason': reason}

    selected, resolved, bad_evidence = set(), [], []
    for block in result['blocks']:
        nodes = tree.xpath(block['xpath'])
        if len(nodes) != 1 or text(nodes[0]) != block['text']:
            bad_evidence.append({'xpath': block['xpath'], 'text': block['text'],
                                 'reason': 'XPath 未唯一命中或文字不一致'})
        else:
            selected.add(nodes[0])
            resolved.append(nodes[0])

    # 独立于 block_xpath 检查所有层级的 p 和 pictext。
    candidates, exclusions, images = set(), set(), set()
    for container in containers:
        candidates.update(n for n in container.xpath(
            ".//p | .//*[contains(concat(' ', normalize-space(@class), ' '), ' pictext ')]"
        ) if text(n) and not excluded(n))
        exclusions.update(n for n in container.iterdescendants()
                          if isinstance(n.tag, str) and
                          EXCLUDED_CLASSES.intersection(n.get('class', '').split()))
        images.update(container.xpath('.//img'))

    def covered(node):
        return node in selected or any(a in selected for a in node.iterancestors())

    missing = [evidence(n, '正文候选未覆盖，需确认是否应保留')
               for n in root.iter() if n in candidates and not covered(n)]
    contamination = []
    for node in resolved:
        if excluded(node) or any(
            EXCLUDED_CLASSES.intersection(n.get('class', '').split())
            for n in node.iterdescendants() if isinstance(n.tag, str)
        ):
            contamination.append(evidence(node, '选中已知广告/编辑区域或包含它的父节点'))
    overlap = [evidence(n, '同时提取此节点及其父节点，可能重复')
               for n in resolved if any(a in selected for a in n.iterancestors())]
    positions = {n: i for i, n in enumerate(root.iter())}
    indices = [positions[n] for n in resolved]
    if indices != sorted(indices) or len(resolved) != len(selected):
        overlap.append({'xpath': '', 'text': '', 'reason': '节点顺序错误或重复选取同一节点'})

    def check(key, label, findings, note):
        return {'id': key, 'label': label,
                'status': 'needs_review' if findings else 'structural_pass',
                'note': note, 'evidence': findings}

    checks = [
        check('candidate_coverage', '候选文字覆盖', missing,
              '仅检查当前容器内非已知杂质区域的 p 与 pictext，不证明整页完整。'),
        check('known_exclusions', '已知广告/编辑区域混入', contamination,
              '仅识别 adInContent、adEditor；未标记的推广内容仍可能混入。'),
        check('source_evidence', 'XPath 与原文一致', bad_evidence,
              '输出文本块在本次 HTML 中唯一定位并匹配文字。'),
        check('order_overlap', '顺序和重复覆盖', overlap,
              '检查 DOM 顺序，不能保证等于视觉阅读顺序。'),
        {'id': 'semantic_quality', 'label': '语义完整与杂质判断', 'status': 'unknown',
         'note': '结构检查不判断语义；如有对话 AI 审核记录，在下方单独展示。', 'evidence': []},
        {'id': 'image_text', 'label': '图片内文字', 'status': 'unknown' if images else 'not_applicable',
         'note': f'容器中有 {len(images)} 个 img 元素；未进行 OCR，未判断是否承载正文。',
         'evidence': [{'xpath': root.getpath(n), 'text': n.get('alt', ''),
                       'reason': '需判断是否承载正文文字'}
                      for n in root.iter() if n in images]},
    ]
    return {'checks': checks, 'excluded_regions': [
        evidence(n, '已知广告/编辑结构，记录排除依据')
        for n in root.iter() if n in exclusions],
        'finding_count': sum(len(c['evidence']) for c in checks if c['status'] == 'needs_review')}
