import json
import pytest
from unittest.mock import MagicMock
from sorter.email_fetcher import ParsedEmail
from sorter.classifier import (
    ClassificationResult,
    classify_email,
    parse_llm_json_response,
)

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
    assert result.urgency == "high"
    assert result.summary == "Operating Systems online class starts in 15 minutes."
    assert result.deadline_or_time == "Today, 11:30 AM"
    assert result.action_link == "https://meet.google.com/xyz-abcd-efg"
    assert result.action_required == "Join meeting right away"

def test_parse_llm_json_with_trailing_commas_and_text():
    raw_text = """Here is the classification result:
    ```json
    {
      "is_alert_worthy": false,
      "category": "Promotional",
      "urgency": "low",
      "summary": "Marketing newsletter",
      "deadline_or_time": null,
      "action_link": null,
      "action_required": null,
    }
    ```
    Hope this helps!"""
    result = parse_llm_json_response(raw_text)
    assert result.is_alert_worthy is False
    assert result.category == "Promotional"
    assert result.urgency == "low"
    assert result.deadline_or_time is None
    assert result.action_link is None
    assert result.action_required is None

def test_parse_llm_json_bare_object():
    raw_text = '{"is_alert_worthy": true, "category": "Hackathon", "urgency": "medium", "summary": "Codefest registration open", "deadline_or_time": "Tomorrow 5 PM", "action_link": "https://unstop.com/hackathons/1", "action_required": "Register before deadline"}'
    result = parse_llm_json_response(raw_text)
    assert result.is_alert_worthy is True
    assert result.category == "Hackathon"

def test_parse_llm_json_invalid_raises_value_error():
    with pytest.raises(ValueError, match="Could not extract valid JSON"):
        parse_llm_json_response("This is not valid json at all")

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
    assert res.category == "Promotional"

    # Verify requests.post payload and headers
    assert mock_post.called
    call_kwargs = mock_post.call_args[1]
    assert call_kwargs["headers"]["Authorization"] == "Bearer dummy_key"
    assert call_kwargs["json"]["model"] == "llama-3.3-70b-versatile"
    assert call_kwargs["json"]["temperature"] == 0.1
    # Check that system prompt and user content contain email details
    messages = call_kwargs["json"]["messages"]
    assert any(m["role"] == "system" for m in messages)
    user_msg = next(m["content"] for m in messages if m["role"] == "user")
    assert "promo@unstop.com" in user_msg
    assert "Learn AI Discount" in user_msg
    assert "Buy our course now." in user_msg

def test_classify_email_api_error(monkeypatch):
    mock_post = MagicMock()
    mock_post.return_value.status_code = 500
    mock_post.return_value.text = "Internal Server Error"
    mock_post.return_value.raise_for_status.side_effect = Exception("500 Server Error")
    monkeypatch.setattr("requests.post", mock_post)

    email_data = ParsedEmail("2", "prof@college.edu", "Class Notice", "date", "Class at 10 AM.")
    with pytest.raises(Exception):
        classify_email(email_data, api_key="dummy_key")

def test_classify_email_truncates_long_body(monkeypatch):
    mock_post = MagicMock()
    mock_post.return_value.status_code = 200
    mock_post.return_value.json.return_value = {
        "choices": [{"message": {"content": json.dumps({
            "is_alert_worthy": True,
            "category": "Assignment / Exam",
            "urgency": "high",
            "summary": "Long announcement",
            "deadline_or_time": "Tomorrow",
            "action_link": None,
            "action_required": "Study"
        })}}]
    }
    monkeypatch.setattr("requests.post", mock_post)

    long_body = "A" * 10000
    email_data = ParsedEmail("3", "prof@college.edu", "Huge Exam Details", "date", long_body)
    classify_email(email_data, api_key="dummy_key")

    user_msg = next(m["content"] for m in mock_post.call_args[1]["json"]["messages"] if m["role"] == "user")
    assert ("A" * 4000) in user_msg
    assert ("A" * 4001) not in user_msg
