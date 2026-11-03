"""扫描疑似独立署名，只生成待审核候选，不修改正文。"""

BYLINE_WORDS = ('记者', '作者', '编辑', '撰文', '供稿')
QUESTION_MARKS = ('：', ':', '？', '?', '！', '!')
SENTENCE_MARKS = ('。', '；', ';', '！', '!', '？', '?')


def find_author_candidates(page):
    """返回可能是独立署名的 paragraph 块；图片说明和问句会被排除。"""
    candidates = []
    for index, block in enumerate(page.get('blocks', [])):
        text = ' '.join(str(block.get('text', '')).split())
        if block.get('type') != 'paragraph' or not text:
            continue
        if not any(word in text for word in BYLINE_WORDS):
            continue
        if any(mark in text for mark in QUESTION_MARKS):
            continue
        if any(mark in text for mark in SENTENCE_MARKS) or len(text) > 48:
            continue
        candidates.append({
            'raw_block_index': index + 1,
            'text': text,
            'xpath': block.get('xpath', ''),
            'reason': '短段落包含署名词，且没有问句或完整句标点；需要语义审核确认。',
        })
    return candidates
