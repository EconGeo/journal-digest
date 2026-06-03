"""
Keyword-based relevance scoring. No AI required.
Sets article.relevance_score (0–3), article.priority_flag, article.keywords_matched.
"""

import re
from gather.fetcher import Article
from config import HIGH_PRIORITY_KEYWORDS, RESEARCH_KEYWORDS


def _text(article: Article) -> str:
    parts = [
        article.title,
        article.abstract_full or "",
        article.abstract_rss or "",
    ]
    return " ".join(parts).lower()


def score_articles(articles: list[Article]) -> None:
    for article in articles:
        text = _text(article)
        matched_priority = []
        matched_research = []

        for kw in HIGH_PRIORITY_KEYWORDS:
            if re.search(r"\b" + re.escape(kw.lower()) + r"\b", text):
                matched_priority.append(kw)

        for kw in RESEARCH_KEYWORDS:
            if re.search(r"\b" + re.escape(kw.lower()) + r"\b", text):
                matched_research.append(kw)

        article.priority_flag = len(matched_priority) > 0
        article.keywords_matched = matched_priority + [
            k for k in matched_research if k not in matched_priority
        ]

        # Score: 3 if high-priority match, else scale on research keyword hits
        if matched_priority:
            article.relevance_score = 3
        elif len(matched_research) >= 3:
            article.relevance_score = 2
        elif len(matched_research) >= 1:
            article.relevance_score = 1
        else:
            article.relevance_score = 0
