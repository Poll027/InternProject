from utils.db_filters import in_clause
from utils.logger import get_logger

logger = get_logger(__name__)

EMPTY_RUN_ALERT_THRESHOLD = 5
FAILED_RUN_ALERT_THRESHOLD = 3


def record_run_outcome(conn, source_name, found_count=None, error=None):
    if error is not None:
        conn.execute(
            "UPDATE sources SET consecutive_failed_runs = consecutive_failed_runs + 1 WHERE name = ?",
            (source_name,),
        )
    elif found_count > 0:
        conn.execute(
            "UPDATE sources SET consecutive_empty_runs = 0, consecutive_failed_runs = 0 WHERE name = ?",
            (source_name,),
        )
    else:
        conn.execute(
            "UPDATE sources SET consecutive_empty_runs = consecutive_empty_runs + 1, consecutive_failed_runs = 0 WHERE name = ?",
            (source_name,),
        )
    conn.commit()


def check_source_health(conn, source_names=None):
    clause, params = in_clause("name", source_names)
    rows = conn.execute(
        f"SELECT name, consecutive_empty_runs, consecutive_failed_runs FROM sources WHERE 1=1{clause}",
        params,
    ).fetchall()
    for row in rows:
        if row["consecutive_failed_runs"] >= FAILED_RUN_ALERT_THRESHOLD:
            logger.critical(
                f"{row['name']}: {row['consecutive_failed_runs']} consecutive failed runs — needs attention"
            )
        elif row["consecutive_empty_runs"] >= EMPTY_RUN_ALERT_THRESHOLD:
            logger.critical(
                f"{row['name']}: {row['consecutive_empty_runs']} consecutive runs with 0 new items — possible silent failure"
            )
