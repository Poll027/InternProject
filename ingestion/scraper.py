from datetime import datetime, timedelta, timezone
import asyncio
import json
import os
import time
from urllib.parse import urljoin

from crawl4ai import AsyncWebCrawler
from firecrawl import Firecrawl

from extraction.classifier import OPENROUTER_MODEL, get_openrouter_headers, post_to_openrouter
from ingestion.health import record_run_outcome
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
                "required": ["title", "url", "published_date"],
                "additionalProperties": False,
            },
        },
    },
    "required": ["items"],
    "additionalProperties": False,
}


def get_firecrawl_client():
    return Firecrawl(api_key=os.getenv("FIRECRAWL_API_KEY"))


def scrape_source_listing_firecrawl(source, firecrawl_client):
    doc = firecrawl_client.scrape(
        source["url"],
        formats=[{
            "type": "json",
            "prompt": "Extract every circular, notice, directive, or news item listed on this page as a list. For each, include its title, the full absolute URL to the item, and its published date if shown, converted to YYYY-MM-DD format.",
            "schema": LISTING_SCHEMA,
        }],
    )
    return doc.json.get("items", [])


def build_listing_prompt(source_url, markdown):
    return f"""Extract every circular, notice, directive, or news item listed on this page as a list. For each, include its title, the URL to the item (absolute, or relative to {source_url}), and its published date if shown, converted to YYYY-MM-DD format (empty string if not shown).

Page content (markdown):
{markdown}
"""


def extract_listing(source_url, markdown, headers):
    response = post_to_openrouter(
        {
            "model": OPENROUTER_MODEL,
            "messages": [{"role": "user", "content": build_listing_prompt(source_url, markdown)}],
            "response_format": {
                "type": "json_schema",
                "json_schema": {"name": "listing", "strict": True, "schema": LISTING_SCHEMA},
            },
        },
        headers,
    )
    content = response.json()["choices"][0]["message"]["content"]
    return json.loads(content).get("items", [])


async def _scrape_source_listing_crawl4ai(source, headers):
    async with AsyncWebCrawler() as crawler:
        result = await crawler.arun(source["url"])
        if not result.success:
            raise RuntimeError(result.error_message or "crawl failed")
        items = extract_listing(source["url"], str(result.markdown), headers)
        for item in items:
            item["url"] = urljoin(source["url"], item["url"])
        return items


def scrape_source_listing(source, firecrawl_client, headers):
    try:
        return scrape_source_listing_firecrawl(source, firecrawl_client)
    except Exception as e:
        logger.warning(f"Firecrawl failed for {source['name']}, falling back to crawl4ai: {e}")
        return asyncio.run(_scrape_source_listing_crawl4ai(source, headers))


def poll_scrape_source(source, conn, firecrawl_client, headers):
    row = conn.execute(
        "SELECT id FROM sources WHERE name = ?", (source["name"],)
    ).fetchone()
    source_id = row["id"]

    items = scrape_source_listing(source, firecrawl_client, headers)
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


def run_scrape_pipeline(conn, source_names=None):
    firecrawl_client = get_firecrawl_client()
    headers = get_openrouter_headers()
    scrape_sources = [s for s in SOURCES if s["pipeline"] == "SCRAPE" and (not source_names or s["name"] in source_names)]

    for source in scrape_sources:
        try:
            new_items = poll_scrape_source(source, conn, firecrawl_client, headers)
            logger.info(f"{source['name']}: {len(new_items)} new items found")
            record_run_outcome(conn, source["name"], found_count=len(new_items))
        except Exception as e:
            logger.error(f"Scrape failed for {source['name']}: {e}")
            record_run_outcome(conn, source["name"], error=e)
        time.sleep(1)
