"""
Enriches Article objects with full abstracts from CrossRef.
"""
from __future__ import annotations

import re
import time
import logging

import requests
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type

from config import CROSSREF_EMAIL
from gather.fetcher import Article

logger = logging.getLogger(__name__)


def _clean_abstract(raw: str) -> str | None:
    clean = re.sub(r"<[^>]+>", " ", raw)
    clean = re.sub(r"\s+", " ", clean).strip()
    return clean if len(clean) > 40 else None


@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=2, min=2, max=16),
    retry=retry_if_exception_type(requests.HTTPError),
    reraise=False,
)
def _fetch_by_doi(doi: str) -> tuple[str | None, str | None]:
    """Returns (abstract, doi) from CrossRef works/{doi}."""
    try:
        resp = requests.get(
            f"https://api.crossref.org/works/{doi}",
            params={"mailto": CROSSREF_EMAIL},
            timeout=10,
        )
        resp.raise_for_status()
        item = resp.json().get("message", {})
        return _clean_abstract(item.get("abstract", "")), doi
    except Exception as e:
        logger.debug("CrossRef DOI fetch failed for %s: %s", doi, e)
    return None, doi


def _fetch_by_title(title: str) -> tuple[str | None, str | None]:
    """Title search fallback — returns (abstract, doi) for best match."""
    try:
        resp = requests.get(
            "https://api.crossref.org/works",
            params={
                "query.title": title,
                "select": "DOI,title,abstract",
                "rows": 1,
                "mailto": CROSSREF_EMAIL,
            },
            timeout=10,
        )
        resp.raise_for_status()
        items = resp.json().get("message", {}).get("items", [])
        if not items:
            return None, None
        item = items[0]
        doi = item.get("DOI")
        return _clean_abstract(item.get("abstract", "")), doi
    except Exception as e:
        logger.debug("CrossRef title search failed for '%s': %s", title[:60], e)
    return None, None


def enrich_abstracts(articles: list[Article]) -> None:
    """Fetch full abstracts and fill missing DOIs via CrossRef."""
    needs_enrichment = [a for a in articles if not a.abstract_full]
    logger.info("Enriching abstracts for %d articles via CrossRef...", len(needs_enrichment))
    for i, article in enumerate(needs_enrichment):
        if article.doi:
            abstract, _ = _fetch_by_doi(article.doi)
        else:
            abstract, found_doi = _fetch_by_title(article.title)
            if found_doi:
                article.doi = found_doi
        if abstract:
            article.abstract_full = abstract
        time.sleep(0.1)
        if (i + 1) % 10 == 0:
            logger.info("  Enriched %d/%d", i + 1, len(needs_enrichment))
