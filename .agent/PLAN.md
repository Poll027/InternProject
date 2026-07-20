# RegWatch — Agent Handoff Plan
**Last updated by**: Claude Code (terminal session)
**Last updated at**: 2026-07-14
**Current status**: STEPS_1_TO_5_COMPLETE — ready for Step 6 (LLM classification)

---

## 1. PROJECT SNAPSHOT

RegWatch is an internal regulatory intelligence and lead generation tool built for Deloitte Africa's Nigeria practice. It monitors official Nigerian regulatory sources daily, detects new circulars, directives, standards updates, and policy notices, classifies them by relevance to four Deloitte service lines (AI & Data, Tax, Audit, Cybersecurity), ranks them by urgency, and generates evidence-backed briefings for internal team members. Output goes to analysts and managers only — never directly to partners or clients. Every finding includes a source link and confidence score so humans can verify before acting. The system is a research accelerant, not a decision engine.

This is an internship project at Deloitte Africa Lagos office, built by Folajuwon on the AI & Data team. The MVP covers Nigeria only. Expansion to South Africa, Kenya, and Ghana is Phase 2.

---

## 2. TECH STACK & CONSTRAINTS

- **Language**: Python 3.12
- **Package manager**: pip (no Poetry, no conda)
- **Database**: SQLite for local dev and demo. PostgreSQL on Azure for production deployment.
- **Key dependencies**:
  - `feedparser` — RSS ingestion for CBN, SEC, IASB
  - `firecrawl-py` — web scraping for NRS, NITDA, FRCN, NAICOM, LIRS
  - `google-genai` — LLM extraction and opportunity framing (Gemini API key for demo, Azure OpenAI for production). Note: `google-generativeai` is deprecated/EOL as of mid-2026, `google-genai` is the current SDK — do not revert.
  - `apscheduler` — scheduling daily ingestion runs
  - `python-dotenv` — environment variable management
  - `requests` — HTTP calls where needed
- **Hosting**: Azure Functions (production). Local for demo.
- **LLM strategy**: Gemini API key for the demo build. Switch to Azure OpenAI when deploying to Deloitte's Azure tenant.

**Hard constraints — no agent should change these without explicit instruction:**
- Never store or log actual API keys in any file. All secrets via `.env` only.
- Never use page-level hashing. Always hash at item level (title + URL + date + source name).
- Never send findings directly to a report without a `confidence_score` field populated.
- Never remove the `source_url` and `evidence_excerpt` fields from any finding. Every finding must be verifiable.
- Never expand scope to additional countries or service lines without explicit instruction.
- The four allowed service lines are exactly: `AI_DATA`, `TAX`, `AUDIT`, `CYBERSECURITY`. Do not add or rename.
- Do not build any partner-facing or client-facing output layer. Output targets analysts and managers only.
- Do not implement media/news monitoring. That is explicitly Phase 2 and out of current scope.

**File structure:**
```
regwatch/
├── .agent/
│   └── PLAN.md                  ← this file
├── .env                         ← secrets, never committed
├── .env.example                 ← committed, shows required keys
├── .gitignore
├── requirements.txt
├── main.py                      ← entry point, runs full pipeline
├── database/
│   ├── __init__.py
│   ├── models.py                ← SQLite schema and table creation
│   └── db.py                    ← connection and query helpers
├── ingestion/
│   ├── __init__.py
│   ├── rss_poller.py            ← Pipeline A: CBN, SEC, IASB RSS feeds
│   ├── scraper.py               ← Pipeline B: NRS, NITDA, FRCN, NAICOM, LIRS
│   └── sources.py               ← source registry: all source configs in one place
├── extraction/
│   ├── __init__.py
│   ├── classifier.py            ← LLM classification prompt, returns structured JSON
│   └── framer.py                ← LLM opportunity framing prompt, per service line
├── reports/
│   ├── __init__.py
│   ├── weekly.py                ← weekly urgent alert generator
│   └── monthly.py               ← monthly digest generator per service line
└── utils/
    ├── __init__.py
    ├── hashing.py               ← item-level SHA-256 hashing logic
    └── logger.py                ← structured logging
```

---

## 3. COMPLETED STEPS

