from reports.weekly import build_email_body, get_days_since_last_report, get_period_findings, persist_report
from utils.logger import get_logger

logger = get_logger(__name__)


def generate_monthly_report(conn, default_days=30):
    days = get_days_since_last_report(conn, "MONTHLY", default_days)
    findings = get_period_findings(conn, days)

    if not findings:
        logger.info("No findings since the last monthly report — skipping.")
        return None, None

    email_body = build_email_body(findings, period_label="month")
    attachment_path = persist_report(conn, "MONTHLY", findings, "monthly", days)

    logger.info(f"Monthly report generated: {len(findings)} findings, attachment at {attachment_path}")
    return email_body, attachment_path
