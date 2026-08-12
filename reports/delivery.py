import base64
from datetime import datetime, timezone
import os

import requests

from utils.logger import get_logger

logger = get_logger(__name__)

SENDGRID_API_URL = "https://api.sendgrid.com/v3/mail/send"


def get_recipients_for_service_line(service_line):
    return [r.strip() for r in os.getenv(f"EMAIL_TO_{service_line}", "").split(",") if r.strip()]


def send_report_email(body, attachment_path, subject, recipients):
    if not recipients:
        logger.error("No recipients provided — skipping email delivery.")
        return False

    with open(attachment_path, "rb") as f:
        attachment_content = base64.b64encode(f.read()).decode()

    payload = {
        "personalizations": [{"to": [{"email": r} for r in recipients]}],
        "from": {"email": os.getenv("EMAIL_FROM")},
        "subject": subject,
        "content": [{"type": "text/plain", "value": body}],
        "attachments": [
            {
                "content": attachment_content,
                "filename": os.path.basename(attachment_path),
                "type": "text/plain",
                "disposition": "attachment",
            }
        ],
    }
    headers = {
        "Authorization": f"Bearer {os.getenv('SENDGRID_API_KEY')}",
        "Content-Type": "application/json",
    }

    response = requests.post(SENDGRID_API_URL, json=payload, headers=headers)
    response.raise_for_status()
    logger.info(f"Report emailed to {', '.join(recipients)}: {subject}")
    return True
