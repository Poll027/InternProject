from datetime import datetime, timezone

SOURCES = [
    {
     "name": "CBN",
     "url": "https://www.cbn.gov.ng",
     "feed_url":"https://www.cbn.gov.ng/RSS/CircularsRss.html",
     "regulatory_body": "Central Bank of Nigeria",
     "country": "Nigeria",
     "source_type": "REGULATORY_BODY",
     "pipeline": "RSS",
     "service_lines":["AI_DATA", "CYBERSECURITY"],
     "reliability_score": 0.95,
     },
     {
        "name": "SEC",
        "url": "https://sec.gov.ng/for-investors/keep-track-of-circulars/",
        "feed_url": "https://sec.gov.ng/feeds/circulars.rss",
        "regulatory_body": "Securities and Exchange Commission",
        "country": "NG",
        "source_type": "REGULATORY_BODY",
        "pipeline": "RSS",
        "service_lines": ["AUDIT", "TAX"],
        "reliability_score": 0.90,
     },
     {
        "name": "IASB",
        "url": "https://www.ifrs.org/news-and-events/updates/iasb/",
        "feed_url": None,
        "regulatory_body": "International Accounting Standards Board",
        "country": "NG",
        "source_type": "STANDARDS_BODY",
        "pipeline": "SCRAPE",
        "service_lines": ["AUDIT"],
        "reliability_score": 0.95,
    },
    {
        "name": "NRS",
        "url": "https://nrs.gov.ng",
        "feed_url": None,
        "regulatory_body": "Nigeria Revenue Service",
        "country": "NG",
        "source_type": "REGULATORY_BODY",
        "pipeline": "SCRAPE",
        "service_lines": ["TAX"],
        "reliability_score": 0.70,
    },
    {
        "name": "NITDA",
        "url": "https://nitda.gov.ng",
        "feed_url": None,
        "regulatory_body": "National Information Technology Development Agency",
        "country": "NG",
        "source_type": "REGULATORY_BODY",
        "pipeline": "SCRAPE",
        "service_lines": ["AI_DATA", "CYBERSECURITY"],
        "reliability_score": 0.65,
    },
    {
        "name": "FRCN",
        "url": "https://www.frcnigeria.gov.ng",
        "feed_url": None,
        "regulatory_body": "Financial Reporting Council of Nigeria",
        "country": "NG",
        "source_type": "REGULATORY_BODY",
        "pipeline": "SCRAPE",
        "service_lines": ["AUDIT"],
        "reliability_score": 0.50,
    },
    {
        "name": "NAICOM",
        "url": "https://naicom.gov.ng",
        "feed_url": None,
        "regulatory_body": "National Insurance Commission",
        "country": "NG",
        "source_type": "REGULATORY_BODY",
        "pipeline": "SCRAPE",
        "service_lines": ["AI_DATA", "AUDIT"],
        "reliability_score": 0.60,
    },
    {
        "name": "LIRS",
        "url": "https://lirs.gov.ng",
        "feed_url": None,
        "regulatory_body": "Lagos Inland Revenue Service",
        "country": "NG",
        "source_type": "REGULATORY_BODY",
        "pipeline": "SCRAPE",
        "service_lines": ["TAX"],
        "reliability_score": 0.65,
    },
]

def seed_sources(conn):
    for source in SOURCES:
        conn.execute(
            """
            INSERT OR IGNORE INTO sources
            (name, url, feed_url, regulatory_body, country, source_type, pipeline, service_lines, reliability_score, created_at)
            VALUES(?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                source["name"],
                source["url"],
                source["feed_url"],
                source["regulatory_body"],
                source["country"],
                source["source_type"],
                source["pipeline"],
                ",".join(source["service_lines"]),
                source["reliability_score"],
                datetime.now(timezone.utc).isoformat()
            )
        )

    conn.commit()