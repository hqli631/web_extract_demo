"""Conservative, explainable article scope selection on parsed snapshot copies."""
import re


def compact(text):
    return re.sub(r'\s+', '', text).casefold()


def select_scope(soup, title):
    # Observed on frozen Chinanews article pages; do not apply this generic
    # class to unrelated sites or accept multiple competing containers.
    chinese_news = soup.select('.left_zw')
    if '中新网' in title and len(chinese_news) == 1:
        return chinese_news, 'article', '中新网 .left_zw', []
    # Narrow content roots take precedence over page-wide main elements.
    for selector, kind in [('#floor-1 .md-body:not(.signature-md)', 'forum_post'),
                           ('[itemprop="articleBody"]', 'article'),
                           ('#artibody', 'article')]:
        roots = soup.select(selector)
        if len(roots) == 1:
            return roots, kind, selector, []

    pages = soup.select('consumption-page')
    if pages:
        matching = [p for p in pages if any(compact(h.get_text()) == compact(title)
                                          for h in p.select('h1'))]
        if len(matching) == 1 and matching[0].select('article'):
            return matching[0].select('article'), 'article', 'consumption-page H1 = document title > article', []
        return [], 'unknown', 'ambiguous_consumption_pages', ['多文章快照未能唯一匹配目标标题，暂不拼接文章。']

    articles = soup.select('article')
    if len(articles) == 1:
        return articles, 'article', 'article', []
    if len(articles) > 1:
        matching = [a for a in articles if any(compact(h.get_text()) == compact(title)
                                             for h in a.select('h1'))]
        if len(matching) == 1:
            return matching, 'article', 'article H1 = document title', []
        return [], 'unknown', 'ambiguous_articles', ['存在多篇文章但标题不能唯一匹配，暂缓提取。']

    if soup.select_one('.topic-list, #topic-list-heading'):
        return [], 'listing', '.topic-list / #topic-list-heading', ['话题列表页应继续采集帖子详情页。']
    if len(soup.select('.url-info')) >= 3:
        return [], 'listing', '.url-info repeated cards', ['目录卡片页不作为单篇文章正文。']

    # Stable editorial block attributes are preferable to hashed CSS classes.
    anchors = soup.select('main p[data-sticky-nav-anchor="true"]')
    if anchors:
        roots = list(anchors)
        for heading in soup.select('main h2, main h3'):
            if not heading.find_parent(['section', 'aside', 'li', 'nav']):
                roots.append(heading)
        return roots, 'article', 'main p[data-sticky-nav-anchor=true] + narrative headings', []
    return [], 'unknown', 'legacy_length_fallback', ['未识别可靠正文容器，保留旧算法候选，需复核。']
