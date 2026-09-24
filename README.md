# RegWatch

Internal regulatory intelligence tool for Deloitte Africa's Nigeria practice. It monitors official Nigerian regulatory sources, detects new circulars, directives, standards updates, and policy notices, classifies them by relevance to four service lines, ranks them by urgency, and generates evidence-backed briefings for internal analysts and managers.

Every finding includes a source link, evidence excerpt, and confidence score. This is a research accelerant, not a decision engine — output goes to analysts and managers only, never directly to partners or clients.

## Service lines

`AI_DATA`, `TAX`, `AUDIT`, `CYBERSECURITY`

## Sources

- **RSS (Pipeline A)**: CBN, SEC
- **Scrape via Firecrawl (Pipeline B)**: NRS, NITDA, FRCN, NAICOM, LIRS, IASB

## Pipeline

1. **rss** — poll CBN/SEC RSS feeds for new items
2. **scrape** — poll the 6 no-feed sources via Firecrawl structured extraction
3. **fetch** — fetch full document content for pending items via Firecrawl
4. **classify** — LLM classification per item into findings (service line, urgency, confidence) via OpenRouter
5. **frame** — LLM opportunity framing per finding (Opportunity / Recommended Action / Why Now)
6. **report** — generate weekly urgent-alert emails per service line
7. **monthly** — generate monthly digest emails per service line
8. **health** — check source health

Each stage is idempotent — reruns only touch items that are new or incomplete, based on DB state (hash existence, `processing_status`, or a null-check join), not "did we run today."

## Setup

```bash
pip install -r requirements.txt
cp .env.example .env   # fill in the values below
```

Environment variables (`.env`):

| Variable | Purpose |
|---|---|
| `OPENROUTER_API_KEY` | LLM classification and framing calls |
| `FIRECRAWL_API_KEY` | Web scraping and full-content fetch |
| `DATABASE_URL` | SQLite file path (default `regwatch.db`) |
| `LOG_LEVEL` | Logging verbosity |
| `SENDGRID_API_KEY` | Email delivery |
| `EMAIL_FROM` | Sender address for reports |
| `EMAIL_TO_AI_DATA` / `EMAIL_TO_TAX` / `EMAIL_TO_AUDIT` / `EMAIL_TO_CYBERSECURITY` | Comma-separated recipients per service line. A line with no recipients set is skipped for delivery and printed to stdout instead. |

## Usage

Run the full pipeline:

```bash
python main.py
```

Restrict to specific sources or stages:

```bash
python main.py --sources CBN,SEC --stages rss,fetch,classify
```

Stages: `rss`, `scrape`, `fetch`, `classify`, `frame`, `report`, `monthly`, `health`.

## Dashboard

A Flask frontend for browsing findings by service line:

```bash
python frontend/app.py
```

## Project layout

```
regwatch/
├── main.py               entry point, runs the full pipeline
├── database/
│   ├── models.py          SQLite schema (raw SQL, no ORM)
│   └── db.py              connection and query helpers
├── ingestion/
│   ├── sources.py         source registry (single source of truth)
│   ├── rss_poller.py      Pipeline A: RSS polling + full-content fetch
│   ├── scraper.py         Pipeline B: Firecrawl structured scraping
│   └── health.py          source health checks
├── extraction/
│   ├── classifier.py      LLM classification (OpenRouter)
│   └── framer.py          LLM opportunity framing (OpenRouter)
├── reports/
│   ├── weekly.py          weekly urgent-alert report generation
│   ├── monthly.py         monthly digest generation
│   └── delivery.py        recipient lookup + SendGrid delivery
├── utils/
│   ├── hashing.py         item-level SHA-256 hashing
│   └── logger.py          structured logging (console + rotating file)
└── frontend/              Flask dashboard
```

## Notes

- Database: SQLite for local dev, PostgreSQL on Azure planned for production. Schema is written to be PostgreSQL-compatible (no SQLite-specific types).
- LLM: OpenRouter (`deepseek/deepseek-v3.2`), called directly via `requests` — no SDK. Azure OpenAI planned for production.
- Hashing is always item-level (`source_name|title|url|published_date`), never page-level.
- Scope: Nigeria only (MVP). Expansion to South Africa, Kenya, and Ghana is a later phase, as is media/news monitoring — neither is in scope currently.
