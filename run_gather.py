#!/usr/bin/env python3
"""
Journal digest gatherer — Tier 1 (free, no AI).

Fetches new articles from real estate and finance journal RSS feeds,
enriches metadata via CrossRef, checks Zotero library, scores relevance
by keyword, and writes a structured raw digest for Claude Code analysis.

Usage:
    python run_gather.py                        # standard weekly run
    python run_gather.py --dry-run              # fetch only, no writes
    python run_gather.py --since 2026-04-01     # reprocess from a date
    python run_gather.py --include-secondary    # also poll JF, RFS, JFE, RSUE
"""

import argparse
import logging
import os
import sys
from datetime import date, datetime

# Allow imports from the journal_digest root
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from config import LOG_DIR
from gather.fetcher import fetch_all_feeds, fetch_primary_crossref, fetch_secondary_journals
from gather.enricher import enrich_abstracts
from gather.zotero import check_zotero
from gather.scorer import score_articles
from gather.state import is_seen, mark_all_seen, get_last_run
from gather.writer import write_raw_digest


def setup_logging(dry_run: bool) -> None:
    os.makedirs(LOG_DIR, exist_ok=True)
    handlers = [logging.StreamHandler(sys.stdout)]
    if not dry_run:
        handlers.append(logging.FileHandler(os.path.join(LOG_DIR, "run.log")))
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s  %(levelname)-7s  %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
        handlers=handlers,
    )


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--dry-run", action="store_true", help="Fetch and score but skip all file writes")
    p.add_argument("--include-secondary", action="store_true", help="Also poll JF, RFS, JFE, RSUE via CrossRef")
    p.add_argument("--since", metavar="YYYY-MM-DD", help="Reprocess articles newer than this date (ignores seen state)")
    return p.parse_args()


def main() -> None:
    args = parse_args()
    setup_logging(args.dry_run)
    log = logging.getLogger(__name__)

    log.info("=" * 60)
    log.info("Journal Digest Gather — %s", datetime.now().strftime("%Y-%m-%d %H:%M"))
    if args.dry_run:
        log.info("DRY RUN — no files will be written")
    last_run = get_last_run()
    log.info("Last run: %s", last_run or "never")

    # 1. Fetch feeds
    log.info("Fetching primary RSS feeds...")
    articles = fetch_all_feeds()

    log.info("Fetching JFQA and JRER via CrossRef...")
    articles.extend(fetch_primary_crossref())

    if args.include_secondary:
        log.info("Fetching secondary journals via CrossRef...")
        articles.extend(fetch_secondary_journals())

    log.info("Total articles fetched: %d", len(articles))

    # 2. Filter seen articles
    if args.since:
        cutoff = args.since
        log.info("--since %s: reprocessing articles published on or after this date", cutoff)
        articles = [a for a in articles if a.published_date >= cutoff]
        log.info("After date filter: %d articles", len(articles))
    else:
        before = len(articles)
        articles = [a for a in articles if not is_seen(a.doi, a.url)]
        log.info("After dedup filter: %d new articles (%d already seen)", len(articles), before - len(articles))

    if not articles:
        log.info("No new articles to process. Done.")
        return

    # 3. Enrich abstracts via CrossRef
    log.info("Enriching abstracts via CrossRef...")
    enrich_abstracts(articles)

    # 4. Check Zotero
    log.info("Checking Zotero library...")
    check_zotero(articles)
    in_zotero = sum(1 for a in articles if a.in_zotero is True)
    log.info("In Zotero: %d / %d", in_zotero, len(articles))

    # 5. Score relevance
    log.info("Scoring relevance...")
    score_articles(articles)
    high = sum(1 for a in articles if a.priority_flag)
    log.info("High-priority articles: %d", high)

    # 6. Write raw digest
    log.info("Writing raw digest...")
    out_path = write_raw_digest(articles, dry_run=args.dry_run)
    if out_path:
        log.info("Raw digest written to: %s", out_path)

    # 7. Update seen state
    if not args.dry_run and not args.since:
        mark_all_seen(articles)
        log.info("State updated.")

    log.info("Done. Open the raw digest in VS Code and ask Claude Code to analyze it.")
    log.info("=" * 60)


if __name__ == "__main__":
    main()
