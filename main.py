from database.db import get_connection
from database.models import create_tables
from ingestion.sources import seed_sources
from ingestion.rss_poller import run_rss_pipeline, run_content_fetch_pipeline
from ingestion.scraper import run_scrape_pipeline
from extraction.classifier import run_classification_pipeline
from extraction.framer import run_framing_pipeline
from reports.weekly import generate_weekly_report
from reports.delivery import send_weekly_email

def main():
    conn = get_connection()
    create_tables(conn)
    seed_sources(conn)
    run_rss_pipeline(conn)
    run_scrape_pipeline(conn)
    run_content_fetch_pipeline(conn)
    run_classification_pipeline(conn)
    run_framing_pipeline(conn)
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
    print("Full pipeline executed")

if __name__ == "__main__":
        main()