from extraction.classifier import SERVICE_LINES
from reports.weekly import build_email_body, get_days_since_last_report, get_period_findings, persist_report
from utils.logger import get_logger

logger = get_logger(__name__)


def generate_monthly_reports(conn, default_days=30):
    """Returns a list of (service_line, email_body, attachment_path) for lines with findings."""
    results = []
    for service_line in SERVICE_LINES:
        report_type = f"MONTHLY_{service_line}"
        days = get_days_since_last_report(conn, report_type, default_days)
        findings = get_period_findings(conn, days, service_line=service_line)

        if not findings:
            logger.info(f"{service_line}: no findings since the last monthly report — skipping.")
            continue

        email_body = build_email_body(findings, period_label="month")
        attachment_path = persist_report(conn, report_type, findings, f"monthly_{service_line.lower()}", days)

        logger.info(f"{service_line}: monthly report generated, {len(findings)} findings, attachment at {attachment_path}")
        results.append((service_line, email_body, attachment_path))
    return results
