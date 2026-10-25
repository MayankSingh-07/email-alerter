import email
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.base import MIMEBase
import pytest
from sorter.email_fetcher import (
    ParsedEmail,
    extract_email_body,
    parse_raw_message,
    fetch_unseen_emails,
)


def test_extract_html_fallback_and_stripping():
    msg = MIMEMultipart("alternative")
    msg["Subject"] = "OS Class Google Meet"
    msg["From"] = "prof@college.edu"
    msg["Message-ID"] = "<123@college.edu>"
    msg["Date"] = "Mon, 25 Oct 2026 10:00:00 +0000"
    html_content = "<html><body><p>Class starting at <b>11:30 AM</b>.<br>Join: <a href='https://meet.google.com/xyz'>Meet</a></p></body></html>"
    msg.attach(MIMEText(html_content, "html"))

    parsed = parse_raw_message(msg.as_bytes())
    assert parsed.subject == "OS Class Google Meet"
    assert parsed.sender == "prof@college.edu"
    assert parsed.message_id == "<123@college.edu>"
    assert "11:30 AM" in parsed.body
    assert "https://meet.google.com/xyz" in parsed.body
    assert "<html>" not in parsed.body
    assert "<p>" not in parsed.body


def test_extract_plain_text_preferred():
    msg = MIMEMultipart("alternative")
    msg["Subject"] = "Assignment 1 Reminder"
    msg["From"] = "ta@college.edu"
    msg["Message-ID"] = "<ta1@college.edu>"
    plain_text = "Please submit assignment 1 by 5 PM today."
    html_content = "<p>Please submit assignment 1 by <b>5 PM</b> today.</p>"
    msg.attach(MIMEText(plain_text, "plain"))
    msg.attach(MIMEText(html_content, "html"))

    parsed = parse_raw_message(msg.as_bytes())
    assert parsed.body == plain_text


def test_nested_multipart_structure():
    # outer multipart/mixed with inner multipart/alternative and an attachment
    outer = MIMEMultipart("mixed")
    outer["Subject"] = "Hackathon Invitation"
    outer["From"] = "unstop@example.com"
    outer["Message-ID"] = "<hack1@example.com>"

    alt = MIMEMultipart("alternative")
    alt.attach(MIMEText("Join the 24hr Hackathon! Link: https://unstop.com/hack", "plain"))
    alt.attach(MIMEText("<html><p>Join the <b>24hr Hackathon</b>!</p></html>", "html"))
    outer.attach(alt)

    attachment = MIMEBase("application", "pdf")
    attachment.set_payload(b"%PDF-fake-content")
    attachment.add_header("Content-Disposition", "attachment", filename="rulebook.pdf")
    outer.attach(attachment)

    parsed = parse_raw_message(outer.as_bytes())
    assert "Join the 24hr Hackathon!" in parsed.body
    assert "%PDF" not in parsed.body


def test_rfc2047_encoded_headers():
    raw = (
        b"From: =?utf-8?B?UHLDs2Zlc3NvciBY?=\r\n"
        b"Subject: =?utf-8?B?Tm90aWZpY2F0aW9uIPCfk6I=?=\r\n"
        b"Message-ID: <enc1@college.edu>\r\n"
        b"Content-Type: text/plain; charset=utf-8\r\n"
        b"\r\n"
        b"Meeting scheduled."
    )
    parsed = parse_raw_message(raw)
    assert parsed.sender == "Pr\xf3fessor X"
    assert "Notification 📢" in parsed.subject
    assert parsed.body == "Meeting scheduled."


def test_html_only_strips_scripts_and_styles():
    msg = MIMEText(
        "<html><head><style>.btn { color: red; }</style><script>alert('x');</script></head>"
        "<body><h1>Urgent Notice</h1><p>Quiz tomorrow &amp; bring calculators.<br>"
        "<a href='https://quiz.college.edu'>Click here</a></p></body></html>",
        "html",
    )
    parsed = parse_raw_message(msg.as_bytes())
    assert ".btn" not in parsed.body
    assert "alert" not in parsed.body
    assert "Urgent Notice" in parsed.body
    assert "Quiz tomorrow & bring calculators." in parsed.body
    assert "https://quiz.college.edu" in parsed.body


def test_fetch_unseen_emails_mocked(mocker):
    mock_imap = mocker.MagicMock()
    mocker.patch("imaplib.IMAP4_SSL", return_value=mock_imap)

    mock_imap.login.return_value = ("OK", [b"Logged in"])
    mock_imap.select.return_value = ("OK", [b"1"])
    mock_imap.search.return_value = ("OK", [b"101 102"])

    sample_email_1 = (
        b"From: prof@college.edu\r\n"
        b"Subject: Class Update\r\n"
        b"Message-ID: <id1@college.edu>\r\n"
        b"Content-Type: text/plain\r\n\r\n"
        b"Room changed to 301."
    )
    sample_email_2 = (
        b"From: hack@unstop.com\r\n"
        b"Subject: New Hackathon\r\n"
        b"Message-ID: <id2@unstop.com>\r\n"
        b"Content-Type: text/plain\r\n\r\n"
        b"Register now."
    )

    def mock_fetch(msg_id, query):
        if msg_id == b"101":
            return ("OK", [(b"101 (RFC822 {100})", sample_email_1), b")"])
        elif msg_id == b"102":
            return ("OK", [(b"102 (RFC822 {100})", sample_email_2), b")"])
        return ("NO", [])

    mock_imap.fetch.side_effect = mock_fetch

    results = fetch_unseen_emails("user@gmail.com", "secretpass")
    assert len(results) == 2
    assert results[0].message_id == "<id1@college.edu>"
    assert results[0].subject == "Class Update"
    assert results[0].body == "Room changed to 301."
    assert results[1].message_id == "<id2@unstop.com>"
    assert results[1].subject == "New Hackathon"

    mock_imap.login.assert_called_once_with("user@gmail.com", "secretpass")
    mock_imap.select.assert_called_once_with("INBOX")
    mock_imap.search.assert_called_once_with(None, "UNSEEN")
    assert mock_imap.logout.called


def test_fetch_unseen_emails_empty_inbox(mocker):
    mock_imap = mocker.MagicMock()
    mocker.patch("imaplib.IMAP4_SSL", return_value=mock_imap)

    mock_imap.login.return_value = ("OK", [b"Logged in"])
    mock_imap.select.return_value = ("OK", [b"0"])
    mock_imap.search.return_value = ("OK", [b""])

    results = fetch_unseen_emails("user@gmail.com", "secretpass")
    assert results == []
