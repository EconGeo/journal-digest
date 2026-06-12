"""
Renders the raw digest markdown file.
The raw digest is structured for Claude Code to read and analyze in-session.
"""
from __future__ import annotations

import fcntl
import os
from datetime import datetime
from collections import Counter

from gather.fetcher import Article
from config import DIGEST_DIR, MY_PUBLICATIONS, TARGET_JOURNALS_FOR_IDEAS


def _zotero_label(article: Article) -> str:
    if article.in_zotero is True:
        return "Yes"
    if article.in_zotero is False:
        return "No"
    return "Unknown"


def _abstract_text(article: Article) -> str:
    text = article.abstract_full or article.abstract_rss
    if not text:
        return "_Abstract not available. Summarize from title and authors only._"
    source = "CrossRef" if article.abstract_full else "RSS (may be truncated)"
    # Wrap long abstracts at ~100 chars per line for readability
    words = text.split()
    lines, line = [], []
    for word in words:
        line.append(word)
        if len(" ".join(line)) > 100:
            lines.append(" ".join(line))
            line = []
    if line:
        lines.append(" ".join(line))
    return "\n  ".join(lines) + f"  _{source}_"


def _render_article(article: Article) -> str:
    priority_tag = "  |  ⚠️ **HIGH PRIORITY**" if article.priority_flag else ""
    kw_str = ", ".join(article.keywords_matched[:6]) if article.keywords_matched else "none"
    doi_str = f"[{article.doi}](https://doi.org/{article.doi})" if article.doi else "N/A"
    authors_str = "; ".join(article.authors[:4]) if article.authors else "Unknown"
    if len(article.authors) > 4:
        authors_str += " et al."

    return f"""### [{article.source_journal}] {article.title}
- **Authors:** {authors_str}
- **Published:** {article.published_date}{priority_tag}
- **DOI:** {doi_str}
- **In Zotero:** {_zotero_label(article)}
- **Keywords matched:** {kw_str}
- **Abstract:** {_abstract_text(article)}
"""


def write_raw_digest(
    new_articles: list[Article],
    run_date: str | None = None,
    dry_run: bool = False,
) -> str | None:
    """Write the raw digest file. Returns the file path, or None on dry-run."""
    today = run_date or datetime.now().strftime("%Y-%m-%d")
    out_path = os.path.join(DIGEST_DIR, f"{today}_raw.md")

    high = [a for a in new_articles if a.priority_flag]
    moderate = [a for a in new_articles if not a.priority_flag and a.relevance_score >= 2]
    low = [a for a in new_articles if not a.priority_flag and a.relevance_score < 2]
    in_zotero_count = sum(1 for a in new_articles if a.in_zotero is True)

    journal_counts = Counter(a.source_journal for a in new_articles)
    journal_summary = ", ".join(f"{j} ({n})" for j, n in sorted(journal_counts.items()))

    run_ts = datetime.now().strftime("%Y-%m-%d %H:%M")

    lines = [
        f"# Journal Digest — Raw Data — {today}",
        f"*Run: {run_ts} | New articles: {len(new_articles)} | Already in Zotero: {in_zotero_count} | High-priority: {len(high)}*",
        f"*Journals: {journal_summary}*",
        "*STATUS: UNANALYZED — open in VS Code and ask Claude Code to analyze this file*",
        "",
        "---",
        "",
        "## How to analyze this digest",
        "",
        "Open this file in VS Code and say:",
        "> \"Analyze the journal digest at journal_digest/digests/" + f"{today}_raw.md\"",
        "",
        "Claude Code will: (1) call Corbis `search_papers` on each HIGH PRIORITY article topic",
        "to surface related literature; (2) call `top_cited_articles` on REE/JREFE for the",
        "dominant topic(s) to establish citation benchmarks; (3) generate triage summaries;",
        "(4) flag connections to your prior work; (5) extract the dataset(s) and key variables",
        "used in each article (for data discovery and Obsidian crosslinking); (6) propose",
        "research gap ideas.",
        f"Output goes to `{today}_digest.md` and `ideas.md`.",
        "",
        "---",
        "",
    ]

    if high:
        lines += [
            "## ⚠️ HIGH PRIORITY (zoning / ESG / affordable housing matches)",
            "",
        ]
        for a in sorted(high, key=lambda x: x.published_date, reverse=True):
            lines.append(_render_article(a))
            lines.append("---")
            lines.append("")

    if moderate:
        lines += [
            "## MODERATE RELEVANCE (score 2–3)",
            "",
        ]
        for a in sorted(moderate, key=lambda x: x.relevance_score, reverse=True):
            lines.append(_render_article(a))
            lines.append("---")
            lines.append("")

    if low:
        lines += [
            "## LOW RELEVANCE / MONITOR (score 0–1)",
            "",
        ]
        for a in sorted(low, key=lambda x: x.published_date, reverse=True):
            lines.append(_render_article(a))
            lines.append("---")
            lines.append("")

    # Embed research context for Claude Code
    lines += [
        "---",
        "",
        "## Context for Claude Code analysis",
        "",
        "**Target journals for new research ideas:** " + ", ".join(TARGET_JOURNALS_FOR_IDEAS),
        "",
        "**Corbis MCP tools to call during analysis (require active Claude Code session):**",
        "- `search_papers`: for each HIGH PRIORITY article, query its topic; filter to",
        "  [\"Real Estate Economics\", \"Journal of Real Estate Finance and Economics\",",
        "  \"Journal of Urban Economics\", \"Journal of Real Estate Research\",",
        "  \"Journal of Finance\", \"Review of Financial Studies\"]; minYear 2018; sortBy citedByCount.",
        "  Check Zotero for each result. Surface top 2–3 not already in library.",
        "- `top_cited_articles`: identify 1–2 dominant topics from this digest; call on",
        "  [\"Real Estate Economics\", \"Journal of Real Estate Finance and Economics\"];",
        "  minYear 2020; limit 5. Include as 'Top Cited on This Topic' in the analyzed digest.",
        "",
        "**Your published work (for surfacing connections):**",
    ]
    for pub in MY_PUBLICATIONS:
        lines.append(f"- {pub}")
    lines.append("")

    content = "\n".join(lines)

    if dry_run:
        print(content[:3000])
        print(f"\n[DRY RUN — would write to {out_path}]")
        return None

    os.makedirs(DIGEST_DIR, exist_ok=True)
    # If a file for today already exists, append as a supplemental run
    if os.path.exists(out_path):
        with open(out_path, "a") as f:
            fcntl.flock(f, fcntl.LOCK_EX)
            f.write(f"\n\n---\n## Supplemental Run — {run_ts}\n\n")
            f.write(content)
            fcntl.flock(f, fcntl.LOCK_UN)
    else:
        with open(out_path, "w") as f:
            fcntl.flock(f, fcntl.LOCK_EX)
            f.write(content)
            fcntl.flock(f, fcntl.LOCK_UN)

    return out_path
