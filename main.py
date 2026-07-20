from database.db import get_connection
from database.models import create_tables
from ingestion.sources import seed_sources
from ingestion.rss_poller import run_rss_pipeline, run_content_fetch_pipeline
from extraction.classifier import run_classification_pipeline

def main():
    conn = get_connection()
    create_tables(conn)
    seed_sources(conn)
    run_rss_pipeline(conn)
    run_content_fetch_pipeline(conn)
    run_classification_pipeline(conn)
    print("Full pipeline executed")

if __name__ == "__main__":
        main()