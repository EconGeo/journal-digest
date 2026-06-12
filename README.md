# journal-digest

Automated weekly monitor for academic journals. Two-tier workflow:

- **Tier 1 (automated):** Fetches journals via RSS + CrossRef, enriches abstracts, checks your Zotero library for duplicates, scores articles by keyword relevance, writes a structured raw digest.
- **Tier 2 (in-session):** Open the digest in Claude Code and ask it to summarize articles, flag connections to your prior work, and propose research ideas.

Originally developed for real estate and finance journals. Configurable for any field.

---

## What's in this repo

| File | Purpose |
|------|---------|
| `run_gather.py` | Main script — runs Tier 1 and writes the digest |
| `config.py` | **Edit this first** — journals, keywords, paths, publications |
| `gather/` | Python module: fetcher, scorer, enricher, Zotero integration |
| `requirements.txt` | Python dependencies |
| `ideas.md` | Cumulative research ideas log (committed; Claude Code appends here) |
| `*.plist.template` | macOS LaunchAgent template for weekly scheduling |

---

## Setup

### 1. Install Python dependencies

Python 3.10+ required. Using micromamba (recommended for isolation):

```bash
micromamba create -n journal-digest python=3.12 -c conda-forge
micromamba activate journal-digest
pip install -r requirements.txt
```

Or with pip directly:
```bash
pip install -r requirements.txt
```

### 2. Edit config.py

Open `config.py` and configure:

| Field | What to set |
|-------|------------|
| `ZOTERO_DB` | Full path to your `zotero.sqlite` file |
| `ZOTERO_DB_BAK` | Full path to `zotero.sqlite.bak` (backup Zotero writes continuously) |
| `CROSSREF_EMAIL` | Your email for CrossRef polite pool (faster rate limits) |
| `HIGH_PRIORITY_KEYWORDS` | Terms that flag an article as ⚠️ HIGH PRIORITY |
| `RESEARCH_KEYWORDS` | Broader terms used for relevance scoring |
| `MY_PUBLICATIONS` | Your prior work — Claude uses this to surface connections |
| `TARGET_JOURNALS_FOR_IDEAS` | Journals Claude targets when proposing research ideas |
| `FEEDS` | RSS feeds for your journals (remove what you don't need) |
| `CROSSREF_PRIMARY` | Journals without working RSS feeds (polled via CrossRef every run) |

#### Finding your Zotero SQLite path

- **macOS local:** `~/Zotero/zotero.sqlite`
- **OneDrive/Dropbox:** `~/Library/CloudStorage/OneDrive-Institution/Zotero/zotero.sqlite`
- Check with: `find ~ -name "zotero.sqlite" 2>/dev/null`

### 3. Test the setup

```bash
python run_gather.py --dry-run
```

This fetches articles and scores them but writes no files. Use it to verify your config before the first real run.

### 4. First real run

```bash
# Limit date range to avoid a cold-start flood of articles
python run_gather.py --since 2026-04-01
```

---

## Usage

```bash
# Standard run (new articles only; tracks seen DOIs in seen_articles.json)
python run_gather.py

# Preview without writing files
python run_gather.py --dry-run

# Also poll secondary journals via CrossRef
python run_gather.py --include-secondary

# Backfill from a specific date
python run_gather.py --since 2026-03-01
```

Output goes to `digests/YYYY-MM-DD_raw.md`.

---

## Tier 2: In-Session Analysis with Claude Code

After Tier 1 produces a raw digest, open Claude Code in this directory and paste:

```
Read digests/YYYY-MM-DD_raw.md and analyze it:
1. For each HIGH PRIORITY article, write a 2-3 sentence triage summary
2. For each article, extract the dataset(s) and key variables/measures used
   (from the abstract/methods), plus geographic unit and time span if stated
3. Flag connections to my prior work (see MY_PUBLICATIONS in config.py)
4. Propose 3-5 research gap ideas targeting [your target journals]
Write the analysis to digests/YYYY-MM-DD_digest.md
Append new ideas to ideas.md under a dated header
```

Claude Code will cross-reference your Zotero library (via MCP or SQLite fallback) to find connections.

**Why extract datasets + variables (step 2):** recording the data each paper uses
turns the digest into a *data-discovery* index. When you later file these into an
Obsidian vault (datasets as `[[wikilinks]]`), each dataset becomes a hub that backlinks
every paper using it — so when you start a project needing data on a topic, you can see
at a glance what's already been used and where to get it. See the Obsidian section of
the [research-claude README](https://github.com/EconGeo/research-claude#optional--obsidian-knowledge-base-journal-digest--checkpoint).

### Zotero integration

The script checks each article against your Zotero library in two modes with automatic fallback:

| Mode | When | How |
|------|------|-----|
| **ZotPilot MCP** | Zotero app is open + MCP registered | Semantic search — finds papers by concept |
| **SQLite fallback** | Zotero app is closed | Direct `sqlite3` queries — read-only, always available |

For ZotPilot MCP setup, see [EconGeo/ZotPilot](https://github.com/EconGeo/ZotPilot).

---

## Scheduling on macOS (weekly cron via launchd)

```bash
# Copy the template plist
cp com.YOUR_USERNAME.journal-digest.plist.template \
   ~/Library/LaunchAgents/com.YOUR_USERNAME.journal-digest.plist

# Edit it: replace YOUR_USERNAME and set your Python + script paths
nano ~/Library/LaunchAgents/com.YOUR_USERNAME.journal-digest.plist

# Load the job
launchctl load ~/Library/LaunchAgents/com.YOUR_USERNAME.journal-digest.plist

# Verify
launchctl list | grep journal-digest
```

Runs every Sunday at 7 AM. Logs go to `logs/run.log`.

**Unload:** `launchctl unload ~/Library/LaunchAgents/com.YOUR_USERNAME.journal-digest.plist`

---

## Adding journals

Journals with working RSS feeds go in `FEEDS`. Journals without working RSS feeds go in `CROSSREF_PRIMARY` (polled via DOI/ISSN on every run).

Find CrossRef ISSNs at [api.crossref.org/journals?query=journal+name](https://api.crossref.org/journals?query=journal+name).

---

## Output files

| File | Description |
|------|-------------|
| `digests/YYYY-MM-DD_raw.md` | Tier 1 output — open in Claude Code for Tier 2 |
| `digests/YYYY-MM-DD_digest.md` | Tier 2 output — summaries, connections, ideas |
| `ideas.md` | Cumulative research ideas (committed; appended by Claude Code) |
| `seen_articles.json` | Tracks processed DOIs to prevent duplicates across runs |
| `logs/run.log` | Run logs from Tier 1 |

`digests/` and `logs/` are gitignored. `ideas.md` is committed.

---

## Uninstall

1. `launchctl unload ~/Library/LaunchAgents/com.YOUR_USERNAME.journal-digest.plist`
2. `rm ~/Library/LaunchAgents/com.YOUR_USERNAME.journal-digest.plist`
3. Delete this directory
4. If using micromamba: `micromamba env remove -n journal-digest`

No global state is left after these steps.
