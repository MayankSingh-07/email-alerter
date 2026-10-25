"""WhatsApp Option B Alerter module using CallMeBot gateway."""

import logging
import re
import time
from urllib.parse import quote_plus
import requests
from sorter.classifier import ClassificationResult
from sorter.email_fetcher import ParsedEmail

logger = logging.getLogger(__name__)

CALLMEBOT_API_URL = "https://api.callmebot.com/whatsapp.php"

# Category-to-Emoji mappings
CATEGORY_EMOJIS = {
    "Online Class": "💻",
    "Assignment / Exam": "📌",
    "Assignment": "📌",
    "Exam": "📌",
    "Hackathon / Competition": "🏆",
    "Hackathon": "🏆",
    "Internship / Job": "💼",
    "Internship": "💼",
    "Administrative Notice": "📢",
    "Administrative": "📢",
}


def _get_header_badge(category: str, urgency: str) -> str:
    """Return appropriate emoji badge based on urgency and category."""
    if urgency.lower() == "high":
        return "🔴"
    return CATEGORY_EMOJIS.get(category, "📌")


def format_whatsapp_message(
    account: str,
    email_data: ParsedEmail,
    decision: ClassificationResult,
) -> str:
    """Format Option B Detailed Briefing message for WhatsApp delivery.

    Layout:
    [Badge] [Account] [Category]
    From: <sender>
    Subject: <subject>
    Summary: <summary>
    Deadline: <deadline_or_time> (if present)
    Link: <action_link> (if present)
    ⚠️ Action: <action_required> (if present)
    """
    badge = _get_header_badge(decision.category, decision.urgency)
    header = f"{badge} [{account}] {decision.category}"
    lines = [
        header,
        f"From: {email_data.sender}",
        f"Subject: {email_data.subject}",
        f"Summary: {decision.summary}",
    ]

    if decision.deadline_or_time:
        lines.append(f"Deadline: {decision.deadline_or_time}")

    if decision.action_link:
        lines.append(f"Link: {decision.action_link}")

    if decision.action_required:
        lines.append(f"⚠️ Action: {decision.action_required}")

    return "\n".join(lines)


def send_whatsapp_alert(
    phone: str,
    api_key: str,
    message: str,
    max_retries: int = 3,
    initial_backoff: float = 2.0,
    timeout: int = 15,
) -> bool:
    """Send formatted WhatsApp message via CallMeBot gateway.

    Parameters:
        phone: WhatsApp target phone number with country code (e.g. +919876543210)
        api_key: CallMeBot API key
        message: Formatted text alert to deliver
        max_retries: Number of retry attempts for 429 rate limit or network errors
        initial_backoff: Backoff seconds before retrying
        timeout: HTTP request timeout in seconds

    Returns:
        True if dispatched successfully (HTTP 200), False otherwise.
    """
    # Clean phone number (remove spaces, hyphens, and any non-digit/plus characters)
    cleaned_phone = re.sub(r"[^\d+]", "", phone.strip())
    # We URL-encode query parameters via params dictionary in requests
    # which uses urllib.parse.quote or quote_plus under the hood.
    # To be fully compliant with CallMeBot requirements (which expects text parameter
    # formatted with + or %20 for spaces and encoded special characters):
    encoded_text = quote_plus(message)
    encoded_phone = quote_plus(cleaned_phone)
    encoded_key = quote_plus(api_key.strip())
    
    # Direct URL with quote_plus to guarantee exact CallMeBot format
    request_url = (
        f"{CALLMEBOT_API_URL}?phone={encoded_phone}&text={encoded_text}&apikey={encoded_key}"
    )

    backoff = initial_backoff
    for attempt in range(1, max_retries + 1):
        try:
            logger.info("Dispatching WhatsApp alert via CallMeBot (attempt %d/%d)...", attempt, max_retries)
            response = requests.get(request_url, timeout=timeout)

            if response.status_code == 200:
                if "error" in response.text.lower():
                    logger.error(
                        "CallMeBot returned error page with HTTP 200: %s (attempt %d/%d)",
                        response.text.strip(),
                        attempt,
                        max_retries,
                    )
                else:
                    logger.info("WhatsApp alert successfully delivered.")
                    return True
            elif response.status_code == 429:
                logger.warning(
                    "CallMeBot rate limit reached (HTTP 429). Backing off for %.1fs (attempt %d/%d)...",
                    backoff,
                    attempt,
                    max_retries,
                )
            else:
                logger.error(
                    "CallMeBot HTTP error %d: %s (attempt %d/%d)",
                    response.status_code,
                    response.text,
                    attempt,
                    max_retries,
                )
        except requests.RequestException as e:
            logger.error(
                "CallMeBot request exception: %s (attempt %d/%d)",
                e,
                attempt,
                max_retries,
            )

        if attempt < max_retries:
            time.sleep(backoff)
            backoff *= 2

    logger.error("Failed to deliver WhatsApp alert after %d attempts.", max_retries)
    return False
