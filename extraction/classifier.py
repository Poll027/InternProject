from datetime import datetime, timezone
import json
import os
import time

import requests

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
                    "headline": {"type": "string"},
                    "summary": {"type": "string"},
                    "evidence_excerpt": {"type": "string"},
                    "confidence": {"type": "number"},
                },
                "required": ["service_line", "urgency", "headline", "summary", "evidence_excerpt", "confidence"],
                "additionalProperties": False,
            },
        },
    },
    "required": ["relevant", "findings"],
    "additionalProperties": False,
}

OPENROUTER_MODEL = "deepseek/deepseek-v3.2"


def get_openrouter_headers():
    return {
        "Authorization": f"Bearer {os.getenv('OPENROUTER_API_KEY')}",
        "Content-Type": "application/json",
    }


def post_to_openrouter(payload, headers, max_retries=3, retry_delay=5):
    for attempt in range(1, max_retries + 1):
        try:
            response = requests.post(
                "https://openrouter.ai/api/v1/chat/completions",
                headers=headers,
                json=payload,
            )
            response.raise_for_status()
            return response
        except requests.exceptions.ConnectionError as e:
            if attempt == max_retries:
                raise
            logger.warning(f"OpenRouter connection failed (attempt {attempt}/{max_retries}), retrying in {retry_delay}s: {e}")
            time.sleep(retry_delay)

def build_prompt(item):
    return f"""You are a regulatory analyst for Deloitte Africa's Nigeria practice.
Read the circular below and decide which of these service lines it is relevant to: {", ".join(SERVICE_LINES)}.
For each relevant service line, assign an urgency ({", ".join(URGENCY_LEVELS)}), a punchy one-sentence headline (max ~15 words, suitable for a scannable email digest), a one-paragraph summary, a short verbatim evidence excerpt quoted from the text, and a confidence score between 0 and 1 for your own judgment.
If the circular is not relevant to any service line, return relevant: false and an empty findings list.

Title: {item['title']}
Source: {item['source_name']}

Document text:
{item['raw_text']}
"""

def classify_item(item, headers):
    prompt = build_prompt(item)
    response = post_to_openrouter(
        {
            "model": OPENROUTER_MODEL,
            "messages": [{"role": "user", "content": prompt}],
            "response_format": {
                "type": "json_schema",
                "json_schema": {
                    "name": "classification",
                    "strict": True,
                    "schema": CLASSIFICATION_SCHEMA,
                },
            },
        },
        headers,
    )
    content = response.json()["choices"][0]["message"]["content"]
    return json.loads(content)

def run_classification_pipeline(conn):
    headers = get_openrouter_headers()
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
            result = classify_item(item, headers)
        except Exception as e:
            logger.error(f"Classification failed for item {item['id']}: {e}")
            continue

        for finding in result.get("findings", []):
            confidence_score = item["reliability_score"] * finding["confidence"]
            conn.execute(
                """
                INSERT INTO findings
                    (source_item_id, service_line, urgency, headline, summary, confidence_score, source_url, evidence_excerpt, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    item["id"],
                    finding["service_line"],
                    finding["urgency"],
                    finding["headline"],
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
        time.sleep(2)