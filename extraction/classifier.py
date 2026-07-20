from datetime import datetime, timezone
import json
import os
import time

from google import genai
from google.genai import types
from utils.logger import get_logger

logger = get_logger(__name__)

SERVICE_LINES = ("AI_DATA", "TAX", "AUDIT", "CYBERSECURITY")
URGENCY_LEVELS = ("CRITICAL", "HIGH", "MEDIUM", "LOW")

CLASSIFICATION_SCHEMA = {
    "type": "object",
    "properties": {
        "relevant": {"type": "boolean"},
        "findings": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "service_line": {"type": "string", "enum": list(SERVICE_LINES)},
                    "urgency": {"type": "string", "enum": list(URGENCY_LEVELS)},
                    "summary": {"type": "string"},
                    "evidence_excerpt": {"type": "string"},
                    "confidence": {"type": "number"},
                },
                "required": ["service_line", "urgency", "summary", "evidence_excerpt", "confidence"],
            },
        },
    },
    "required": ["relevant", "findings"],
}

def get_gemini_client():
    return genai.Client(api_key = os.getenv("GEMINI_API_KEY"))

def build_prompt(item):
    return f"""You are a regulatory analyst for Deloitte Africa's Nigeria practice.
Read the circular below and decide which of these service lines it is relevant to: {", ".join(SERVICE_LINES)}.
For each relevant service line, assign an urgency ({", ".join(URGENCY_LEVELS)}), a one-paragraph summary, a short verbatim evidence excerpt quoted from the text, and a confidence score between 0 and 1 for your own judgment.
If the circular is not relevant to any service line, return relevant: false and an empty findings list.

Title: {item['title']}
Source: {item['source_name']}

Document text:
{item['raw_text']}
"""

def classify_item(item, client):
    prompt = build_prompt(item)
    response = client.models.generate_content(
        model = "gemini-2.5-flash",
        contents = prompt,
        config = types.GenerateContentConfig(
            response_mime_type="application/json",
            response_schema=CLASSIFICATION_SCHEMA,

        )
    )
    return json.loads(response.text)

def run_classification_pipeline(conn):
    client = get_gemini_client()
    items = conn.execute(
        """
        SELECT source_items.id, source_items.title, source_items.raw_text,
               source_items.url, sources.name AS source_name, sources.reliability_score
        FROM source_items
        JOIN sources ON sources.id = source_items.source_id
        WHERE source_items.processing_status = 'EXTRACTED'
        """
    ).fetchall()

    for item in items:
        try:
            result = classify_item(item, client)
        except Exception as e:
            logger.error(f"Classification failed for item {item['id']}: {e}")
            continue

        for finding in result.get("findings", []):
            confidence_score = item["reliability_score"] * finding["confidence"]
            conn.execute(
                """
                INSERT INTO findings
                    (source_item_id, service_line, urgency, summary, confidence_score, source_url, evidence_excerpt, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    item["id"],
                    finding["service_line"],
                    finding["urgency"],
                    finding["summary"],
                    confidence_score,
                    item["url"],
                    finding["evidence_excerpt"],
                    datetime.now(timezone.utc).isoformat(),
                ),
            )

        conn.execute(
            "UPDATE source_items SET processing_status = 'CLASSIFIED' WHERE id = ?",
            (item["id"],),
        )
        conn.commit()
        logger.info(f"{item['title'][:50]}: {len(result.get('findings', []))} findings")
        time.sleep(13)