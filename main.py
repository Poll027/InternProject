import argparse

from database.db import get_connection
from database.models import create_tables
from ingestion.sources import seed_sources, SOURCES
from ingestion.rss_poller import run_rss_pipeline, run_content_fetch_pipeline
from ingestion.scraper import run_scrape_pipeline
from extraction.classifier import run_classification_pipeline
from extraction.framer import run_framing_pipeline
from reports.weekly import generate_weekly_report
from reports.delivery import send_weekly_email

STAGES = ("rss", "scrape", "fetch", "classify", "frame", "report")


def parse_args():
    parser = argparse.ArgumentParser(description="Run the RegWatch pipeline.")
    parser.add_argument(
        "--sources",
        help=f"Comma-separated source names to restrict to, from {sorted(s['name'] for s in SOURCES)} (default: all)",
    )
    parser.add_argument(
        "--stages",
        help=f"Comma-separated stages to run, from {STAGES} (default: all)",
    )
    args = parser.parse_args()

    if args.sources:
        unknown = set(args.sources.split(",")) - {s["name"] for s in SOURCES}
        if unknown:
            parser.error(f"Unknown source(s): {', '.join(sorted(unknown))}")
    if args.stages:
        unknown = set(args.stages.split(",")) - set(STAGES)
        if unknown:
            parser.error(f"Unknown stage(s): {', '.join(sorted(unknown))}")

    return args


def main():
    args = parse_args()
    source_names = args.sources.split(",") if args.sources else None
    stages = args.stages.split(",") if args.stages else STAGES

    conn = get_connection()
    create_tables(conn)
    seed_sources(conn)

    if "rss" in stages:
        run_rss_pipeline(conn, source_names)
    if "scrape" in stages:
        run_scrape_pipeline(conn, source_names)
    if "fetch" in stages:
        run_content_fetch_pipeline(conn, source_names)
    if "classify" in stages:
        run_classification_pipeline(conn, source_names)
    if "frame" in stages:
        run_framing_pipeline(conn, source_names)
    if "report" in stages:
        email_body, attachment_path = generate_weekly_report(conn)
        if email_body:
            sent = False
            try:
                sent = send_weekly_email(email_body, attachment_path)
            except Exception as e:
                print(f"Email delivery failed: {e}")
            if not sent:
                print(email_body)
                print(f"\nAttachment saved to: {attachment_path}")

    print(f"Pipeline executed (stages: {','.join(stages)}; sources: {','.join(source_names) if source_names else 'all'})")

if __name__ == "__main__":
        main()
