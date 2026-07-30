from datetime import datetime, timedelta, timezone
import os
import time

from firecrawl import Firecrawl

from ingestion.sources import SOURCES
from utils.hashing import generate_item_hash
from utils.logger import get_logger

logger = get_logger(__name__)

MAX_ITEM_AGE_DAYS = 180

LISTING_SCHEMA = {
    "type": "object",
    "properties": {
        "items": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "title": {"type": "string"},
                    "url": {"type": "string"},
                    "published_date": {"type": "string"},
                },
                "required": ["title", "url"],
            },
        },
    },
    "required": ["items"],
}


def get_firecrawl_client():
    return Firecrawl(api_key=os.getenv("FIRECRAWL_API_KEY"))


def scrape_source_listing(source, firecrawl_client):
    doc = firecrawl_client.scrape(
        source["url"],
        formats=[{
            "type": "json",
            "prompt": "Extract every circular, notice, directive, or news item listed on this page as a list. For each, include its title, the full absolute URL to the item, and its published date if shown, converted to YYYY-MM-DD format.",
            "schema": LISTING_SCHEMA,
        }],
    )
    return doc.json.get("items", [])


def poll_scrape_source(source, conn, firecrawl_client):
    row = conn.execute(
        "SELECT id FROM sources WHERE name = ?", (source["name"],)
    ).fetchone()
    source_id = row["id"]

    items = scrape_source_listing(source, firecrawl_client)
    new_items = []
    cutoff = datetime.now(timezone.utc) - timedelta(days=MAX_ITEM_AGE_DAYS)

    for entry in items:
        published = entry.get("published_date", "")
        try:
            published_dt = datetime.strptime(published, "%Y-%m-%d").replace(tzinfo=timezone.utc)
            if published_dt < cutoff:
                continue
        except ValueError:
            pass

        item_hash = generate_item_hash(source["name"], entry["title"], entry["url"], published)

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
            (source_id, entry["title"], entry["url"], published, item_hash, datetime.now(timezone.utc).isoformat()),
        )
        new_items.append(entry)

    conn.commit()
    return new_items


def run_scrape_pipeline(conn):
    firecrawl_client = get_firecrawl_client()
    scrape_sources = [s for s in SOURCES if s["pipeline"] == "SCRAPE"]

    for source in scrape_sources:
        try:
            new_items = poll_scrape_source(source, conn, firecrawl_client)
            logger.info(f"{source['name']}: {len(new_items)} new items found")
        except Exception as e:
            logger.error(f"Scrape failed for {source['name']}: {e}")
        time.sleep(1)
