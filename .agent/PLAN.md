# RegWatch — Agent Handoff Plan
**Last updated by**: Claude Code (terminal session)
**Last updated at**: 2026-07-29
**Current status**: STEPS_1_TO_9_COMPLETE (weekly report only, no monthly; Pipeline B live for all 6 scrape sources) — next up: scheduling, SendGrid delivery, or monthly report

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
  - LLM extraction and opportunity framing via OpenRouter (`deepseek/deepseek-v3.2`), called directly with `requests` (already a dependency, no SDK needed) — chosen for cost (~$0.02 per full classification run at current volume) over Gemini's free-tier daily quota wall and OpenAI. Azure OpenAI still planned for production. Note: `google-generativeai` and `google-genai` were both tried and dropped — do not reintroduce.
  - `apscheduler` — scheduling daily ingestion runs
  - `python-dotenv` — environment variable management
  - `requests` — HTTP calls where needed
- **Hosting**: Azure Functions (production). Local for demo.
- **LLM strategy**: OpenRouter (`deepseek/deepseek-v3.2`) for the demo build — swapped from Gemini after hitting a restrictive free-tier daily quota (20 req/day observed), and from OpenAI before that (never implemented, cost-compared only). Switch to Azure OpenAI when deploying to Deloitte's Azure tenant.

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
│   ├── rss_poller.py            ← Pipeline A: CBN, SEC RSS feeds (IASB is NOT RSS — see corrections below)
│   ├── scraper.py               ← Pipeline B: NRS, NITDA, FRCN, NAICOM, LIRS, IASB (6 sources) — DONE
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
    └── logger.py                ← structured logging, console + rotating file (regwatch.log)
