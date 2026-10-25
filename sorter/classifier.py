"""AI Classifier & Action Item Extractor using Groq LLaMA models."""

from dataclasses import dataclass
import json
import re
from typing import Any
import requests

from sorter.email_fetcher import ParsedEmail

GROQ_API_URL = "https://api.groq.com/openai/v1/chat/completions"

SYSTEM_PROMPT = """You are an intelligent email analyzer for an engineering student.
Your task is to analyze incoming emails and extract structured action items and alerts.

You must categorize and assess whether an email is ALERT-WORTHY based on its content, NOT merely on the sender.
- ALERT-WORTHY items:
  * Online class notices, emergency class cancellations or links (Google Meet/Zoom)
  * Hackathons, coding competitions, or technical challenges with real deadlines/registrations
  * Exam schedules, assignment submission deadlines, or academic advisories
  * Official internship/job interview invites or urgent application deadlines
- NOT ALERT-WORTHY (Marketing / Promotional / General Spam):
  * Marketing newsletters, course discount offers, sales, bootcamps (e.g. from Unstop, Coursera, Udemy, etc.)
  * Society general newsletters, promotional event hype without immediate action required
  * Spam, social media digests, automated notifications of no consequence

Categories to choose from:
- "Online Class"
- "Assignment / Exam"
- "Hackathon / Competition"
- "Internship / Job"
- "Administrative Notice"
- "Promotional"
- "Newsletter"
- "Other"

Urgency levels:
- "high": Immediate action within 24 hours, starting soon, or emergency class announcement.
- "medium": Action required within 1-7 days (e.g. hackathon registration deadline, upcoming exam).
- "low": No immediate urgency or promotional/informational.

You MUST respond strictly with a valid JSON object matching this schema:
{
  "is_alert_worthy": true | false,
  "category": "<Category>",
  "urgency": "high" | "medium" | "low",
  "summary": "<1-2 sentence concise plain text summary>",
  "deadline_or_time": "<Deadline or start time string or null>",
  "action_link": "<Primary action/meeting/registration URL or null>",
  "action_required": "<Specific action student needs to take or null>"
}
Do not include any commentary outside the JSON object.
"""


@dataclass
class ClassificationResult:
    is_alert_worthy: bool
    category: str
    urgency: str
    summary: str
    deadline_or_time: str | None
    action_link: str | None
    action_required: str | None


def _remove_trailing_commas(json_str: str) -> str:
    """Remove trailing commas before closing braces or brackets in a JSON string."""
    return re.sub(r",(\s*[}\]])", r"\1", json_str)


def parse_llm_json_response(raw_text: str) -> ClassificationResult:
    """Robustly parse LLM response into ClassificationResult.
    
    Handles markdown fences (```json ... ```), extra commentary,
    and trailing commas.
    """
    clean_text = raw_text.strip()
    
    # Strip markdown code fences if present
    match = re.search(r"```(?:json)?\s*([\s\S]*?)\s*```", clean_text, re.IGNORECASE)
    if match:
        clean_text = match.group(1).strip()
    else:
        # If no code block, try to find the outermost JSON object {...}
        brace_match = re.search(r"\{[\s\S]*\}", clean_text)
        if brace_match:
            clean_text = brace_match.group(0).strip()

    # Clean trailing commas
    sanitized = _remove_trailing_commas(clean_text)

    try:
        data: dict[str, Any] = json.loads(sanitized)
    except json.JSONDecodeError as exc:
        raise ValueError(f"Could not extract valid JSON from LLM response: {raw_text}") from exc

    return ClassificationResult(
        is_alert_worthy=bool(data.get("is_alert_worthy", False)),
        category=str(data.get("category", "Other")),
        urgency=str(data.get("urgency", "low")),
        summary=str(data.get("summary", "")),
        deadline_or_time=data.get("deadline_or_time"),
        action_link=data.get("action_link"),
        action_required=data.get("action_required"),
    )


def classify_email(
    email_data: ParsedEmail,
    api_key: str,
    model: str = "llama-3.3-70b-versatile",
) -> ClassificationResult:
    """Classify an email using Groq's chat completion API and LLaMA models."""
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }

    truncated_body = email_data.body[:4000] if email_data.body else ""
    user_prompt = (
        f"Sender: {email_data.sender}\n"
        f"Date: {email_data.date}\n"
        f"Subject: {email_data.subject}\n\n"
        f"Email Body:\n{truncated_body}\n"
    )
    payload = {
        "model": model,
        "temperature": 0.1,
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": user_prompt},
        ],
    }

    response = requests.post(
        GROQ_API_URL,
        headers=headers,
        json=payload,
        timeout=30,
    )
    response.raise_for_status()

    res_json = response.json()
    choices = res_json.get("choices", [])
    if not choices:
        raise ValueError("No choices returned in Groq response")

    content = choices[0]["message"]["content"]
    return parse_llm_json_response(content)
