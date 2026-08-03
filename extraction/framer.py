from datetime import datetime, timezone
import time
from extraction.classifier import OPENROUTER_MODEL, get_openrouter_headers, post_to_openrouter
from utils.db_filters import in_clause
from utils.logger import get_logger

logger = get_logger(__name__)

def build_framing_prompt(finding):
    return f"""You are advising Deloitte Africa's Nigeria {finding['service_line']} practice on how to act on a regulatory finding. Write an internal briefing note for analysts and managers only — never phrase this as if addressed to a client or partner directly.

Do not add a memo header, letterhead, or metadata fields — no "TO:", "FROM:", "DATE:", "SUBJECT:", or classification markings, and do not invent a date. Start directly with the first section below.

Structure your response with these labeled sections:
Opportunity: What does this finding mean for the {finding['service_line']} practice — a new engagement angle, a compliance risk to flag to existing clients, or an internal awareness item?
Recommended Action: Concrete next step(s) the team should take.
Why Now: The urgency rationale — why this matters at this point in time.

Scale the depth of your answer to how significant the finding actually is. A minor administrative notice deserves a few brief sentences total. A major regulatory shift with broad client impact deserves a fuller breakdown with specific examples under each section.

Finding details:
Urgency: {finding['urgency']}
Summary: {finding['summary']}
Evidence: {finding['evidence_excerpt']}
Source: {finding['source_url']}
"""

def frame_finding(finding, headers):
    prompt = build_framing_prompt(finding)
    response = post_to_openrouter(
        {
            "model": OPENROUTER_MODEL,
            "messages": [{"role": "user", "content": prompt}],
        },
        headers,
    )
    return response.json()["choices"][0]["message"]["content"]

def run_framing_pipeline(conn, source_names=None):
    headers = get_openrouter_headers()
    clause, params = in_clause("sources.name", source_names)
    findings = conn.execute(
        f"""
        SELECT findings.id, findings.service_line, findings.urgency, findings.summary,
               findings.evidence_excerpt, findings.source_url
        FROM findings
        JOIN source_items ON source_items.id = findings.source_item_id
        JOIN sources ON sources.id = source_items.source_id
        LEFT JOIN opportunity_framings ON opportunity_framings.finding_id = findings.id
        WHERE opportunity_framings.id IS NULL{clause}
        """,
        params,
    ).fetchall()

    for finding in findings:
        try:
            framing_text = frame_finding(finding, headers)
        except Exception as e:
            logger.error(f"Framing failed for finding {finding['id']}: {e}")
            continue

        conn.execute(
            """
            INSERT INTO opportunity_framings (finding_id, service_line, framing_text, created_at)
            VALUES (?, ?, ?, ?)
            """,
            (finding["id"], finding["service_line"], framing_text, datetime.now(timezone.utc).isoformat()),
        )
        conn.commit()
        logger.info(f"Finding {finding['id']} ({finding['service_line']}/{finding['urgency']}): framed")
        time.sleep(2)