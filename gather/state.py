"""
Tracks which articles have already been processed across runs.
Uses DOI as primary key; falls back to normalized URL.
"""
from __future__ import annotations

import json
import os
import re
from datetime import datetime, timezone

from config import STATE_FILE


def _load() -> dict:
    if not os.path.exists(STATE_FILE):
        return {"dois": [], "urls": [], "last_run": None}
    with open(STATE_FILE) as f:
        return json.load(f)


def _save(state: dict) -> None:
    with open(STATE_FILE, "w") as f:
        json.dump(state, f, indent=2)


def normalize_doi(doi: str | None) -> str | None:
    if not doi:
        return None
    doi = re.sub(r"^https?://(dx\.)?doi\.org/", "", doi.strip())
    return doi.lower()


def normalize_url(url: str | None) -> str | None:
    if not url:
        return None
    return url.strip().rstrip("/").lower()


def is_seen(doi: str | None, url: str | None) -> bool:
    state = _load()
    ndoi = normalize_doi(doi)
    nurl = normalize_url(url)
    if ndoi and ndoi in state["dois"]:
        return True
    if nurl and nurl in state["urls"]:
        return True
    return False


def mark_seen(doi: str | None, url: str | None) -> None:
    state = _load()
    ndoi = normalize_doi(doi)
    nurl = normalize_url(url)
    if ndoi and ndoi not in state["dois"]:
        state["dois"].append(ndoi)
    if nurl and nurl not in state["urls"]:
        state["urls"].append(nurl)
    state["last_run"] = datetime.now(timezone.utc).isoformat()
    _save(state)


def mark_all_seen(articles: list) -> None:
    """Batch-mark a list of Article objects as seen."""
    state = _load()
    for a in articles:
        ndoi = normalize_doi(a.doi)
        nurl = normalize_url(a.url)
        if ndoi and ndoi not in state["dois"]:
            state["dois"].append(ndoi)
        if nurl and nurl not in state["urls"]:
            state["urls"].append(nurl)
    state["last_run"] = datetime.now(timezone.utc).isoformat()
    _save(state)


def get_last_run() -> str | None:
    return _load().get("last_run")
