from datetime import datetime, timedelta, timezone
import os

from utils.db_filters import in_clause
from utils.logger import get_logger

logger = get_logger(__name__)

TOP_N_FOR_EMAIL = 10
OUTPUT_DIR = "reports/output"

URGENT_LEVELS = ("CRITICAL", "HIGH")


def get_days_since_last_report(conn, report_type, default_days):
    row = conn.execute(
        "SELECT MAX(generated_at) AS last FROM reports WHERE report_type = ?",
        (report_type,),
    ).fetchone()
    if not row["last"]:
        return default_days
    last_dt = datetime.fromisoformat(row["last"])
    elapsed_days = (datetime.now(timezone.utc) - last_dt).total_seconds() / 86400
    return max(elapsed_days, 0)


def get_period_findings(conn, days=7, urgency_levels=None):
    cutoff = (datetime.now(timezone.utc) - timedelta(days=days)).isoformat()
    clause, extra_params = in_clause("findings.urgency", urgency_levels)
    return conn.execute(
        f"""
        SELECT findings.id, findings.service_line, findings.urgency, findings.headline, findings.summary,
               findings.confidence_score, findings.source_url, opportunity_framings.framing_text,
               CASE findings.urgency
                   WHEN 'CRITICAL' THEN 1
                   WHEN 'HIGH' THEN 2
                   WHEN 'MEDIUM' THEN 3
                   WHEN 'LOW' THEN 4
               END AS urgency_rank
        FROM findings
        JOIN opportunity_framings ON opportunity_framings.finding_id = findings.id
        WHERE findings.created_at >= ?{clause}
        ORDER BY urgency_rank ASC, findings.confidence_score DESC
        """,
        (cutoff, *extra_params),
    ).fetchall()


def build_email_body(findings, period_label="week"):
    top_findings = findings[:TOP_N_FOR_EMAIL]
    lines = [
        "Hi team,",
        "",
        f"{len(findings)} regulatory items were flagged this {period_label}. Here are the top {len(top_findings)} opportunities:",
        "",
    ]
    for f in top_findings:
        headline = f["headline"] or f["summary"]
        lines.append(f"[{f['service_line']} / {f['urgency']}] {headline}")
        lines.append(f"Source: {f['source_url']}")
        lines.append("")
    lines.append("Full breakdown of all findings and recommended actions is in the attached document.")
    lines.append("")
    lines.append("— RegWatch")
    return "\n".join(lines)


def build_attachment_text(findings):
    blocks = []
    for f in findings:
        blocks.append(
            f"{'=' * 60}\n"
            f"{f['service_line']} — {f['urgency']} (confidence: {f['confidence_score']:.2f})\n"
            f"{'-' * 60}\n"
            f"Summary: {f['summary']}\n\n"
            f"{f['framing_text']}\n\n"
            f"Source: {f['source_url']}\n"
        )
    return "\n".join(blocks)


def persist_report(conn, report_type, findings, filename_prefix, days):
    attachment_text = build_attachment_text(findings)

    os.makedirs(OUTPUT_DIR, exist_ok=True)
    today = datetime.now(timezone.utc).date().isoformat()
    attachment_path = f"{OUTPUT_DIR}/{filename_prefix}_{today}.txt"
    with open(attachment_path, "w") as f:
        f.write(attachment_text)

    period_start = (datetime.now(timezone.utc) - timedelta(days=days)).isoformat()
    period_end = datetime.now(timezone.utc).isoformat()

    cursor = conn.execute(
        "INSERT INTO reports (report_type, period_start, period_end, generated_at) VALUES (?, ?, ?, ?)",
        (report_type, period_start, period_end, period_end),
    )
    report_id = cursor.lastrowid

    for f in findings:
        conn.execute(
            "INSERT INTO report_findings (report_id, finding_id) VALUES (?, ?)",
            (report_id, f["id"]),
        )
    conn.commit()
    return attachment_path


def generate_weekly_report(conn, default_days=7):
    days = get_days_since_last_report(conn, "WEEKLY", default_days)
    findings = get_period_findings(conn, days, urgency_levels=URGENT_LEVELS)

    if not findings:
        logger.info("No urgent findings since the last weekly report — skipping.")
        return None, None

    email_body = build_email_body(findings, period_label="week")
    attachment_path = persist_report(conn, "WEEKLY", findings, "weekly", days)

    logger.info(f"Weekly report generated: {len(findings)} findings, attachment at {attachment_path}")
    return email_body, attachment_path