```

Note: `reports/monthly.py` listed above does not exist yet — only `weekly.py` is built.

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
- **Step 2 done**: `utils/hashing.py` (`generate_item_hash`, SHA-256, deterministic — verified) and `utils/logger.py` (`get_logger`, stdlib `logging`, format `[TIMESTAMP] [LEVEL] [MODULE] message`) both working and importable. **Updated 2026-07-25**: `get_logger` now also attaches a `RotatingFileHandler` (`regwatch.log`, 5MB cap, 3 backups) alongside the console handler — logs persist across runs, capped total disk use (~20MB), no manual cleanup needed. Both handlers share the same duplicate-handler guard (`if not logger.handlers`).
- **Step 3 done**: `ingestion/sources.py` — all 8 sources defined in `SOURCES`, `seed_sources(conn)` populates the `sources` table via `INSERT OR IGNORE` (idempotent on `name`). Verified all 8 rows present with correct `pipeline`/`reliability_score`.
- **Step 4 done**: `ingestion/rss_poller.py` — `poll_rss_source` + `run_rss_pipeline`, CBN and SEC only (IASB still excluded per plan). Verified: first run found real new items, second run found 0 for both (hash dedup confirmed working).
- **Step 5 done**: `fetch_full_content`, `get_firecrawl_client`, `run_content_fetch_pipeline` added to `rss_poller.py`. All 51 seeded items reached `EXTRACTED` with real markdown content in `raw_text` (spot-checked — substantive circular text present, some nav/share-link boilerplate from Firecrawl's markdown conversion, not blocking).
- **Step 6 done**: `extraction/classifier.py` — `classify_item`/`run_classification_pipeline`, calls OpenRouter (`deepseek/deepseek-v3.2`) directly via `requests` (no SDK) with `response_format: json_schema` (`strict: true`) to force valid structured output. `confidence_score` on each finding = `source.reliability_score * llm_confidence` (composite formula from the completed decisions above). Verified: 83 findings written across 51 items, zero duplicate `(source_item_id, service_line)` pairs, `source_url`/`evidence_excerpt` populated on every row per the hard constraint. **Updated 2026-07-25**: added a `headline` field (schema + prompt + INSERT) — a punchy ~15-word one-liner for email digests, separate from the longer `summary`. `findings.headline` column added via `ALTER TABLE` on the live DB (nullable, existing 83 rows have `NULL` and are not retroactively backfilled — reports fall back to `summary` for those).
- **Step 7 done**: `extraction/framer.py` — `frame_finding`/`run_framing_pipeline`, second half of the two-prompt architecture. Plain-text completion (no JSON schema needed, single prose field). Prompt enforces internal-audience-only framing and three labeled sections (Opportunity / Recommended Action / Why Now), with explicit instruction to scale depth to the finding's actual significance — verified working (CRITICAL finding got a multi-section breakdown with immediate/mid-term action tiers; LOW finding stayed to a few sentences with a 6-month re-review note). Un-framed findings detected via `LEFT JOIN opportunity_framings ... WHERE id IS NULL` — no extra status column needed, naturally idempotent. Verified: 83/83 findings framed, reruns produce 0 new work as expected. Known issue (not fixed): the model adds its own memo-style formatting (`**INTERNAL BRIEFING NOTE**`, `FROM:`/`DATE:`/`CLASSIFICATION:` headers) unprompted — harmless in the DB column, but reads too formal if dropped verbatim into an email; `reports/weekly.py` works around this by using `findings.headline`/`summary` for the email body and reserving `framing_text` for the full `.txt` attachment only.
- **Step 8 done (partial — weekly only)**: `reports/weekly.py` — `get_period_findings`, `build_email_body`, `build_attachment_text`, `generate_weekly_report`. Email body = top 10 findings by urgency (CRITICAL first) then `confidence_score`, using the short `headline` (bare-bones, scannable). Full `.txt` attachment = every finding from the period (default last 7 days), all urgency levels, with complete `summary` + `framing_text` + `source_url`, written to `reports/output/weekly_<date>.txt` (gitignored — generated output). Writes one `reports` row and one `report_findings` row per *included* finding (all of them, not just the top 10 — the attachment counts as part of the same report package). Wired into `main.py` after the framing pipeline; prints the email body and attachment path to console (actual sending not built — see Delivery in Open Decisions). Verified: 50 real findings in a live run, correct top-10 ordering, attachment file written and readable. `reports/monthly.py` (per-service-line monthly digest) is NOT started.
- **Step 9 done**: `ingestion/scraper.py` — Pipeline B, all 6 no-feed sources (NRS, NITDA, FRCN, NAICOM, LIRS, IASB). Uses Firecrawl's structured JSON extraction (`formats=[{"type": "json", "prompt": ..., "schema": LISTING_SCHEMA}]`, result on `doc.json`) instead of hand-written CSS-selector scrapers — one shared prompt generalizes across all 6 unrelated site layouts, no per-site code. `poll_scrape_source` writes to `source_items` exactly like `poll_rss_source` does (same columns, same `PENDING` status, same hash-based dedup) — Steps 5/6/7 needed zero changes, since they already process `source_items` generically regardless of which pipeline discovered a row. First live run: 0 errors, real results across all 6 sources. **Bug found and fixed during that first run**: IASB's page is an un-paginated 16-year archive (2010-2026) — Firecrawl faithfully extracted all 203 items, 125 of which got fully processed (real Firecrawl + OpenRouter spend) before being caught, since `poll_scrape_source` had no age filter. Fixed with `MAX_ITEM_AGE_DAYS = 180` in `poll_scrape_source` (skips anything older, applies to all 6 scrape sources, not just IASB) plus a prompt change requesting `published_date` in `YYYY-MM-DD` specifically (parseable via `datetime.strptime`, no date-parsing library needed). 197 stale IASB `source_items` and 207 cascading `findings`/`opportunity_framings`/`report_findings` rows deleted retroactively per explicit instruction. **Do not remove the age cutoff** — any future archive-style source will hit the same failure mode without it.

---

## 4. CURRENT STATE

- What works: Full pipeline runs end to end via `python main.py` — creates tables, seeds 8 sources, polls CBN + SEC via RSS and all 6 remaining sources (NRS, NITDA, FRCN, NAICOM, LIRS, IASB) via Firecrawl scraping, fetches full content via Firecrawl for every PENDING item, classifies every EXTRACTED item into `findings` via OpenRouter/DeepSeek, frames every un-framed finding into `opportunity_framings`, and generates a weekly report (bare-bones email body + full `.txt` attachment). **All 8 sources are now live** — verified clean run (0 errors) across the whole pipeline. All six stages are independently idempotent — each queries DB state (hash existence, `processing_status`, or a `LEFT JOIN` null-check) rather than "did we run today," so reruns only ever touch what's genuinely new or incomplete. Logging persists to `regwatch.log` (rotating), not just console.
- What is broken or incomplete: `reports/monthly.py` not started. Actual delivery (SendGrid/email sending) not started — `main.py` only prints the report and saves the attachment locally. `apscheduler` is an unused dependency — nothing runs on a schedule yet, only manual `python main.py`. `google-genai`/Gemini fully removed; do not reintroduce. FRCN returned 0 items on its first scrape run — unclear yet whether that's genuinely nothing new or FRCN's known site reliability issues silently returning an empty page; not investigated further, revisit if it stays at 0 across multiple runs.
- Any half-done work: None — Steps 1-7, the weekly half of Step 8, and Step 9 are each fully working and verified.
- Transient issues observed in one run (not code bugs, no action needed): a momentary DNS resolution failure hit both `api.firecrawl.dev` and `openrouter.ai` mid-run, and Firecrawl's rate limit was briefly hit during a large content-fetch backlog. Both were absorbed correctly by the existing per-item `try/except` pattern — affected items simply stayed retriable on the next run.
- Performance note: DeepSeek V3.2 via OpenRouter has highly variable latency per call (observed 15s to 5+ minutes per classification/framing call, average ~40s) — not the deliberate rate-limit sleep (2s), but actual API/routing latency. Acceptable for a background-agent use case (explicitly confirmed acceptable by the project owner) but would need a timeout/retry or provider-routing pin (`provider: {sort: "throughput"}`) if this ever needs to run synchronously or against a much larger daily volume.
- Notes:
  - CBN RSS feed confirmed working at `https://www.cbn.gov.ng/RSS/CircularsRSS.html` — live data verified, real items ingested
  - SEC circulars page confirmed at `https://sec.gov.ng/for-investors/keep-track-of-circulars/` — RSS feed at `sec.gov.ng/feeds/circulars.rss` — **known issue**: SEC's feed declares `<link>` entries resolving to `http://localhost/...` (a misconfiguration on SEC's end). Fix implemented in `poll_rss_source`: strip the feed-provided scheme/host via `urlparse`, keep only path+query, rebuild the URL against the trusted `source["url"]` domain from `sources.py`. Do not revert this — without it, Firecrawl rejects every SEC item with "URL must have a valid top-level domain."
  - **Correction (2026-07-25)**: earlier notes claiming "IASB RSS confirmed available at ifrs.org" were wrong — never actually verified, just carried forward from the original scope doc. Checked directly: neither `ifrs.org/news-and-events/news/` nor `.../updates/iasb/` expose an RSS/Atom autodiscovery link; the only real feed IFRS Foundation publishes is an unrelated podcast feed. `sources.py` and the live `sources` table have been corrected — IASB is now `pipeline: SCRAPE`, `url` pointed at the actual IASB updates page, `feed_url` stays `None`. IASB is Pipeline B like the other five, not a Pipeline A quick-add.
  - NRS, NITDA, FRCN, NAICOM, LIRS, and now IASB all require scraping — each needs a source-specific parser (Pipeline B, not started) — **6 of 8 sources**, not 5
  - FRCN website has known reliability issues (MySQL errors observed) — ICAN is the fallback
  - Item-level hashing hash input format is: `{source_name}|{title}|{url}|{published_date}` — confirmed deterministic via `utils/hashing.py` self-test
  - Firecrawl content quality spot-checked on a real SEC circular: substantive text, headings, deadlines, and links all present and usable for LLM classification; some repeated nav/breadcrumb/social-share boilerplate from the markdown conversion — not cleaned, not currently blocking, revisit only if it pollutes LLM output

