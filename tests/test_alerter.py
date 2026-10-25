"""Tests for WhatsApp alerter module."""

from unittest.mock import MagicMock
import pytest
import requests

from sorter.email_fetcher import ParsedEmail
from sorter.classifier import ClassificationResult
from sorter.alerter import (
    format_whatsapp_message,
    send_whatsapp_alert,
    _get_header_badge,
)


def test_format_option_b_message():
    email_data = ParsedEmail(
        message_id="<id1>",
        sender="prof@college.edu",
        subject="Lab 3 Teams",
        date="date",
        body="Form teams of 3.",
    )
    decision = ClassificationResult(
        is_alert_worthy=True,
        category="Assignment",
        urgency="high",
        summary="Form groups of 3 for the distributed systems project.",
        deadline_or_time="Oct 30, 11:59 PM",
        action_link="https://forms.gle/lab3teams",
        action_required="Find 2 team members and submit Google Form",
    )

    msg = format_whatsapp_message("College", email_data, decision)
    assert "[College] Assignment" in msg
    assert "From: prof@college.edu" in msg
    assert "Subject: Lab 3 Teams" in msg
    assert "Summary: Form groups of 3 for the distributed systems project." in msg
    assert "Deadline: Oct 30, 11:59 PM" in msg
    assert "Link: https://forms.gle/lab3teams" in msg
    assert "⚠️ Action: Find 2 team members and submit Google Form" in msg


def test_format_option_b_message_urgent_badge():
    email_data = ParsedEmail(
        message_id="<id2>",
        sender="hod@college.edu",
        subject="Urgent: Class Relocation",
        date="date",
        body="Join online meet now.",
    )
    decision = ClassificationResult(
        is_alert_worthy=True,
        category="Online Class",
        urgency="high",
        summary="Online class starting now due to campus maintenance.",
        deadline_or_time="Immediate",
        action_link="https://meet.google.com/abc-defg-hij",
        action_required="Join the Meet link immediately",
    )

    msg = format_whatsapp_message("College", email_data, decision)
    assert "🔴 [College] Online Class" in msg
    assert "Link: https://meet.google.com/abc-defg-hij" in msg


def test_format_option_b_message_optional_fields_omitted():
    email_data = ParsedEmail(
        message_id="<id3>",
        sender="club@college.edu",
        subject="Tech Talk Announcement",
        date="date",
        body="Talk tomorrow.",
    )
    decision = ClassificationResult(
        is_alert_worthy=True,
        category="Hackathon / Competition",
        urgency="medium",
        summary="Annual hackathon announced.",
        deadline_or_time=None,
        action_link=None,
        action_required=None,
    )

    msg = format_whatsapp_message("Personal", email_data, decision)
    assert "🏆 [Personal] Hackathon / Competition" in msg
    assert "From: club@college.edu" in msg
    assert "Subject: Tech Talk Announcement" in msg
    assert "Summary: Annual hackathon announced." in msg
    assert "Deadline:" not in msg
    assert "Link:" not in msg
    assert "Action:" not in msg


def test_header_badge_categories():
    assert _get_header_badge("Online Class", "medium") == "💻"
    assert _get_header_badge("Online Class", "high") == "🔴"
    assert _get_header_badge("Assignment / Exam", "low") == "📌"
    assert _get_header_badge("Assignment", "low") == "📌"
    assert _get_header_badge("Hackathon / Competition", "medium") == "🏆"
    assert _get_header_badge("Internship / Job", "medium") == "💼"
    assert _get_header_badge("Administrative Notice", "medium") == "📢"
    assert _get_header_badge("Unknown Category", "medium") == "📌"


def test_send_whatsapp_alert_success(monkeypatch):
    mock_get = MagicMock()
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.text = "Message queued"
    mock_get.return_value = mock_response
    monkeypatch.setattr("requests.get", mock_get)

    ok = send_whatsapp_alert("+919876543210", "apikey123", "Test Alert with emojis 🔴 and & ampersands")
    assert ok is True
    assert mock_get.called
    called_url = mock_get.call_args[0][0]
    assert "api.callmebot.com/whatsapp.php" in called_url
    assert "params" in mock_get.call_args[1] or "%" in called_url


def test_send_whatsapp_alert_url_encoding(monkeypatch):
    mock_get = MagicMock()
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_get.return_value = mock_response
    monkeypatch.setattr("requests.get", mock_get)

    message = "🔴 [College] URGENT: Online Class\nFrom: prof@college.edu\nLink: https://meet.google.com/abc?authuser=1&hl=en"
    send_whatsapp_alert("+91 98765 43210", "key&123", message)

    args, kwargs = mock_get.call_args
    url = args[0]
    # Check that either params dict was passed or the query string in URL was quote_plus encoded
    if "params" in kwargs and kwargs["params"]:
        params = kwargs["params"]
        assert params["phone"] == "+91 98765 43210" or params["phone"] == "+919876543210"
        assert params["apikey"] == "key&123"
        assert params["text"] == message
    else:
        assert "%26" in url or "key%26123" in url
        assert "http" in url


def test_send_whatsapp_alert_rate_limiting_429_retry(monkeypatch):
    mock_get = MagicMock()
    resp_429 = MagicMock()
    resp_429.status_code = 429
    resp_429.text = "Too Many Requests"

    resp_200 = MagicMock()
    resp_200.status_code = 200
    resp_200.text = "OK"

    mock_get.side_effect = [resp_429, resp_200]
    monkeypatch.setattr("requests.get", mock_get)
    monkeypatch.setattr("time.sleep", lambda s: None)

    ok = send_whatsapp_alert("+919876543210", "key123", "Alert text", max_retries=2)
    assert ok is True
    assert mock_get.call_count == 2


def test_send_whatsapp_alert_failure_after_retries(monkeypatch):
    mock_get = MagicMock()
    resp_500 = MagicMock()
    resp_500.status_code = 500
    resp_500.text = "Internal Server Error"
    mock_get.return_value = resp_500
    monkeypatch.setattr("requests.get", mock_get)
    monkeypatch.setattr("time.sleep", lambda s: None)

    ok = send_whatsapp_alert("+919876543210", "key123", "Alert text", max_retries=2)
    assert ok is False
    assert mock_get.call_count == 2


def test_send_whatsapp_alert_network_exception(monkeypatch):
    mock_get = MagicMock()
    mock_get.side_effect = requests.RequestException("Connection error")
    monkeypatch.setattr("requests.get", mock_get)
    monkeypatch.setattr("time.sleep", lambda s: None)

    ok = send_whatsapp_alert("+919876543210", "key123", "Alert text", max_retries=2)
    assert ok is False
