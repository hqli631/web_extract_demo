"""按有效 AI 审核中的明确指令生成派生正文，保留全部原始块。"""
import copy
import hashlib
import json


def compose_cleaned(page):
    original = page['blocks']
    output = {'status': 'unchanged', 'policy_version': 1, 'authors': [],
              'blocks': copy.deepcopy(original), 'applied': [],
              'note': '未应用修正；清理结果不代表新一轮 AI 审核通过。'}
    review = page.get('semantic_review', {})
    if review.get('status') != 'current':
        output.update(status='not_applied', note='没有适用的语义审核，保留原文，不执行修正。')
        return output
    record = review['record']
    actions = record.get('corrections', [])
    confirmed = set()
    for rubric in record.get('rubrics', []):
        if rubric.get('id') == 'non_content' and rubric.get('status') == 'needs_review':
            confirmed.update((e.get('xpath'), e.get('quote')) for e in rubric.get('evidence', []))
    indices = set()
    authors = []
    for action in actions:
        matches = [i for i, b in enumerate(original) if b['xpath'] == action.get('xpath')
                   and b['text'] == action.get('expected_text') and b['type'] == 'paragraph']
        if (action.get('operation') != 'move_to_author' or len(matches) != 1
                or matches[0] in indices
                or (action.get('xpath'), action.get('expected_text')) not in confirmed
                or not isinstance(action.get('author_name'), str)
                or not action['author_name'].strip()
                or action['author_name'] not in action['expected_text']
                or any(mark in action['expected_text'] for mark in ('：', ':', '。', '？', '?', '！', '!'))):
            output.update(status='rejected', note='修正指令与已确认署名证据不一致；整组修正拒绝，保留原文。')
            return output
        index = matches[0]
        indices.add(index)
        authors.append({'name': action['author_name'], 'byline': original[index]['text'],
                        'xpath': original[index]['xpath'], 'raw_block_index': index + 1})
    output['authors'] = authors
    output['blocks'] = [copy.deepcopy(b) for i, b in enumerate(original) if i not in indices]
    output['applied'] = copy.deepcopy(actions)
    output['status'] = 'applied' if actions else 'unchanged'
    if actions:
        output['note'] = ('独立署名已移到作者字段；图片说明和其余正文保持原序。'
                          '这是执行已记录的修正，尚未对清理后结果另做 AI 审核。')
    else:
        output['note'] = '没有需要执行的已确认修正；正文与图片说明保持原序。'
    output['raw_block_count'] = len(original)
    output['clean_block_count'] = len(output['blocks'])
    output['conservation_check'] = len(original) == len(output['blocks']) + len(authors)
    output['review_fingerprint'] = record['fingerprint']
    output['projection_sha256'] = hashlib.sha256(json.dumps(
        {'blocks': output['blocks'], 'authors': authors, 'actions': actions,
         'review_fingerprint': record['fingerprint'], 'policy_version': 1},
        ensure_ascii=False, sort_keys=True).encode('utf-8')).hexdigest()
    return output
