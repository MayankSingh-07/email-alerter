"""Email fetcher and MIME parser for incoming Gmail messages."""

from dataclasses import dataclass
import email
from email.header import decode_header
import email.message
import hashlib
from html.parser import HTMLParser
import imaplib
import re


@dataclass
class ParsedEmail:
    message_id: str
    sender: str
    subject: str
    date: str
    body: str


class _HTMLTextExtractor(HTMLParser):
    """HTML parser that strips tags, ignores scripts/styles, and captures link URLs."""

    def __init__(self):
        super().__init__()
        self._pieces: list[str] = []
        self._ignore_depth: int = 0

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]):
        tag_lower = tag.lower()
        if tag_lower in ("script", "style", "head"):
            self._ignore_depth += 1
            return

        if self._ignore_depth > 0:
            return

        if tag_lower in ("p", "div", "br", "tr", "li", "h1", "h2", "h3", "h4", "h5", "h6"):
            self._pieces.append("\n")

        if tag_lower == "a":
            href = dict(attrs).get("href")
            if href:
                # Capture link url inline
                self._pieces.append(f" {href} ")

    def handle_endtag(self, tag: str):
        tag_lower = tag.lower()
        if tag_lower in ("script", "style", "head"):
            if self._ignore_depth > 0:
                self._ignore_depth -= 1
            return
        if self._ignore_depth == 0 and tag_lower in ("p", "div", "tr", "li", "h1", "h2", "h3", "h4", "h5", "h6"):
            self._pieces.append("\n")

    def handle_data(self, data: str):
        if self._ignore_depth == 0 and data:
            self._pieces.append(data)

    def get_text(self) -> str:
        raw_text = "".join(self._pieces)
        # Normalize whitespace while preserving paragraphs
        lines = [line.strip() for line in raw_text.splitlines()]
        cleaned = "\n".join(line for line in lines if line)
        return cleaned.strip()


def _decode_header_value(header_val: str | None) -> str:
    """Safely decode RFC 2047 encoded email headers."""
    if not header_val:
        return ""
    decoded_fragments = decode_header(header_val)
    parts: list[str] = []
    for fragment, charset in decoded_fragments:
        if isinstance(fragment, bytes):
            try:
                parts.append(fragment.decode(charset or "utf-8", errors="replace"))
            except (LookupError, UnicodeDecodeError):
                parts.append(fragment.decode("utf-8", errors="replace"))
        else:
            parts.append(str(fragment))
    return "".join(parts).strip()


def _clean_html(html_str: str) -> str:
    """Extract clean plain text from HTML string."""
    parser = _HTMLTextExtractor()
    try:
        parser.feed(html_str)
        parser.close()
        return parser.get_text()
    except Exception:
        # Fallback to regex strip if parser fails
        text = re.sub(r"(?is)<(script|style).*?>.*?</\1>", "", html_str)
        text = re.sub(r"<[^>]+>", " ", text)
        return " ".join(text.split())


def _decode_payload(part: email.message.Message) -> str:
    """Decode a message part's payload using its declared charset, falling back safely."""
    payload = part.get_payload(decode=True)
    if payload is None:
        return ""
    if isinstance(payload, str):
        return payload

    charset = part.get_content_charset()
    if charset:
        try:
            return payload.decode(charset, errors="replace")
        except (LookupError, UnicodeDecodeError):
            pass

    for enc in ("utf-8", "latin-1", "windows-1252"):
        try:
            return payload.decode(enc)
        except UnicodeDecodeError:
            continue

    return payload.decode("utf-8", errors="replace")


def extract_email_body(msg: email.message.Message) -> str:
    """
    Extract readable plain text from email message.
    Handles plain text, multipart/alternative, nested multiparts, and HTML fallbacks.
    """
    plain_bodies: list[str] = []
    html_bodies: list[str] = []

    if msg.is_multipart():
        for part in msg.walk():
            # Skip multipart containers
            if part.is_multipart():
                continue

            content_type = part.get_content_type()
            content_disposition = str(part.get("Content-Disposition", ""))

            # Skip attachments
            if "attachment" in content_disposition:
                continue

            if content_type == "text/plain":
                text = _decode_payload(part).strip()
                if text:
                    plain_bodies.append(text)
            elif content_type == "text/html":
                text = _decode_payload(part).strip()
                if text:
                    html_bodies.append(text)
    else:
        content_type = msg.get_content_type()
        text = _decode_payload(msg).strip()
        if content_type == "text/plain":
            plain_bodies.append(text)
        elif content_type == "text/html":
            html_bodies.append(text)

    # Prefer plain text if available
    if plain_bodies:
        return "\n\n".join(plain_bodies).strip()

    # Fallback to HTML stripping
    if html_bodies:
        combined_html = "\n\n".join(html_bodies)
        return _clean_html(combined_html)

    return ""


def parse_raw_message(raw_bytes: bytes) -> ParsedEmail:
    """Parse raw email RFC822 bytes into a structured ParsedEmail object."""
    msg = email.message_from_bytes(raw_bytes)

    message_id = msg.get("Message-ID", "").strip()
    sender = _decode_header_value(msg.get("From", ""))
    subject = _decode_header_value(msg.get("Subject", ""))
    date = msg.get("Date", "").strip()
    body = extract_email_body(msg)

    if not message_id:
        fallback_seed = f"{sender}|{subject}|{date}|{body[:100]}"
        message_id = f"<gen-{hashlib.sha256(fallback_seed.encode('utf-8')).hexdigest()[:16]}>"

    return ParsedEmail(
        message_id=message_id,
        sender=sender,
        subject=subject,
        date=date,
        body=body,
    )


def fetch_unseen_emails(
    user: str,
    password: str,
    host: str = "imap.gmail.com",
    mailbox: str = "INBOX",
) -> list[ParsedEmail]:
    """
    Connect to IMAP SSL, fetch unseen emails, and return parsed ParsedEmail list.
    Marks retrieved emails or keeps them depending on mailbox state.
    """
    parsed_emails: list[ParsedEmail] = []

    mail = imaplib.IMAP4_SSL(host, timeout=30)
    try:
        mail.login(user, password)
        status, _ = mail.select(mailbox)
        if status != "OK":
            return []

        status, response = mail.search(None, "UNSEEN")
        if status != "OK" or not response or not response[0]:
            return []

        msg_ids = response[0].split()
        for msg_id in msg_ids:
            res_status, msg_data = mail.fetch(msg_id, "(BODY.PEEK[])")
            if res_status != "OK" or not msg_data:
                continue

            for part in msg_data:
                if isinstance(part, tuple) and len(part) > 1 and isinstance(part[1], bytes):
                    parsed_email = parse_raw_message(part[1])
                    parsed_emails.append(parsed_email)
                    break
    finally:
        try:
            mail.close()
        except Exception:
            pass
        try:
            mail.logout()
        except Exception:
            pass

    return parsed_emails
