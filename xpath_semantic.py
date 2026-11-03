"""读取本次对话 AI 的离线审核记录，校验记录是否仍适用。不会调用模型。"""
import hashlib
import json

RUBRIC_IDS = {'text_scope', 'non_content', 'captions', 'order', 'image_text'}


def review_fingerprint(page, rules):
    payload = {key: page[key] for key in
               ('file', 'source_sha256', 'title', 'container_count', 'blocks')}
    payload['rules'] = rules
    return hashlib.sha256(json.dumps(payload, ensure_ascii=False, sort_keys=True,
                                    separators=(',', ':')).encode('utf-8')).hexdigest()


def find_review(page, rules, document):
    entries = [entry for entry in document.get('reviews', []) if entry.get('file') == page['file']]
    if not entries:
        return {'status': 'missing', 'note': '尚无本次样本的 AI 语义审核记录。'}
    if len(entries) != 1:
        return {'status': 'invalid', 'note': '同一文件有重复审核记录。'}
    entry = entries[0]
    if entry.get('fingerprint') != review_fingerprint(page, rules):
        return {'status': 'stale', 'note': '源文件、规则或抽取结果已变化；旧审核不再适用。'}
    rubrics = entry.get('rubrics', [])
    if len(rubrics) != len(RUBRIC_IDS) or {r.get('id') for r in rubrics} != RUBRIC_IDS:
        return {'status': 'invalid', 'note': '审核项不完整或重复。'}
    blocks = {b['xpath']: b['text'] for b in page['blocks']}
    for rubric in rubrics:
        if rubric.get('status') not in {'pass', 'needs_review', 'unknown'} or not rubric.get('reason'):
            return {'status': 'invalid', 'note': '审核状态或理由无效。'}
        evidence = rubric.get('evidence', [])
        if rubric['status'] != 'unknown' and not evidence:
            return {'status': 'invalid', 'note': '有结论的审核项必须附文字和 XPath 证据。'}
        for item in evidence:
            if not item.get('quote') or item['quote'] not in blocks.get(item.get('xpath'), ''):
                return {'status': 'invalid', 'note': '审核证据不能与当前输出对应。'}
    return {'status': 'current', 'note': '审核记录与本次输入、规则和输出匹配。',
            'reviewer': document.get('reviewer', ''), 'reviewed_at': document.get('reviewed_at', ''),
            'scope': document.get('scope', ''), 'record': entry}
