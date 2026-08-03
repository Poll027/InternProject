from datetime import datetime, timezone
import asyncio
from urllib.parse import urljoin, urlparse
import feedparser

from crawl4ai import AsyncWebCrawler, CrawlerRunConfig
from crawl4ai.processors.pdf import PDFCrawlerStrategy, PDFContentScrapingStrategy
from ingestion.sources import SOURCES
from utils.db_filters import in_clause
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


def run_rss_pipeline(conn, source_names=None):
    rss_sources = [s for s in SOURCES if s["pipeline"] == "RSS" and (not source_names or s["name"] in source_names)]
    for source in rss_sources:
        new_items = poll_rss_source(source, conn)
        logger.info(f"{source['name']}: {len(new_items)} new items found")

PDF_CONFIG = CrawlerRunConfig(scraping_strategy=PDFContentScrapingStrategy())


async def _fetch_one(item, html_crawler, pdf_crawler):
    if item["url"].lower().endswith(".pdf"):
        result = await pdf_crawler.arun(item["url"], config=PDF_CONFIG)
        text = str(result.markdown)
        # PDFCrawlerStrategy reports html="Scraper will handle the real work" as a
        # stub, which trips crawl4ai's anti-bot "near-empty content" heuristic on
        # every PDF regardless of actual content — check extracted text instead of
        # result.success.
        if not text.strip():
            raise RuntimeError(result.error_message or "empty PDF content")
        return text

    result = await html_crawler.arun(item["url"])
    if not result.success:
        raise RuntimeError(result.error_message or "crawl failed")
    return str(result.markdown)


async def _fetch_all_content(conn, pending_items):
    async with AsyncWebCrawler() as html_crawler, AsyncWebCrawler(crawler_strategy=PDFCrawlerStrategy()) as pdf_crawler:
        for item in pending_items:
            try:
                raw_text = await _fetch_one(item, html_crawler, pdf_crawler)
                conn.execute(
                    "UPDATE source_items SET raw_text = ?, processing_status = 'EXTRACTED', last_seen_at = ? WHERE id = ?",
                    (raw_text, datetime.now(timezone.utc).isoformat(), item["id"]),
                )
            except Exception as e:
                logger.error(f"Crawl4AI failed for item {item['id']}: {e}")
                conn.execute("UPDATE source_items SET processing_status = 'FETCH_FAILED' WHERE id = ?",
                             (item["id"],),)

            conn.commit()

def run_content_fetch_pipeline(conn, source_names=None):
    clause, params = in_clause("sources.name", source_names)
    pending_items = conn.execute(
        f"""
        SELECT source_items.id, source_items.url
        FROM source_items
        JOIN sources ON sources.id = source_items.source_id
        WHERE source_items.processing_status = 'PENDING'{clause}
        """,
        params,
    ).fetchall()
    asyncio.run(_fetch_all_content(conn, pending_items))
