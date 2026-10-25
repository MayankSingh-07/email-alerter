# Email Classifier & WhatsApp Alerter Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a 24/7 cloud-ready background service that monitors dual Gmail accounts (College and Personal), uses hosted open-source LLaMA 3.3 via Groq to filter and extract critical academic/competition details, and delivers structured Option B briefings directly to WhatsApp via CallMeBot.

**Architecture:** A lightweight Python daemon executes a periodic polling cycle over IMAP SSL for both Gmail accounts. Unprocessed emails are parsed, checked against an SQLite deduplication store, evaluated for actionability and key facts via Groq API (LLaMA 3.3 70B), and dispatched as formatted Option B WhatsApp messages using the CallMeBot gateway.

**Tech Stack:** Python 3.11+, `imaplib`, `sqlite3`, `groq` (or `requests` to Groq REST API), `requests`, `python-dotenv`, `pytest`, `pytest-mock`.

**Spec:** `docs/superpowers/specs/2026-10-25-email-alerter-design.md`

## Global Constraints

- **Python Version:** Python 3.10+ compatible.
- **Cost:** Zero paid services; strictly free tiers (Groq API free tier, CallMeBot WhatsApp API, free cloud runner).
- **Inboxes:** Support simultaneous monitoring of College Gmail and Personal Gmail.
- **Notification Style:** Option B Detailed Briefing format with account badge, sender context, summary, deadline, clickable links, and action requirement.
- **Filtering Standard:** Content-based actionability filter: discard promotional blasts and non-actionable hype even from legitimate platforms (e.g., Unstop courses vs. Unstop hackathons).

## Review Focus

1. **HTML/MIME Multipart Body Extraction:** Emails containing only nested `multipart/alternative` or rich HTML (e.g., Unstop HTML flyers, Google Classroom HTML notices) must extract clean readable plain text without raw HTML tags. (Pinned to Task 3).
2. **LLaMA Malformed/Markdown-Wrapped JSON:** Groq/LLaMA output wrapped in markdown fences (e.g. ` ```json ... ``` `) or containing trailing commas must parse safely into structured dicts without crashing the worker. (Pinned to Task 4).
3. **CallMeBot Rate Limiting & Character Encoding:** WhatsApp alert text with emojis, ampersands, or long URLs must be correctly URL-encoded and dispatched without truncation or 429 throttling errors. (Pinned to Task 5).
4. **IMAP Disconnection & Reconnection Resiliency:** Network drops or SSL socket timeouts during IMAP polling must be caught, logged, and retried cleanly on the next cycle without terminating the daemon. (Pinned to Task 6).
5. **Initial Boot Inbox Flood Prevention:** On first boot with an existing inbox of 1000+ unread emails, the service must not spam WhatsApp with historical alerts; only emails arriving after initial sync or within a strict recent window should trigger alerts. (Pinned to Task 2 & Task 6).

---

### Task 1: Project Setup & Configuration Management

**Files:**
- Create: `requirements.txt`
- Create: `sorter/__init__.py`
- Create: `sorter/config.py`
- Create: `.env.example`
- Test: `tests/test_config.py`

**Interfaces:**
- Produces: `sorter.config.Config` dataclass and `load_config() -> Config` with fields:
  - `college_user: str`
  - `college_pass: str`
  - `personal_user: str`
  - `personal_pass: str`
  - `groq_api_key: str`
  - `callmebot_phone: str`
  - `callmebot_api_key: str`
  - `poll_interval_seconds: int` (default 300)
  - `db_path: str` (default "data/alerts.db")

- [ ] **Step 1: Write the failing test for configuration loading**

