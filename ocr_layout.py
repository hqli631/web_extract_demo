"""Conservative, opt-in layout profiles; never alter recognized words."""
import re


def select_card_body(lines, height, profile='none'):
    """Return line decisions. This profile is for Chinanews quote cards only."""
    decisions = [dict(line, label='待判断', reason='未启用匹配的图片版式规则') for line in lines]
    if profile != 'chinanews_quote_card_v1' or height <= 0:
        return decisions, 'not_applied'
    # Check all layout anchors before removing anything. Similar-looking images
    # without these anchors remain unclassified rather than silently cropped.
    top = [i for i, line in enumerate(lines) if line['text'] in {'言道', '习言道'}
           and max(p[1] for p in line['box']) / height < .15]
    domain = [i for i, line in enumerate(lines) if 'CHINANEWS.COM.CN' in line['text'].upper()
              and min(p[1] for p in line['box']) / height > .9]
    dates = [i for i, line in enumerate(lines) if re.fullmatch(r'\d{4}年\d{1,2}月\d{1,2}日', line['text'])
             and min(p[1] for p in line['box']) / height > .7]
    attribution = [i for i, line in enumerate(lines) if line['text'] == '在党外人士座谈会上说'
                   and min(p[1] for p in line['box']) / height > .7]
    if not (len(top) == len(domain) == len(dates) == len(attribution) == 1):
        return decisions, 'anchors_not_matched'
    end = attribution[0] - 1
    if end < 0 or lines[end]['text'] != '习近平' or not (top[0] < end < attribution[0] < dates[0] < domain[0]):
        return decisions, 'anchors_not_matched'
    for index, line in enumerate(decisions):
        inside = top[0] < index < end
        line['label'] = '正文候选' if inside else '版式附属文字'
        line['reason'] = '匹配卡片正文与署名边界' if inside else '匹配卡片页眉、署名、日期或水印范围'
    return decisions, 'applied'
