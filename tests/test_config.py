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
    assert cfg.college_pass == "app-pass-1"
    assert cfg.personal_user == "personal@gmail.com"
    assert cfg.personal_pass == "app-pass-2"
    assert cfg.groq_api_key == "gsk_test123"
    assert cfg.callmebot_phone == "+919876543210"
    assert cfg.callmebot_api_key == "cmb_test456"
    assert cfg.poll_interval_seconds == 180
    assert cfg.db_path == "data/alerts.db"

def test_load_config_missing_required_raises(monkeypatch):
    monkeypatch.setenv("COLLEGE_GMAIL_USER", "student@college.edu")
    monkeypatch.setenv("COLLEGE_GMAIL_PASSWORD", "app-pass-1")
    monkeypatch.setenv("PERSONAL_GMAIL_USER", "personal@gmail.com")
    monkeypatch.setenv("PERSONAL_GMAIL_PASSWORD", "app-pass-2")
    monkeypatch.setenv("CALLMEBOT_PHONE", "+919876543210")
    monkeypatch.setenv("CALLMEBOT_API_KEY", "cmb_test456")
    monkeypatch.delenv("GROQ_API_KEY", raising=False)
    with pytest.raises(ValueError, match="GROQ_API_KEY"):
        load_config()

def test_load_config_defaults(monkeypatch):
    monkeypatch.setenv("COLLEGE_GMAIL_USER", "student@college.edu")
    monkeypatch.setenv("COLLEGE_GMAIL_PASSWORD", "app-pass-1")
    monkeypatch.setenv("PERSONAL_GMAIL_USER", "personal@gmail.com")
    monkeypatch.setenv("PERSONAL_GMAIL_PASSWORD", "app-pass-2")
    monkeypatch.setenv("GROQ_API_KEY", "gsk_test123")
    monkeypatch.setenv("CALLMEBOT_PHONE", "+919876543210")
    monkeypatch.setenv("CALLMEBOT_API_KEY", "cmb_test456")
    monkeypatch.delenv("POLL_INTERVAL_SECONDS", raising=False)
    monkeypatch.delenv("DB_PATH", raising=False)

    cfg = load_config()
    assert cfg.poll_interval_seconds == 300
    assert cfg.db_path == "data/alerts.db"

def test_load_config_invalid_poll_interval(monkeypatch):
    monkeypatch.setenv("COLLEGE_GMAIL_USER", "student@college.edu")
    monkeypatch.setenv("COLLEGE_GMAIL_PASSWORD", "app-pass-1")
    monkeypatch.setenv("PERSONAL_GMAIL_USER", "personal@gmail.com")
    monkeypatch.setenv("PERSONAL_GMAIL_PASSWORD", "app-pass-2")
    monkeypatch.setenv("GROQ_API_KEY", "gsk_test123")
    monkeypatch.setenv("CALLMEBOT_PHONE", "+919876543210")
    monkeypatch.setenv("CALLMEBOT_API_KEY", "cmb_test456")
    monkeypatch.setenv("POLL_INTERVAL_SECONDS", "not-a-number")

    with pytest.raises(ValueError, match="POLL_INTERVAL_SECONDS"):
        load_config()
