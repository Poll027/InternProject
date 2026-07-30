import base64
from datetime import datetime, timezone
import os

import requests

from utils.logger import get_logger

logger = get_logger(__name__)

SENDGRID_API_URL = "https://api.sendgrid.com/v3/mail/send"


def send_weekly_email(body, attachment_path):
    recipients = [r.strip() for r in os.getenv("EMAIL_TO", "").split(",") if r.strip()]
    if not recipients:
        logger.error("EMAIL_TO not set — skipping email delivery.")
        return False

    with open(attachment_path, "rb") as f:
        attachment_content = base64.b64encode(f.read()).decode()

    payload = {
        "personalizations": [{"to": [{"email": r} for r in recipients]}],
        "from": {"email": os.getenv("EMAIL_FROM")},
        "subject": f"RegWatch Weekly Alert — {datetime.now(timezone.utc).date().isoformat()}",
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
    logger.info(f"Weekly report emailed to {', '.join(recipients)}")
    return True
