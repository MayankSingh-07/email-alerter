import os
import sqlite3
from datetime import datetime, timezone


class Storage:
    def __init__(self, db_path: str):
        self.db_path = db_path
        db_dir = os.path.dirname(db_path)
        if db_dir:
            os.makedirs(db_dir, exist_ok=True)
        self._init_db()

    def _get_connection(self) -> sqlite3.Connection:
        return sqlite3.connect(self.db_path)

    def _init_db(self) -> None:
        conn = self._get_connection()
        try:
            with conn:
                conn.execute(
                    """
                    CREATE TABLE IF NOT EXISTS processed_emails (
                        account TEXT,
                        message_id TEXT,
                        subject TEXT,
                        alerted INTEGER,
                        processed_at TIMESTAMP,
                        PRIMARY KEY(account, message_id)
                    )
                    """
                )
        finally:
            conn.close()

    def is_processed(self, account: str, message_id: str) -> bool:
        conn = self._get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT 1 FROM processed_emails WHERE account = ? AND message_id = ?",
                (account, message_id),
            )
            return cursor.fetchone() is not None
        finally:
            conn.close()

    def mark_processed(
        self, account: str, message_id: str, subject: str, alerted: bool
    ) -> None:
        now = datetime.now(timezone.utc).isoformat()
        conn = self._get_connection()
        try:
            with conn:
                conn.execute(
                    """
                    INSERT INTO processed_emails (account, message_id, subject, alerted, processed_at)
                    VALUES (?, ?, ?, ?, ?)
                    ON CONFLICT(account, message_id) DO UPDATE SET
                        subject = excluded.subject,
                        alerted = excluded.alerted,
                        processed_at = excluded.processed_at
                    """,
                    (account, message_id, subject, 1 if alerted else 0, now),
                )
        finally:
            conn.close()

    def get_processed_count(self) -> int:
        conn = self._get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute("SELECT COUNT(*) FROM processed_emails")
            row = cursor.fetchone()
            return row[0] if row else 0
        finally:
            conn.close()
