import os
from dataclasses import dataclass
from dotenv import load_dotenv


@dataclass
class Config:
    college_user: str
    college_pass: str
    personal_user: str
    personal_pass: str
    groq_api_key: str
    callmebot_phone: str
    callmebot_api_key: str
    groq_model: str = "llama-3.3-70b-versatile"
    poll_interval_seconds: int = 300
    db_path: str = "data/alerts.db"


def load_config() -> Config:
    load_dotenv()

    required_vars = [
        ("COLLEGE_GMAIL_USER", "college_user"),
        ("COLLEGE_GMAIL_PASSWORD", "college_pass"),
        ("PERSONAL_GMAIL_USER", "personal_user"),
        ("PERSONAL_GMAIL_PASSWORD", "personal_pass"),
        ("GROQ_API_KEY", "groq_api_key"),
        ("CALLMEBOT_PHONE", "callmebot_phone"),
        ("CALLMEBOT_API_KEY", "callmebot_api_key"),
    ]

    values = {}
    for env_var, field_name in required_vars:
        val = os.getenv(env_var)
        if not val:
            raise ValueError(f"Missing required environment variable: {env_var}")
        values[field_name] = val

    poll_interval_str = os.getenv("POLL_INTERVAL_SECONDS")
    if poll_interval_str:
        try:
            val = int(poll_interval_str)
            if val <= 0:
                raise ValueError
            values["poll_interval_seconds"] = val
        except ValueError:
            raise ValueError(f"POLL_INTERVAL_SECONDS must be a positive integer, got: {poll_interval_str}")

    db_path = os.getenv("DB_PATH")
    if db_path:
        values["db_path"] = db_path

    groq_model = os.getenv("GROQ_MODEL")
    if groq_model:
        values["groq_model"] = groq_model.strip()

    return Config(**values)
