"""
Fetches RSS feeds and returns Article objects.
Also handles CrossRef ISSN polling for secondary journals.
"""
from __future__ import annotations

import re
import time
import logging
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone

import feedparser
import requests
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type

from config import FEEDS, CROSSREF_PRIMARY, CROSSREF_JOURNALS, CROSSREF_LOOKBACK_DAYS, CROSSREF_EMAIL

logger = logging.getLogger(__name__)

_DOI_RE = re.compile(r"10\.\d{4,9}/[-._;()/:A-Za-z0-9]+")


@dataclass
class Article:
    source_journal: str
    title: str
    authors: list[str]
    doi: str | None
    url: str
    abstract_rss: str | None
    published_date: str
    # filled in later
    abstract_full: str | None = None
    in_zotero: bool | None = None
    relevance_score: int = 0
    priority_flag: bool = False
    keywords_matched: list[str] = field(default_factory=list)


def _extract_doi(entry) -> str | None:
    """Try to extract a DOI from various feed entry fields."""
    for candidate in [
        getattr(entry, "id", ""),
        getattr(entry, "link", ""),
        getattr(entry, "doi", ""),
    ]:
        if candidate:
            m = _DOI_RE.search(candidate)
            if m:
                return m.group(0)
    # Some feeds put it in tags
    for tag in getattr(entry, "tags", []):
        m = _DOI_RE.search(tag.get("term", ""))
        if m:
            return m.group(0)
    return None


def _extract_authors(entry) -> list[str]:
    authors = []
    if hasattr(entry, "authors"):
        for a in entry.authors:
            name = a.get("name", "").strip()
            if name:
                authors.append(name)
    elif hasattr(entry, "author"):
        authors = [entry.author.strip()]
    return authors


def _extract_abstract(entry) -> str | None:
    for attr in ("summary", "description", "content"):
        val = getattr(entry, attr, None)
        if isinstance(val, list):
            val = val[0].get("value", "") if val else None
        if val:
            # Strip HTML tags
            text = re.sub(r"<[^>]+>", " ", val).strip()
            text = re.sub(r"\s+", " ", text)
            if len(text) > 80:
                return text
    return None


def _parse_date(entry) -> str:
    for attr in ("published", "updated", "created"):
        val = getattr(entry, f"{attr}_parsed", None)
        if val:
            try:
                return datetime(*val[:6]).strftime("%Y-%m-%d")
            except Exception:
                pass
    return datetime.now().strftime("%Y-%m-%d")


_HEADERS = {
    "User-Agent": "Mozilla/5.0 (research journal monitor; mailto:drewmueller@gmail.com)",
    "Accept": "application/rss+xml, application/xml, text/xml, */*",
}

# ScienceDirect embeds authors in description as "Author(s): Name1, Name2"
_SD_AUTHORS_RE = re.compile(r"Author\(s\):\s*(.+?)(?:\s*$)", re.IGNORECASE)


def _extract_authors_sciencedirect(entry) -> list[str]:
    """Extract authors from ScienceDirect description text."""
    for attr in ("summary", "description"):
        val = getattr(entry, attr, "") or ""
        val = re.sub(r"<[^>]+>", " ", val)
        m = _SD_AUTHORS_RE.search(val)
        if m:
            names = [n.strip() for n in m.group(1).split(",") if n.strip()]
            return names
    return []


def _fetch_single_feed(journal_key: str, url: str) -> list[Article]:
    try:
        # Fetch raw bytes with requests first — many feeds reject feedparser's default UA
        # or have encoding issues that requests handles better than feedparser's urllib
        resp = requests.get(url, headers=_HEADERS, timeout=15)
        resp.raise_for_status()
        feed = feedparser.parse(resp.content)

        if not feed.entries:
            # Log bozo exception only if we got no entries at all
            if feed.bozo:
                logger.warning("Feed parse error for %s: %s", journal_key, feed.bozo_exception)
            return []

        is_sciencedirect = "sciencedirect.com" in url

        articles = []
        for entry in feed.entries:
            title = getattr(entry, "title", "").strip()
            if not title:
                continue

            authors = (
                _extract_authors_sciencedirect(entry)
                if is_sciencedirect
                else _extract_authors(entry)
            )

            articles.append(Article(
                source_journal=journal_key,
                title=title,
                authors=authors,
                doi=_extract_doi(entry),
                url=getattr(entry, "link", "").strip(),
                abstract_rss=_extract_abstract(entry),
                published_date=_parse_date(entry),
            ))
        logger.info("  %s: %d articles fetched", journal_key, len(articles))
        return articles
    except requests.HTTPError as e:
        logger.error("HTTP error fetching feed for %s: %s", journal_key, e)
        return []
    except Exception as e:
        logger.error("Failed to fetch feed for %s: %s", journal_key, e)
        return []


def fetch_all_feeds() -> list[Article]:
    """Fetch all primary RSS feeds in parallel."""
    all_articles = []
    with ThreadPoolExecutor(max_workers=5) as pool:
        futures = {pool.submit(_fetch_single_feed, k, v): k for k, v in FEEDS.items()}
        for future in as_completed(futures):
            all_articles.extend(future.result())
    return all_articles


@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=2, min=2, max=16),
    retry=retry_if_exception_type(requests.HTTPError),
    reraise=True,
)
def _crossref_request(url: str, params: dict) -> dict:
    resp = requests.get(url, params=params, timeout=15)
    resp.raise_for_status()
    return resp.json()


def _poll_crossref_issns(journals: dict[str, str]) -> list[Article]:
    """Poll a dict of {journal_key: issn} via CrossRef."""
    cutoff = (datetime.now(timezone.utc) - timedelta(days=CROSSREF_LOOKBACK_DAYS)).strftime("%Y-%m-%d")
    articles = []
    for journal_key, issn in journals.items():
        try:
            data = _crossref_request(
                "https://api.crossref.org/works",
                {
                    "filter": f"issn:{issn},from-pub-date:{cutoff}",
                    "select": "DOI,title,author,abstract,published-print,published-online,URL",
                    "rows": 50,
                    "mailto": CROSSREF_EMAIL,
                },
            )
            for item in data.get("message", {}).get("items", []):
                titles = item.get("title", [])
                if not titles:
                    continue
                authors = [
                    f"{a.get('family', '')} {a.get('given', '')}".strip()
                    for a in item.get("author", [])
                ]
                pub = item.get("published-print") or item.get("published-online") or {}
                parts = pub.get("date-parts", [[]])[0]
                date_str = "-".join(str(p) for p in parts) if parts else ""

                raw_abstract = item.get("abstract", "")
                clean_abstract = re.sub(r"<[^>]+>", " ", raw_abstract).strip() if raw_abstract else None

                articles.append(Article(
                    source_journal=journal_key,
                    title=titles[0],
                    authors=authors,
                    doi=item.get("DOI"),
                    url=item.get("URL", ""),
                    abstract_rss=None,
                    published_date=date_str,
                    abstract_full=clean_abstract,
                ))
            logger.info("  %s (CrossRef): %d articles fetched", journal_key, len(articles))
            time.sleep(0.2)
        except Exception as e:
            logger.error("Failed CrossRef poll for %s: %s", journal_key, e)
    return articles


def fetch_primary_crossref() -> list[Article]:
    """Fetch JFQA and JRER via CrossRef (RSS unavailable for these journals)."""
    return _poll_crossref_issns(CROSSREF_PRIMARY)


def fetch_secondary_journals() -> list[Article]:
    """Poll secondary journals via CrossRef ISSN queries (--include-secondary flag)."""
    return _poll_crossref_issns(CROSSREF_JOURNALS)