---

## 5. OPEN DECISIONS

- **Azure OpenAI vs OpenAI API**: Using OpenAI API key for demo. Switch to Azure OpenAI on deployment. Do not hardcode either — the LLM client should be swappable via env var.
- **Delivery mechanism**: Email via SendGrid for demo. Microsoft Graph API for Teams/Outlook on production deployment. Build report generation first, delivery second. Report generation (weekly) is now done — `generate_weekly_report` returns `(email_body, attachment_path)` but nothing sends it anywhere yet; `main.py` just prints it. SendGrid wiring is the next real piece of this item.
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
  - Create `requirements.txt` with: feedparser, firecrawl-py, apscheduler, python-dotenv, requests (no LLM SDK — OpenRouter is called directly via `requests`)
  - Create `.env.example` with: `OPENROUTER_API_KEY=`, `FIRECRAWL_API_KEY=`, `DATABASE_URL=regwatch.db`, `LOG_LEVEL=INFO`
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

### Step 6 — LLM classification — ✅ DONE
- **Goal**: For each EXTRACTED source_item, judge relevance to the four service lines, urgency, and a confidence sub-score; write one row per relevant service line into `findings`
- **Input**: Completed Step 5 with real EXTRACTED items
- **Output**: `extraction/classifier.py` — `build_prompt`, `classify_item`, `run_classification_pipeline`, `get_openrouter_headers`, `OPENROUTER_MODEL`
- **How it was implemented**:
  - Query `source_items` joined to `sources` (for `reliability_score`) `WHERE processing_status = 'EXTRACTED'`
  - One OpenRouter call per item, `response_format: {type: "json_schema", json_schema: {strict: true, schema: CLASSIFICATION_SCHEMA}}` — forces valid JSON matching `{relevant, findings: [{service_line, urgency, summary, evidence_excerpt, confidence}]}`, `additionalProperties: false` at every level (required for strict mode)
  - `confidence_score` on the inserted `findings` row = `item.reliability_score * finding.confidence` — the composite formula from the completed decisions
  - On success, `source_items.processing_status` → `CLASSIFIED`; on failure, logged and left as `EXTRACTED` so it's naturally retried next run