- Project fully scoped and documented (scope document exists separately)
- Directory structure created
- Source list confirmed: CBN, SEC, IASB (Pipeline A); NRS, NITDA, FRCN, NAICOM, LIRS (Pipeline B)
- Service lines confirmed: AI_DATA, TAX, AUDIT, CYBERSECURITY (Risk Advisory dropped — no team)
- Urgency framework defined (CRITICAL / HIGH / MEDIUM / LOW) with separate tracks for regulations and standards
- Confidence score formula defined (composite of source reliability weight × LLM sub-scores)
- Two-prompt LLM architecture confirmed: classification prompt → opportunity framing prompt
- Database schema designed (Sources, SourceItems, Findings, OpportunityFramings, Reports, ReportFindings)
- Tech stack confirmed
- **Step 1 done**: `requirements.txt`, `.env`, `.env.example`, `.gitignore`, `database/models.py`, `database/db.py`, `main.py` all working. `python main.py` creates `regwatch.db` with all six tables (raw SQL, no ORM).
- **Step 2 done**: `utils/hashing.py` (`generate_item_hash`, SHA-256, deterministic — verified) and `utils/logger.py` (`get_logger`, stdlib `logging`, format `[TIMESTAMP] [LEVEL] [MODULE] message`) both working and importable.
- **Step 3 done**: `ingestion/sources.py` — all 8 sources defined in `SOURCES`, `seed_sources(conn)` populates the `sources` table via `INSERT OR IGNORE` (idempotent on `name`). Verified all 8 rows present with correct `pipeline`/`reliability_score`.
- **Step 4 done**: `ingestion/rss_poller.py` — `poll_rss_source` + `run_rss_pipeline`, CBN and SEC only (IASB still excluded per plan). Verified: first run found real new items, second run found 0 for both (hash dedup confirmed working).
- **Step 5 done**: `fetch_full_content`, `get_firecrawl_client`, `run_content_fetch_pipeline` added to `rss_poller.py`. All 51 seeded items reached `EXTRACTED` with real markdown content in `raw_text` (spot-checked — substantive circular text present, some nav/share-link boilerplate from Firecrawl's markdown conversion, not blocking).

---

## 4. CURRENT STATE

- What works: Full pipeline runs end to end via `python main.py` — creates tables, seeds 8 sources, polls CBN + SEC RSS with dedup, fetches full content via Firecrawl for every PENDING item. Verified clean run (0 errors) after a fresh `rm regwatch.db`.
- What is broken or incomplete: Pipeline B (scraping NRS, NITDA, FRCN, NAICOM, LIRS) not started. IASB RSS not yet polled (deliberately excluded per plan until CBN/SEC proven — they now are, so IASB can be added). LLM classification/framing (Step 6+) not started. Reports and delivery not started.
- Any half-done work: None — Steps 1-5 are each fully working and verified.
- Notes:
  - CBN RSS feed confirmed working at `https://www.cbn.gov.ng/RSS/CircularsRSS.html` — live data verified, real items ingested
  - SEC circulars page confirmed at `https://sec.gov.ng/for-investors/keep-track-of-circulars/` — RSS feed at `sec.gov.ng/feeds/circulars.rss` — **known issue**: SEC's feed declares `<link>` entries resolving to `http://localhost/...` (a misconfiguration on SEC's end). Fix implemented in `poll_rss_source`: strip the feed-provided scheme/host via `urlparse`, keep only path+query, rebuild the URL against the trusted `source["url"]` domain from `sources.py`. Do not revert this — without it, Firecrawl rejects every SEC item with "URL must have a valid top-level domain."
  - IASB RSS confirmed available at `ifrs.org` — not yet wired into `run_rss_pipeline`'s filter (`s["name"] in ("CBN", "SEC")`)
  - NRS, NITDA, FRCN, NAICOM, LIRS all require scraping — each needs a source-specific parser (Pipeline B, not started)
  - FRCN website has known reliability issues (MySQL errors observed) — ICAN is the fallback
  - Item-level hashing hash input format is: `{source_name}|{title}|{url}|{published_date}` — confirmed deterministic via `utils/hashing.py` self-test
  - Firecrawl content quality spot-checked on a real SEC circular: substantive text, headings, deadlines, and links all present and usable for LLM classification; some repeated nav/breadcrumb/social-share boilerplate from the markdown conversion — not cleaned, not currently blocking, revisit only if it pollutes LLM output

---

## 5. OPEN DECISIONS

- **Azure OpenAI vs OpenAI API**: Using OpenAI API key for demo. Switch to Azure OpenAI on deployment. Do not hardcode either — the LLM client should be swappable via env var.
- **Delivery mechanism**: Email via SendGrid for demo. Microsoft Graph API for Teams/Outlook on production deployment. Build report generation first, delivery second.
- **NAICOM service line mapping**: With Risk Advisory dropped, NAICOM directives map to AI_DATA and AUDIT only. This is confirmed — do not add Risk Advisory back.
- **Named post-internship maintainer**: Not yet identified. System must be built simply enough for a non-engineer to maintain the source list and review logs.
- **PostgreSQL migration**: SQLite for now. Schema must be written to be PostgreSQL-compatible from day one — no SQLite-specific syntax that would break on migration.

---

