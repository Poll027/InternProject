CREATE_TABLES_SQL = """
CREATE TABLE IF NOT EXISTS sources (
id INTEGER PRIMARY KEY,
name TEXT UNIQUE NOT NULL,
url TEXT,
feed_url TEXT,
regulatory_body TEXT,
country TEXT NOT NULL,
source_type TEXT NOT NULL,
pipeline TEXT NOT NULL,
service_lines TEXT NOT NULL,
reliability_score REAL NOT NULL,
created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS source_items (
id INTEGER PRIMARY KEY,
source_id INTEGER NOT NULL REFERENCES sources(id),
title text not null,
url TEXT NOT NULL,
published_date TEXT,
item_hash TEXT UNIQUE NOT NULL,
raw_text TEXT,
processing_status TEXT NOT NULL DEFAULT 'PENDING',
first_seen_at TEXT NOT NULL,
last_seen_at TEXT
);

CREATE TABLE IF NOT EXISTS findings (
id INTEGER PRIMARY KEY,
source_item_id INTEGER NOT NULL REFERENCES source_items(id),
service_line TEXT NOT NULL,
urgency TEXT NOT NULL,
headline TEXT,
summary TEXT NOT NULL,
confidence_score REAL NOT NULL,
source_url TEXT NOT NULL,
evidence_excerpt TEXT NOT NULL,
created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS opportunity_framings (
id INTEGER PRIMARY KEY,
finding_id INTEGER NOT NULL REFERENCES findings (id),
service_line TEXT NOT NULL,
framing_text TEXT NOT NULL,
created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS reports (
id INTEGER PRIMARY KEY,
report_type TEXT NOT NULL,
period_start TEXT,
period_end TEXT,
generated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS report_findings (
id INTEGER PRIMARY KEY,
report_id INTEGER NOT NULL REFERENCES reports(id),
finding_id INTEGER NOT NULL REFERENCES findings(id)
);
"""

def create_tables (conn):
    conn.executes@cript(CREATE_TABLES_SQL)
    conn.commit()