- **Done when**: `sqlite3 regwatch.db "SELECT service_line, urgency, count(*) FROM findings GROUP BY service_line, urgency;"` shows a real distribution across all four service lines. Verified.
- **Do NOT**: Reintroduce `google-generativeai` or `google-genai` (both dropped — Gemini's free tier daily quota, observed as low as 20 req/day, made it unworkable). Do not add an LLM SDK dependency — `requests` direct-to-OpenRouter is deliberate.

### Step 7 — Opportunity framing — ✅ DONE
- **Goal**: For each finding with no existing framing, generate an internal "what should we do about this" narrative and write it to `opportunity_framings`
- **Input**: Completed Step 6 with real rows in `findings`
- **Output**: `extraction/framer.py` — `build_framing_prompt`, `frame_finding`, `run_framing_pipeline`
- **How it was implemented**:
  - Reuses `OPENROUTER_MODEL` and `get_openrouter_headers()` from `classifier.py` via import rather than duplicating them
  - Un-framed findings found via `findings LEFT JOIN opportunity_framings ... WHERE opportunity_framings.id IS NULL` — no new status column needed
  - Plain-text completion (no JSON schema — single prose field, schema would be pure overhead)
  - Prompt enforces: internal-audience-only framing (never client/partner-facing, per the hard constraints), three labeled sections (Opportunity / Recommended Action / Why Now), and explicit instruction to scale depth/length to the finding's actual significance
- **Done when**: `sqlite3 regwatch.db "SELECT count(*) FROM opportunity_framings;"` equals the `findings` count. Verified 83/83, and spot-checked that a CRITICAL finding produced a substantially deeper framing than a LOW finding.
- **Do NOT**: Add a JSON schema to this step — it was deliberately left as plain text. Do not skip the internal-audience instruction in the prompt.

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
| LLM (demo) | OpenRouter, `deepseek/deepseek-v3.2` |
| LLM (prod) | Azure OpenAI |
| Hashing strategy | Item-level SHA-256 only |
| Urgency levels | CRITICAL, HIGH, MEDIUM, LOW |
| Report audience | Analysts and managers only |
| Delivery (demo) | Email via SendGrid |
| Delivery (prod) | Microsoft Graph API |
| ORM | None — raw SQL only |
| Page-level hashing | Never |