## 6. NEXT STEPS (execution contract)

### Step 1 — Project bootstrap and database schema — ✅ DONE
- **Goal**: Installable project with working database schema and all tables created on first run
- **Input**: Empty project directory, requirements.txt to be created
- **Output**: `requirements.txt`, `.env.example`, `.gitignore`, `database/models.py`, `database/db.py` all working. Running `python main.py` creates the SQLite database with all tables.
- **How to implement**:
  - Create `requirements.txt` with: feedparser, firecrawl-py, openai, apscheduler, python-dotenv, requests
  - Create `.env.example` with: `GEMINI_API_KEY=`, `FIRECRAWL_API_KEY=`, `DATABASE_URL=regwatch.db`, `LOG_LEVEL=INFO`
  - Create `.gitignore` that excludes `.env`, `*.db`, `__pycache__`, `.env.local`
  - In `database/models.py`: define all six tables as SQL CREATE TABLE IF NOT EXISTS statements. Use standard SQL only — no SQLite-specific types that break on PostgreSQL. Use TEXT for strings, INTEGER for ints, REAL for floats, BOOLEAN as INTEGER (0/1).
  - In `database/db.py`: connection manager, `get_connection()`, `execute()`, `fetchall()`, `fetchone()` helpers
  - In `main.py`: import db, call `create_tables()` on startup, print confirmation
- **Done when**: `python main.py` runs without error and `regwatch.db` exists with all six tables visible via `sqlite3 regwatch.db .tables`
- **Do NOT**: Use any ORM (no SQLAlchemy, no Django ORM). Raw SQL only. Do not create any tables not in the schema. Do not write any ingestion code in this step.

### Step 2 — Utility layer: hashing and logging — ✅ DONE
- **Goal**: Reusable hashing and logging utilities that all other modules import
- **Input**: Completed Step 1
- **Output**: `utils/hashing.py` and `utils/logger.py` working and importable
- **How to implement**:
  - `utils/hashing.py`: single function `generate_item_hash(source_name, title, url, published_date) -> str`. Uses SHA-256. Input string format: `{source_name}|{title}|{url}|{published_date}`. Returns hex digest. Must be deterministic — same inputs always produce same hash.
  - `utils/logger.py`: structured logger using Python's built-in `logging` module. Log level from env var. Format: `[TIMESTAMP] [LEVEL] [MODULE] message`. No third-party logging libraries.
  - Write a quick test at the bottom of `hashing.py` under `if __name__ == "__main__"` that prints two hashes — one should be deterministic across runs.
- **Done when**: `python utils/hashing.py` prints consistent hashes. Logger imports cleanly in any module with `from utils.logger import get_logger`.
- **Do NOT**: Use any external hashing or logging libraries. Do not add any retry logic or caching here — that belongs in ingestion.

### Step 3 — Source registry — ✅ DONE
- **Goal**: Single source of truth for all monitored sources — their URLs, types, service lines, and pipeline assignment
- **Input**: Completed Steps 1 and 2
- **Output**: `ingestion/sources.py` with all sources defined as a list of dicts. Sources table populated in the database on first run.
- **How to implement**:
  - Define `SOURCES` as a list of dicts, one per source. Each dict has: `name`, `url`, `regulatory_body`, `country` (NG for all), `source_type` (REGULATORY_BODY or STANDARDS_BODY), `pipeline` (RSS or SCRAPE), `service_lines` (list), `reliability_score` (float), `feed_url` (for RSS sources, else None)
  - Sources to include:
    - CBN: pipeline RSS, feed_url `https://www.cbn.gov.ng/RSS/CircularsRSS.html`, service_lines [AI_DATA, CYBERSECURITY], reliability 0.95
    - SEC: pipeline RSS, feed_url `https://sec.gov.ng/feeds/circulars.rss`, service_lines [AUDIT, TAX], reliability 0.90
    - IASB: pipeline RSS, feed_url to be confirmed from ifrs.org, service_lines [AUDIT], reliability 0.95, source_type STANDARDS_BODY
    - NRS: pipeline SCRAPE, url `https://nrs.gov.ng`, service_lines [TAX], reliability 0.70
    - NITDA: pipeline SCRAPE, url `https://nitda.gov.ng`, service_lines [AI_DATA, CYBERSECURITY], reliability 0.65
    - FRCN: pipeline SCRAPE, url `https://financialreportingcouncil.gov.ng`, service_lines [AUDIT], reliability 0.50
    - NAICOM: pipeline SCRAPE, url `https://naicom.gov.ng`, service_lines [AI_DATA, AUDIT], reliability 0.60
    - LIRS: pipeline SCRAPE, url `https://lirs.gov.ng`, service_lines [TAX], reliability 0.65
  - Write `seed_sources(conn)` function that inserts all sources into the Sources table if they don't already exist (upsert on name)
  - Call `seed_sources()` from `main.py` after `create_tables()`
