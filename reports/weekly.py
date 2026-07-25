from datetime import datetime, timedelta, timezone
import os

from utils.logger import get_logger

logger = get_logger(__name__)

TOP_N_FOR_EMAIL = 10
OUTPUT_DIR = "reports/output"


def get_period_findings(conn, days=7):
    cutoff = (datetime.now(timezone.utc) - timedelta(days=days)).isoformat()
    return conn.execute(
        """
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
        WHERE findings.created_at >= ?
        ORDER BY urgency_rank ASC, findings.confidence_score DESC
        """,
        (cutoff,),
    ).fetchall()


def build_email_body(findings):
    top_findings = findings[:TOP_N_FOR_EMAIL]
    lines = [
        "Hi team,",
        "",
        f"{len(findings)} regulatory items were flagged this week. Here are the top {len(top_findings)} opportunities:",
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


def generate_weekly_report(conn, days=7):
    findings = get_period_findings(conn, days)

    if not findings:
        logger.info("No findings in the period — skipping weekly report.")
        return None, None

    email_body = build_email_body(findings)
    attachment_text = build_attachment_text(findings)

    os.makedirs(OUTPUT_DIR, exist_ok=True)
    today = datetime.now(timezone.utc).date().isoformat()
    attachment_path = f"{OUTPUT_DIR}/weekly_{today}.txt"
    with open(attachment_path, "w") as f:
        f.write(attachment_text)

    period_start = (datetime.now(timezone.utc) - timedelta(days=days)).isoformat()
    period_end = datetime.now(timezone.utc).isoformat()

    cursor = conn.execute(
        "INSERT INTO reports (report_type, period_start, period_end, generated_at) VALUES (?, ?, ?, ?)",
        ("WEEKLY", period_start, period_end, period_end),
    )
    report_id = cursor.lastrowid

    for f in findings:
        conn.execute(
            "INSERT INTO report_findings (report_id, finding_id) VALUES (?, ?)",
            (report_id, f["id"]),
        )
    conn.commit()

    logger.info(f"Weekly report generated: {len(findings)} findings, attachment at {attachment_path}")
    return email_body, attachment_path