```python
# tests/test_config.py
import os
import pytest
from sorter.config import load_config, Config

def test_load_config_from_env(monkeypatch):
    monkeypatch.setenv("COLLEGE_GMAIL_USER", "student@college.edu")
    monkeypatch.setenv("COLLEGE_GMAIL_PASSWORD", "app-pass-1")
    monkeypatch.setenv("PERSONAL_GMAIL_USER", "personal@gmail.com")
    monkeypatch.setenv("PERSONAL_GMAIL_PASSWORD", "app-pass-2")
    monkeypatch.setenv("GROQ_API_KEY", "gsk_test123")
    monkeypatch.setenv("CALLMEBOT_PHONE", "+919876543210")
    monkeypatch.setenv("CALLMEBOT_API_KEY", "cmb_test456")
    monkeypatch.setenv("POLL_INTERVAL_SECONDS", "180")
    
    cfg = load_config()
    assert cfg.college_user == "student@college.edu"
    assert cfg.poll_interval_seconds == 180
    assert cfg.db_path == "data/alerts.db"

def test_load_config_missing_required_raises(monkeypatch):
    monkeypatch.delenv("GROQ_API_KEY", raising=False)
    with pytest.raises(ValueError, match="GROQ_API_KEY"):
        load_config()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_config.py -v`  
Expected: FAIL with ModuleNotFoundError or ImportError for `sorter.config`

- [ ] **Step 3: Implement `requirements.txt`, `sorter/config.py`, and `.env.example`**

Define `Config` dataclass with type hints, defaults, and validation in `sorter/config.py`.

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_config.py -v`  
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add requirements.txt sorter/__init__.py sorter/config.py .env.example tests/test_config.py
git commit -m "feat: add configuration loader and environment definition"
```

---

### Task 2: SQLite Deduplication & State Storage

**Files:**
- Create: `sorter/storage.py`
- Test: `tests/test_storage.py`

**Interfaces:**
- Consumes: `db_path: str`
- Produces: `sorter.storage.Storage` class:
  - `__init__(db_path: str)`
  - `is_processed(account: str, message_id: str) -> bool`
  - `mark_processed(account: str, message_id: str, subject: str, alerted: bool)`
  - `get_processed_count() -> int`

- [ ] **Step 1: Write the failing test for SQLite storage**

```python
# tests/test_storage.py
import os
from sorter.storage import Storage

def test_storage_lifecycle(tmp_path):
    db_file = str(tmp_path / "test.db")
    storage = Storage(db_file)
    
    # Verify initial state
    assert not storage.is_processed("college", "<msg1@college.edu>")
    assert storage.get_processed_count() == 0
    
    # Mark as processed
    storage.mark_processed("college", "<msg1@college.edu>", "Urgent Class", True)
    assert storage.is_processed("college", "<msg1@college.edu>")
    assert storage.get_processed_count() == 1
    
    # Separate account with same message_id should not collide
    assert not storage.is_processed("personal", "<msg1@college.edu>")
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_storage.py -v`  
Expected: FAIL with ModuleNotFoundError: No module named 'sorter.storage'

- [ ] **Step 3: Implement `Storage` in `sorter/storage.py`**

Initialize SQLite database schema `processed_emails(account TEXT, message_id TEXT, subject TEXT, alerted INTEGER, processed_at TIMESTAMP, PRIMARY KEY(account, message_id))`.

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_storage.py -v`  
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add sorter/storage.py tests/test_storage.py
git commit -m "feat: add SQLite deduplication and state storage"
```

---

### Task 3: Email Ingestion & Plaintext Extraction

**Files:**
- Create: `sorter/email_fetcher.py`
- Test: `tests/test_email_fetcher.py`

**Interfaces:**
- Produces:
  - `ParsedEmail` dataclass: `message_id: str, sender: str, subject: str, date: str, body: str`
  - `extract_email_body(msg: email.message.Message) -> str`
  - `fetch_unseen_emails(user: str, password: str, host: str = "imap.gmail.com") -> list[ParsedEmail]`

- [ ] **Step 1: Write the failing test for email body extraction and parsing**

