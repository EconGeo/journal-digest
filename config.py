"""
Central configuration for the journal digest system.
Edit this file to add journals, adjust keywords, or change paths.

--- CONFIGURE THESE FIELDS BEFORE FIRST RUN ---
1. ZOTERO_DB / ZOTERO_DB_BAK  — paths to your Zotero SQLite files
2. CROSSREF_EMAIL              — your email for CrossRef polite pool
3. MY_PUBLICATIONS             — your published work (Claude uses this to find connections)
4. HIGH_PRIORITY_KEYWORDS      — terms that trigger the ⚠️ HIGH PRIORITY flag
5. TARGET_JOURNALS_FOR_IDEAS   — journals Claude targets when proposing ideas
"""

# ── RSS feeds (journals with working feeds) ───────────────────────────────────
FEEDS = {
    "JREFE": "https://link.springer.com/search.rss?facet-journal-id=11146&query=*",
    "REE":   "https://onlinelibrary.wiley.com/feed/15406229/most-recent",
    "JUE":   "https://rss.sciencedirect.com/publication/science/00941190",
}

# ── Primary journals polled via CrossRef (RSS unavailable; runs every week) ───
# JFQA: Cambridge RSS is malformed. JRER: Taylor & Francis RSS is blocked.
CROSSREF_PRIMARY = {
    "JFQA": "0022-1090",
    "JRER": "0896-5803",
}

# ── Secondary journals via CrossRef ISSN polling (--include-secondary flag) ───
CROSSREF_JOURNALS = {
    "JF":   "0022-1082",
    "RFS":  "1465-7368",
    "JFE":  "0304-405X",
    "RSUE": "0166-0462",
}
CROSSREF_LOOKBACK_DAYS = 30

# ── Keywords that trigger ⚠️ HIGH PRIORITY flag ───────────────────────────────
# Customize these for your research area
HIGH_PRIORITY_KEYWORDS = [
    # Example: Zoning / land use
    "zoning", "land use regulation", "upzoning",
    # Example: ESG / sustainability / climate
    "ESG", "green building", "LEED", "climate risk", "sustainability",
    # Add your own high-priority terms here
]

# ── Broader research keywords (used for relevance scoring 0–3) ────────────────
RESEARCH_KEYWORDS = [
    "REIT", "commercial real estate", "housing", "housing supply", "multifamily",
    "asset pricing", "urban form", "transit",
    # Add your own research keywords here
]

# ── Your published work — Claude Code uses this to surface connections ─────────
# Example format: "Paper Title (Year, Journal)"
MY_PUBLICATIONS = [
    # "Your Paper Title (Year, Journal)",
    # "Another Paper (Year, Journal)",
]

# ── Target journals for suggested new work ────────────────────────────────────
TARGET_JOURNALS_FOR_IDEAS = [
    # "Journal of Finance (JF)",
    # "Review of Financial Studies (RFS)",
]

# ── Zotero SQLite paths ───────────────────────────────────────────────────────
# macOS path example: /Users/YOUR_USERNAME/Library/CloudStorage/OneDrive-Institution/Zotero/zotero.sqlite
# Or: /Users/YOUR_USERNAME/Zotero/zotero.sqlite  (if using local Zotero storage)
ZOTERO_DB     = "/Users/YOUR_USERNAME/Zotero/zotero.sqlite"
ZOTERO_DB_BAK = "/Users/YOUR_USERNAME/Zotero/zotero.sqlite.bak"

# ── CrossRef polite pool (faster rate limits with a valid email) ───────────────
CROSSREF_EMAIL = "your.email@example.com"

# ── Output paths (auto-detected from script location) ────────────────────────
import os
_BASE = os.path.dirname(os.path.abspath(__file__))

DIGEST_DIR = os.path.join(_BASE, "digests")
IDEAS_FILE = os.path.join(_BASE, "ideas.md")
STATE_FILE = os.path.join(_BASE, "seen_articles.json")
LOG_DIR    = os.path.join(_BASE, "logs")
