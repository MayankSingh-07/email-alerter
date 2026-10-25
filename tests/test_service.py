import logging
import ssl
from unittest.mock import MagicMock, call
import pytest

from sorter.config import Config
from sorter.storage import Storage
from sorter.email_fetcher import ParsedEmail
from sorter.classifier import ClassificationResult
from sorter.service import EmailMonitorService


@pytest.fixture
def test_config(tmp_path):
    return Config(
        college_user="c@gmail.com",
        college_pass="cp",
        personal_user="p@gmail.com",
        personal_pass="pp",
        groq_api_key="gk",
        callmebot_phone="123456",
        callmebot_api_key="ck",
        poll_interval_seconds=300,
        db_path=str(tmp_path / "alerts.db"),
    )


def test_service_run_once_end_to_end(test_config, monkeypatch):
    storage = Storage(test_config.db_path)

    # Mock email fetching
    mock_email = ParsedEmail(
        "<1@c.edu>", "prof@college.edu", "Class Link", "date", "Join class."
    )
    monkeypatch.setattr(
        "sorter.service.fetch_unseen_emails",
        lambda u, p: [mock_email] if u == "c@gmail.com" else [],
    )

    # Mock classifier
    mock_decision = ClassificationResult(
        True,
        "Online Class",
        "high",
        "Class starting.",
        "10 AM",
        "https://meet.google.com/abc",
        "Join now",
    )
    monkeypatch.setattr("sorter.service.classify_email", lambda e, k: mock_decision)

    # Mock alerter
    mock_alert = MagicMock(return_value=True)
    monkeypatch.setattr("sorter.service.send_whatsapp_alert", mock_alert)

    service = EmailMonitorService(test_config, storage)
    alerts_sent = service.run_once()

    assert alerts_sent == 1
    assert storage.is_processed("College", "<1@c.edu>")
    assert mock_alert.called


def test_service_run_once_skips_already_processed(test_config, monkeypatch):
    storage = Storage(test_config.db_path)
    storage.mark_processed("College", "<1@c.edu>", "Old Subject", alerted=True)

    mock_email = ParsedEmail(
        "<1@c.edu>", "prof@college.edu", "Class Link", "date", "Join class."
    )
    monkeypatch.setattr(
        "sorter.service.fetch_unseen_emails",
        lambda u, p: [mock_email] if u == "c@gmail.com" else [],
    )

    mock_classify = MagicMock()
    monkeypatch.setattr("sorter.service.classify_email", mock_classify)

    mock_alert = MagicMock()
    monkeypatch.setattr("sorter.service.send_whatsapp_alert", mock_alert)

    service = EmailMonitorService(test_config, storage)
    alerts_sent = service.run_once()

    assert alerts_sent == 0
    assert mock_classify.call_count == 0
    assert mock_alert.call_count == 0


def test_service_run_once_not_alert_worthy(test_config, monkeypatch):
    storage = Storage(test_config.db_path)

    mock_email = ParsedEmail(
        "<2@c.edu>", "news@promo.com", "Discount Course", "date", "Buy now."
    )
    monkeypatch.setattr(
        "sorter.service.fetch_unseen_emails",
        lambda u, p: [mock_email] if u == "c@gmail.com" else [],
    )

    mock_decision = ClassificationResult(
        False,
        "Promotional",
        "low",
        "Promo email",
        None,
        None,
        None,
    )
    monkeypatch.setattr("sorter.service.classify_email", lambda e, k: mock_decision)

    mock_alert = MagicMock()
    monkeypatch.setattr("sorter.service.send_whatsapp_alert", mock_alert)

    service = EmailMonitorService(test_config, storage)
    alerts_sent = service.run_once()

    assert alerts_sent == 0
    assert storage.is_processed("College", "<2@c.edu>")
    assert mock_alert.call_count == 0


def test_service_baseline_mode_marks_processed_without_alert(test_config, monkeypatch):
    storage = Storage(test_config.db_path)

    mock_email = ParsedEmail(
        "<3@c.edu>", "prof@college.edu", "Exam Alert", "date", "Exam scheduled."
    )
    monkeypatch.setattr(
        "sorter.service.fetch_unseen_emails",
        lambda u, p: [mock_email] if u == "c@gmail.com" else [],
    )

    mock_classify = MagicMock()
    monkeypatch.setattr("sorter.service.classify_email", mock_classify)

    mock_alert = MagicMock()
    monkeypatch.setattr("sorter.service.send_whatsapp_alert", mock_alert)

    service = EmailMonitorService(test_config, storage)
    alerts_sent = service.run_once(alert_new=False)

    assert alerts_sent == 0
    assert storage.is_processed("College", "<3@c.edu>")
    # Neither classifier nor WhatsApp alerter should be invoked in baseline mode
    assert mock_classify.call_count == 0
    assert mock_alert.call_count == 0


def test_service_network_or_ssl_error_resilience(test_config, monkeypatch, caplog):
    storage = Storage(test_config.db_path)

    def mock_fetch(u, p):
        if u == "c@gmail.com":
            raise ssl.SSLError("SSL handshake failed or connection timed out")
        return [
            ParsedEmail(
                "<personal@p.edu>", "friend@p.edu", "Meetup", "date", "Hello"
            )
        ]

    monkeypatch.setattr("sorter.service.fetch_unseen_emails", mock_fetch)

    mock_decision = ClassificationResult(
        False,
        "Other",
        "low",
        "Friendly email",
        None,
        None,
        None,
    )
    monkeypatch.setattr("sorter.service.classify_email", lambda e, k: mock_decision)

    service = EmailMonitorService(test_config, storage)
    with caplog.at_level(logging.ERROR):
        alerts_sent = service.run_once()

    # Even though college account failed with SSLError, personal account continued processing
    assert alerts_sent == 0
    assert storage.is_processed("Personal", "<personal@p.edu>")
    assert "SSL handshake failed" in caplog.text


def test_service_classifier_error_resilience(test_config, monkeypatch, caplog):
    storage = Storage(test_config.db_path)

    mock_email = ParsedEmail(
        "<err@c.edu>", "prof@college.edu", "Class", "date", "Body"
    )
    monkeypatch.setattr(
        "sorter.service.fetch_unseen_emails",
        lambda u, p: [mock_email] if u == "c@gmail.com" else [],
    )

    def failing_classifier(e, k):
        raise RuntimeError("Groq API 500 error")

    monkeypatch.setattr("sorter.service.classify_email", failing_classifier)

    service = EmailMonitorService(test_config, storage)
    with caplog.at_level(logging.ERROR):
        alerts_sent = service.run_once()

    assert alerts_sent == 0
    # Should not mark processed if classification errored out
    assert not storage.is_processed("College", "<err@c.edu>")
    assert "Groq API 500 error" in caplog.text


def test_service_start_runs_and_handles_keyboard_interrupt(test_config, monkeypatch):
    storage = Storage(test_config.db_path)
    service = EmailMonitorService(test_config, storage)

    call_count = 0

    def mock_run_once(alert_new=True):
        nonlocal call_count
        call_count += 1
        return 1

    monkeypatch.setattr(service, "run_once", mock_run_once)

    def mock_sleep(seconds):
        raise KeyboardInterrupt

    monkeypatch.setattr("time.sleep", mock_sleep)

    # Should exit cleanly on KeyboardInterrupt
    service.start()
    assert call_count == 1