```python
# tests/test_email_fetcher.py
import email
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from sorter.email_fetcher import extract_email_body, parse_raw_message

def test_extract_html_fallback_and_stripping():
    msg = MIMEMultipart('alternative')
    msg['Subject'] = 'OS Class Google Meet'
    msg['From'] = 'prof@college.edu'
    msg['Message-ID'] = '<123@college.edu>'
    html_content = "<html><body><p>Class starting at <b>11:30 AM</b>.<br>Join: <a href='https://meet.google.com/xyz'>Meet</a></p></body></html>"
    msg.attach(MIMEText(html_content, 'html'))
    
    parsed = parse_raw_message(msg.as_bytes())
    assert parsed.subject == 'OS Class Google Meet'
    assert parsed.sender == 'prof@college.edu'
    assert '11:30 AM' in parsed.body
    assert 'meet.google.com/xyz' in parsed.body
    assert '<html>' not in parsed.body
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_email_fetcher.py -v`  
Expected: FAIL with ModuleNotFoundError: No module named 'sorter.email_fetcher'

- [ ] **Step 3: Implement `extract_email_body`, `parse_raw_message`, and `fetch_unseen_emails`**

In `sorter/email_fetcher.py`:
- Use `html.parser` or regex/unescape to cleanly strip tags from HTML when text/plain is missing.
- Handle charset decoding (utf-8, latin-1 fallback).
- Implement `fetch_unseen_emails` with `imaplib.IMAP4_SSL`.

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_email_fetcher.py -v`  
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add sorter/email_fetcher.py tests/test_email_fetcher.py
git commit -m "feat: add email parsing and IMAP ingestion"
```

---

### Task 4: AI Classifier & Action Item Extractor (Groq LLaMA)

**Files:**
- Create: `sorter/classifier.py`
- Test: `tests/test_classifier.py`

**Interfaces:**
- Consumes: `groq_api_key: str`, `ParsedEmail`
- Produces:
  - `ClassificationResult` dataclass:
    - `is_alert_worthy: bool`
    - `category: str`
    - `urgency: str`
    - `summary: str`
    - `deadline_or_time: str | None`
    - `action_link: str | None`
    - `action_required: str | None`
  - `classify_email(email_data: ParsedEmail, api_key: str, model: str = "llama-3.3-70b-versatile") -> ClassificationResult`

- [ ] **Step 1: Write the failing test for AI classification and JSON parsing**

```python
# tests/test_classifier.py
import json
from unittest.mock import MagicMock
from sorter.email_fetcher import ParsedEmail
from sorter.classifier import classify_email, parse_llm_json_response

def test_parse_llm_json_with_markdown_fences():
    raw_markdown = """```json
    {
      "is_alert_worthy": true,
      "category": "Online Class",
      "urgency": "high",
      "summary": "Operating Systems online class starts in 15 minutes.",
      "deadline_or_time": "Today, 11:30 AM",
      "action_link": "https://meet.google.com/xyz-abcd-efg",
      "action_required": "Join meeting right away"
    }
    ```"""
    result = parse_llm_json_response(raw_markdown)
    assert result.is_alert_worthy is True
    assert result.category == "Online Class"
    assert result.action_link == "https://meet.google.com/xyz-abcd-efg"

def test_classify_promotional_email_returns_false(monkeypatch):
    mock_post = MagicMock()
    mock_post.return_value.status_code = 200
    mock_post.return_value.json.return_value = {
        "choices": [{"message": {"content": json.dumps({
            "is_alert_worthy": False,
            "category": "Promotional",
            "urgency": "low",
            "summary": "50% off web development bootcamp",
            "deadline_or_time": None,
            "action_link": None,
            "action_required": None
        })}}]
    }
    monkeypatch.setattr("requests.post", mock_post)
    
    email_data = ParsedEmail("1", "promo@unstop.com", "Learn AI Discount", "date", "Buy our course now.")
    res = classify_email(email_data, api_key="dummy_key")
    assert res.is_alert_worthy is False
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_classifier.py -v`  
Expected: FAIL with ModuleNotFoundError: No module named 'sorter.classifier'