- **Done when**: Running `python main.py` populates the Sources table. `sqlite3 regwatch.db "SELECT name, pipeline, reliability_score FROM sources;"` shows all 8 sources.
- **Do NOT**: Hardcode source configs anywhere else in the codebase. All source config lives in `sources.py` only. Do not add any sources not listed above without explicit instruction.

### Step 4 — Pipeline A: RSS ingestion (CBN and SEC first) — ✅ DONE
- **Goal**: Working RSS poller that fetches CBN and SEC feeds, detects new items, stores them deduplicated
- **Input**: Completed Steps 1-3
- **Output**: `ingestion/rss_poller.py` working. Running it fetches real CBN and SEC items and stores them in the SourceItems table without duplicates.
- **How to implement**:
  - `poll_rss_source(source: dict, conn) -> list[dict]`: takes a source config dict, fetches its feed_url via feedparser, iterates entries, generates item hash for each, checks if hash exists in SourceItems, skips if exists, stores new items with status PENDING, returns list of new items
  - Hash input: `{source['name']}|{entry.title}|{entry.link}|{entry.get('published', '')}`
  - Store in SourceItems: source_id, title, url (from entry.link), published_date, item_hash, processing_status=PENDING, first_seen_at=now
  - `run_rss_pipeline(conn)`: iterates all RSS sources from SOURCES list, calls `poll_rss_source` for each, logs count of new items found per source
  - Add to `main.py`: call `run_rss_pipeline()` after seeding
- **Done when**: Running `python main.py` prints "CBN: N new items found", "SEC: N new items found". Second run prints 0 new items for both (deduplication working). `sqlite3 regwatch.db "SELECT source_id, title, processing_status FROM source_items LIMIT 10;"` shows real CBN circulars.
- **Do NOT**: Fetch full document content in this step. That is Step 5. Do not call the LLM in this step. Do not poll IASB yet — CBN and SEC only until those are proven.

### Step 5 — Full content fetch via Firecrawl — ✅ DONE
- **Goal**: For each PENDING item in SourceItems, fetch the full document text via Firecrawl and store it
- **Input**: Completed Step 4 with real PENDING items in the database
- **Output**: PENDING items updated with `raw_text` populated and status changed to EXTRACTED
- **How to implement**:
  - In `ingestion/rss_poller.py` add `fetch_full_content(item: dict, firecrawl_client) -> str`: calls Firecrawl scrape on item URL, returns markdown text. Handle errors gracefully — if Firecrawl fails, log the error, set item status to FETCH_FAILED, do not crash the pipeline.
  - After polling, iterate new items and fetch content for each. Update SourceItems: set raw_text, update processing_status to EXTRACTED, update last_seen_at
  - Firecrawl client initialised once from env var `FIRECRAWL_API_KEY`
  - Add rate limiting: 1 second sleep between Firecrawl calls to avoid hammering the API
- **Done when**: `sqlite3 regwatch.db "SELECT title, processing_status, length(raw_text) FROM source_items LIMIT 5;"` shows EXTRACTED status and non-zero raw_text length for CBN items.
- **Do NOT**: Pass raw_text to the LLM yet. Do not implement Firecrawl for scraping pipeline sources yet — that is Pipeline B in a later step. Do not remove FETCH_FAILED items — keep them for retry logic later.

---

## 7. HANDOFF VERIFICATION PROMPT

Before writing any code, the receiving agent must respond to:

"Summarize your understanding of: (1) what is already done in this project, (2) exactly what step you are about to implement, (3) what you must not touch or change, and (4) what done looks like for this step."

If the agent cannot answer all four parts specifically, it should re-read this document before proceeding.

---

## QUICK REFERENCE — Key Decisions Already Made

| Decision | Answer |
|---|---|
| Countries | Nigeria only (MVP) |
| Service lines | AI_DATA, TAX, AUDIT, CYBERSECURITY |
| Risk Advisory | Dropped — no team |
| Cloud | Dropped — too thin regulatory signal |
| Media monitoring | Phase 2 — not in current scope |
| Database (dev) | SQLite |
| Database (prod) | PostgreSQL on Azure |
| LLM (demo) | Gemini API |
| LLM (prod) | Azure OpenAI |
| Hashing strategy | Item-level SHA-256 only |
| Urgency levels | CRITICAL, HIGH, MEDIUM, LOW |
| Report audience | Analysts and managers only |
| Delivery (demo) | Email via SendGrid |
| Delivery (prod) | Microsoft Graph API |
| ORM | None — raw SQL only |
| Page-level hashing | Never |
