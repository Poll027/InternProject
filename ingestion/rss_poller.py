from datetime import datetime, timezone
import os
import time
from urllib.parse import urljoin, urlparse
import feedparser

from firecrawl import Firecrawl
from ingestion.sources import SOURCES
from utils.hashing import generate_item_hash
from utils.logger import get_logger

logger = get_logger(__name__)

def poll_rss_source(source, conn):
    row = conn.execute(
        "SELECT id FROM sources WHERE name = ?", (source["name"],)
    ).fetchone()
    source_id = row["id"]

    feed = feedparser.parse(source["feed_url"])
    new_items = []

    for entry in feed.entries:
        published = entry.get("published", "")
        parsed_link = urlparse(entry.link)
        link_path = parsed_link.path
        if parsed_link.query:
            link_path += "?" + parsed_link.query
        item_url = urljoin(source["url"], link_path)
        item_hash = generate_item_hash(source["name"], entry.title, item_url, published)

        exists = conn.execute(
            "SELECT 1 FROM source_items WHERE item_hash = ?", (item_hash,)
        ).fetchone()
        if exists:
            continue

        conn.execute(
            """
            INSERT INTO source_items
            (source_id, title, url, published_date, item_hash, processing_status, first_seen_at)
            VALUES (?, ?, ?, ?, ?, 'PENDING', ?)
            """,
            (source_id, entry.title, item_url, published, item_hash, datetime.now(timezone.utc).isoformat()),
        )
        new_items.append(entry)

    conn.commit()
    return new_items


def run_rss_pipeline(conn):
    rss_sources = [s for s in SOURCES if s["pipeline"] == "RSS" and s["name"] in ("CBN", "SEC")]
    for source in rss_sources:
        new_items = poll_rss_source(source, conn)
        logger.info(f"{source['name']}: {len(new_items)} new items found")

def get_firecrawl_client():
    return Firecrawl(api_key=os.getenv("FIRECRAWL_API_KEY"))

def fetch_full_content(item, firecrawl_client):
    doc = firecrawl_client.scrape(item["url"], formats=["markdown"])
    return doc.markdown

def run_content_fetch_pipeline(conn):
    firecrawl_client = get_firecrawl_client()
    pending_items = conn.execute(
        "SELECT id, url FROM source_items WHERE processing_status = 'PENDING'"
    ).fetchall()

    for item in pending_items:
        try:
            raw_text = fetch_full_content(item, firecrawl_client)
            conn.execute(
                "UPDATE source_items SET raw_text = ?, processing_status = 'EXTRACTED', last_seen_at = ? WHERE id = ?",
                (raw_text, datetime.now(timezone.utc).isoformat(), item["id"]),
            )
        except Exception as e:
            logger.error(f"Firecrawl failed for item {item['id']}: {e}")
            conn.execute("UPDATE source_items SET processing_status = 'FETCH_FAILED' WHERE id = ?",
                         (item["id"],),)
            
        conn.commit()
        time.sleep(1)

        