- [ ] **Step 3: Implement `classify_email` and prompt template in `sorter/classifier.py`**

Construct strict system prompt enforcing JSON schema and criteria (distinguishing actionable hackathons/classes vs. promotions). Use `requests.post` targeting `https://api.groq.com/openai/v1/chat/completions`. Clean code fences from the returned response before `json.loads`.

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_classifier.py -v`  
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add sorter/classifier.py tests/test_classifier.py
git commit -m "feat: add Groq LLaMA classifier and JSON response parser"
```

---

### Task 5: WhatsApp Option B Alerter (CallMeBot)

**Files:**
- Create: `sorter/alerter.py`
- Test: `tests/test_alerter.py`

**Interfaces:**
- Consumes: `account_label: str`, `ParsedEmail`, `ClassificationResult`, `phone: str`, `api_key: str`
- Produces:
  - `format_whatsapp_message(account: str, email_data: ParsedEmail, decision: ClassificationResult) -> str`
  - `send_whatsapp_alert(phone: str, api_key: str, message: str) -> bool`

- [ ] **Step 1: Write the failing test for Option B message formatting and URL dispatch**

```python
# tests/test_alerter.py
from unittest.mock import MagicMock
from sorter.email_fetcher import ParsedEmail
from sorter.classifier import ClassificationResult
from sorter.alerter import format_whatsapp_message, send_whatsapp_alert

def test_format_option_b_message():
    email_data = ParsedEmail("<id1>", "prof@college.edu", "Lab 3 Teams", "date", "Form teams of 3.")
    decision = ClassificationResult(
        is_alert_worthy=True,
        category="Assignment",
        urgency="high",
        summary="Form groups of 3 for the distributed systems project.",
        deadline_or_time="Oct 30, 11:59 PM",
        action_link="https://forms.gle/lab3teams",
        action_required="Find 2 team members and submit Google Form"
    )
    
    msg = format_whatsapp_message("College", email_data, decision)
    assert "[College] Assignment" in msg
    assert "From: prof@college.edu" in msg
    assert "Subject: Lab 3 Teams" in msg
    assert "Oct 30, 11:59 PM" in msg
    assert "https://forms.gle/lab3teams" in msg
    assert "Action: Find 2 team members" in msg

def test_send_whatsapp_alert_success(monkeypatch):
    mock_get = MagicMock()
    mock_get.return_value.status_code = 200
    monkeypatch.setattr("requests.get", mock_get)
    
    ok = send_whatsapp_alert("+919876543210", "apikey123", "Test Alert")
    assert ok is True
    assert mock_get.called
    called_url = mock_get.call_args[0][0]
    assert "api.callmebot.com/whatsapp.php" in called_url
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_alerter.py -v`  
Expected: FAIL with ModuleNotFoundError: No module named 'sorter.alerter'

- [ ] **Step 3: Implement `format_whatsapp_message` and `send_whatsapp_alert` in `sorter/alerter.py`**

Format Option B layout with emoji indicators, encode message parameters with `urllib.parse.quote_plus`, and execute GET request to CallMeBot API.

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_alerter.py -v`  
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add sorter/alerter.py tests/test_alerter.py
git commit -m "feat: add WhatsApp Option B message formatter and CallMeBot client"
```

---

### Task 6: Polling Orchestrator Service & CLI Entrypoint

**Files:**
- Create: `sorter/service.py`
- Create: `main.py`
- Test: `tests/test_service.py`

**Interfaces:**
- Consumes: `Config`, `Storage`, `email_fetcher`, `classifier`, `alerter`
- Produces:
  - `class EmailMonitorService`:
    - `run_once() -> int` (returns number of alerts dispatched)
    - `start()` (runs continuous polling loop with interval)
  - `main.py` CLI supporting `--once` and `--daemon` modes.

