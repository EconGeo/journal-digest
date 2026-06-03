"""
Checks articles against the Zotero SQLite database.
Strategy: DOI exact match → fuzzy title match → unknown.
Falls back to .bak file if main DB is locked.
"""
from __future__ import annotations

import logging
import re
import sqlite3
from difflib import SequenceMatcher

from config import ZOTERO_DB, ZOTERO_DB_BAK
from gather.fetcher import Article

logger = logging.getLogger(__name__)

_PUNCT_RE = re.compile(r"[^\w\s]")


def _normalize_title(title: str) -> str:
    return re.sub(r"\s+", " ", _PUNCT_RE.sub("", title.lower())).strip()


def _open_db() -> sqlite3.Connection | None:
    for path in (ZOTERO_DB, ZOTERO_DB_BAK):
        try:
            conn = sqlite3.connect(f"file:{path}?mode=ro", uri=True, timeout=5)
            conn.execute("PRAGMA query_only = ON")
            conn.execute("SELECT COUNT(*) FROM items")  # smoke test
            logger.debug("Opened Zotero DB: %s", path)
            return conn
        except sqlite3.OperationalError as e:
            logger.warning("Cannot open %s: %s", path, e)
    logger.error("Both Zotero DB files inaccessible — Zotero status will be unknown")
    return None


# Fetch all DOIs and titles once per run to avoid repeated queries
_doi_cache: set[str] = set()
_title_cache: list[str] = []
_cache_loaded = False


def _load_cache(conn: sqlite3.Connection) -> None:
    global _doi_cache, _title_cache, _cache_loaded
    if _cache_loaded:
        return
    # Load all DOIs
    rows = conn.execute("""
        SELECT LOWER(idv.value)
        FROM itemData id
        JOIN fields f ON id.fieldID = f.fieldID AND f.fieldName = 'DOI'
        JOIN itemDataValues idv ON id.valueID = idv.valueID
        JOIN items i ON id.itemID = i.itemID
        WHERE i.itemID NOT IN (SELECT itemID FROM deletedItems)
    """).fetchall()
    _doi_cache = {r[0].strip() for r in rows}

    # Load all titles (for fuzzy matching)
    rows = conn.execute("""
        SELECT idv.value
        FROM itemData id
        JOIN fields f ON id.fieldID = f.fieldID AND f.fieldName = 'title'
        JOIN itemDataValues idv ON id.valueID = idv.valueID
        JOIN items i ON id.itemID = i.itemID
        WHERE i.itemID NOT IN (SELECT itemID FROM deletedItems)
          AND i.itemTypeID != 14
    """).fetchall()
    _title_cache = [r[0] for r in rows]
    _cache_loaded = True
    logger.info("Zotero cache loaded: %d DOIs, %d titles", len(_doi_cache), len(_title_cache))


def _check_doi(doi: str) -> bool:
    clean = re.sub(r"^https?://(dx\.)?doi\.org/", "", doi.strip()).lower()
    return clean in _doi_cache


def _check_title_fuzzy(title: str, threshold: float = 0.90) -> bool:
    needle = _normalize_title(title)
    for candidate in _title_cache:
        ratio = SequenceMatcher(None, needle, _normalize_title(candidate)).ratio()
        if ratio >= threshold:
            return True
    return False


def check_zotero(articles: list[Article]) -> None:
    """Sets article.in_zotero for each article. None means unknown (DB locked)."""
    conn = _open_db()
    if conn is None:
        for a in articles:
            a.in_zotero = None
        return

    try:
        _load_cache(conn)
        for article in articles:
            if article.doi and _check_doi(article.doi):
                article.in_zotero = True
            elif _check_title_fuzzy(article.title):
                article.in_zotero = True
            else:
                article.in_zotero = False
    finally:
        conn.close()