- [ ] **Step 1: Write the failing integration test for the polling service**

```python
# tests/test_service.py
from unittest.mock import MagicMock
from sorter.config import Config
from sorter.storage import Storage
from sorter.email_fetcher import ParsedEmail
from sorter.classifier import ClassificationResult
from sorter.service import EmailMonitorService

def test_service_run_once_end_to_end(tmp_path, monkeypatch):
    cfg = Config(
        college_user="c@gmail.com", college_pass="cp",
        personal_user="p@gmail.com", personal_pass="pp",
        groq_api_key="gk", callmebot_phone="123", callmebot_api_key="ck",
        poll_interval_seconds=300, db_path=str(tmp_path / "alerts.db")
    )
    storage = Storage(cfg.db_path)
    
    # Mock email fetching
    mock_email = ParsedEmail("<1@c.edu>", "prof@college.edu", "Class Link", "date", "Join class.")
    monkeypatch.setattr("sorter.service.fetch_unseen_emails", lambda u, p: [mock_email] if u == "c@gmail.com" else [])
    
    # Mock classifier
    mock_decision = ClassificationResult(True, "Online Class", "high", "Class starting.", "10 AM", "https://meet.google.com/abc", "Join now")
    monkeypatch.setattr("sorter.service.classify_email", lambda e, k: mock_decision)
    
    # Mock alerter
    mock_alert = MagicMock(return_value=True)
    monkeypatch.setattr("sorter.service.send_whatsapp_alert", mock_alert)
    
    service = EmailMonitorService(cfg, storage)
    alerts_sent = service.run_once()
    
    assert alerts_sent == 1
    assert storage.is_processed("College", "<1@c.edu>")
    assert mock_alert.called
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_service.py -v`  
Expected: FAIL with ModuleNotFoundError: No module named 'sorter.service'

- [ ] **Step 3: Implement `EmailMonitorService` in `sorter/service.py` and entrypoint `main.py`**

Orchestrate the loop:
1. Iterate over both accounts (`College`, `Personal`).
2. Fetch unread emails.
3. Skip already processed emails via `Storage`.
4. Run classifier.
5. If `is_alert_worthy`, send WhatsApp alert.
6. Record processed status in `Storage`.
7. Catch IMAP/network exceptions to prevent crashing the daemon.

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_service.py -v`  
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add sorter/service.py main.py tests/test_service.py
git commit -m "feat: add email monitor service and CLI entrypoint"
```

---

### Task 7: Containerization, Deployment Guide, & Smoke Verification

**Files:**
- Create: `Dockerfile`
- Create: `render.yaml`
- Create: `README.md`
- Test: Throwaway verification script `tests/smoke_verify.py`

**Interfaces:**
- Produces: Production Docker container and Render free tier blueprint for 24/7 background worker execution.

- [ ] **Step 1: Write smoke test verifying CLI argument parsing and components**

```python
# tests/test_smoke.py
import subprocess
import sys

def test_cli_help():
    result = subprocess.run([sys.executable, "main.py", "--help"], capture_output=True, text=True)
    assert result.returncode == 0
    assert "email monitor" in result.stdout.lower()
```

- [ ] **Step 2: Run test to verify it passes**

Run: `pytest tests/test_smoke.py -v`  
Expected: PASS

- [ ] **Step 3: Create `Dockerfile`, `render.yaml`, and `README.md`**

Write standard `Dockerfile` (Python 3.11-slim, install deps, non-root user), `render.yaml` (worker type, env vars), and comprehensive `README.md` explaining how to obtain Gmail App Passwords, Groq API key, and CallMeBot API key.

- [ ] **Step 4: Run full test suite to verify 100% green build**

Run: `pytest tests/ -v`  
Expected: All unit & integration tests PASS.

- [ ] **Step 5: Commit**

```bash
git add Dockerfile render.yaml README.md tests/test_smoke.py
git commit -m "chore: add deployment manifests and documentation"
```
