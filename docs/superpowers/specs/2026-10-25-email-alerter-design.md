# Design Document: AI Email Classifier & WhatsApp Alerter

**Date:** 2026-10-25  
**Status:** Draft  
**Target:** 24/7 Cloud-Based Student Email Monitor  

---

## 1. Intent & The Why

College students frequently miss critical, time-sensitive academic announcements because they rarely check their email inboxes. Missed communications include:
- Surprise online class announcements (e.g., Google Meet link sent 20 minutes before class).
- Critical assignment requirements (e.g., mandatory group formation with short deadlines).
- Quiz announcements and academic deadlines.
- Competitive opportunities (e.g., hackathons and contest registrations).

The system acts as an **active safety net**: an always-on background service that monitors incoming emails, filters out marketing and promotional noise using an open-source LLM (LLaMA), extracts critical dates, links, and action items, and immediately delivers structured alerts to WhatsApp where the student actually looks.

---

## 2. Goals, Non-Goals, & Anti-Goals

### Goals
- **Instant Actionable Alerts:** Extract and deliver high-stakes details (Meet links, deadlines, team formation requirements, hackathon registrations) within 5–10 minutes of arrival.
- **Structured Briefing Format (Option B):** Every alert must include:
  - Account source badge (`[College]` or `[Personal]`)
  - Category indicator (e.g., `🔴 URGENT: Online Class`, `📌 Assignment`, `🏆 Hackathon`)
  - Sender and subject line context
  - 1–2 sentence actionable summary
  - Key date/deadline
  - Clickable action link (Google Meet, Google Form, Portal)
  - Explicit action required (e.g., "⚠️ Action: Join meeting right away")
- **Dual Gmail Support:** Monitor both college student inbox and personal inbox simultaneously.
- **Zero-Cost & 24/7 Availability:** 100% free hosting and API usage, running in the cloud with zero dependency on the student's personal laptop being awake.

### Non-Goals
- Two-way interaction (e.g., replying to emails via WhatsApp).
- Comprehensive email sorting into dozens of client-side folders.
- Web dashboard or complex GUI (configuration via environment variables / config file).

### Anti-Goals (What would make this a failure)
- **Alert Fatigue:** Forwarding spam, course marketing blasts (e.g., Unstop courses/webinars), cultural society recruitment hype, or generic campus newsletters.
- **Laptop Battery Drain:** Requiring local GPU/CPU compute or keeping a personal laptop awake 24/7.
- **Brittle Browser Automation:** Relying on automated WhatsApp Web browser sessions (Puppeteer/Playwright) that disconnect or break frequently.

---

## 3. Constraints

- **Hardware/Hosting:** The user does not have an always-on home server or secondary device. The service must run on a free cloud tier (e.g., Render background worker, PythonAnywhere, or scheduled GitHub Actions).
- **Delivery Channel:** Strictly WhatsApp (user does not use Telegram).
- **Cost:** Must use free tiers exclusively:
  - Groq Free Tier (for hosted open-source LLaMA 3.3 70B / 3.1 8B inference).
  - CallMeBot Free Tier (HTTP-based personal WhatsApp gateway).
  - Gmail IMAP / API (standard Google account access).
- **Email Inboxes:** Both accounts are hosted on Google (Gmail / Google Workspace).

---

## 4. User-Decided Specifications

| Component | Decision | Rationale |
|-----------|----------|-----------|
| **Email Accounts** | Dual Gmail (`[College]` + `[Personal]`) | Both accounts on Gmail allows consistent ingestion architecture. |
| **Alert Destination** | WhatsApp | User does not use Telegram; WhatsApp is where they spend their day. |
| **Notification Style** | Option B: Detailed Briefing | Gives sender, subject, concise summary, deadline, and action item so user rarely needs to open Gmail. |
| **AI Model** | Open-source LLaMA (via Groq API) | High-speed, structured extraction without requiring local VRAM or laptop compute. |
| **Filtering Threshold** | Content-based Actionability Filter | Senders cannot be bluntly blacklisted: Unstop promotional emails are dropped, while Unstop hackathons pass through. Cultural club hype is dropped, while actual events pass through. |
| **Execution Environment** | Cloud-hosted background runner | Laptop stays off; cloud worker polls every 5–10 minutes. |

---

## 5. System Architecture & Data Flow

```
+--------------------+        +---------------------+
| College Gmail      |        | Personal Gmail      |
+---------+----------+        +----------+----------+
          |                              |
          +--------------+---------------+
                         |
                         v (IMAP SSL / Gmail API)
          +------------------------------+
          | Python Cloud Daemon (Render) |
          | - Polls inboxes every 5 mins |
          | - Checks SQLite state DB     |
          +--------------+---------------+
                         |
                         v (Pass unread emails)
          +------------------------------+
          | Groq API (LLaMA 3.3 70B)    |
          | Evaluates:                   |
          | 1. Is actionable / urgent?   |
          | 2. Extracts dates, links,    |
          |    summary, action item      |
          +--------------+---------------+
                         |
                         | (If is_alert_worthy == true)
                         v
          +------------------------------+
          | CallMeBot WhatsApp Gateway   |
          | GET https://api.callmebot... |
          +--------------+---------------+
                         |
                         v
          +------------------------------+
          | Student WhatsApp Phone       |
          | [Option B Detailed Alert]    |
          +------------------------------+
```

---

## 6. What's Left to the Builder

The builder has full latitude on the following implementation specifics:

1. **Email Fetching Implementation:**
   - Default: Python `imaplib` / `aioimaplib` using Gmail App Passwords over SSL (simplest, no expiring refresh tokens).
   - Fallback: Google Workspace OAuth2 (if college administrator disables App Passwords).
2. **State & Deduplication Storage:**
   - Lightweight SQLite database or local JSON store recording `(account, message_id, processed_at, alerted)`.
   - Ensures no email is ever processed or alerted more than once across restarts.
3. **LLaMA Prompt & Structured Output:**
   - Enforce JSON output schema:
     ```json
     {
       "is_alert_worthy": true,
       "category": "Online Class" | "Assignment" | "Hackathon" | "Quiz" | "General Alert",
       "urgency": "high" | "medium" | "low",
       "summary": "1-2 sentence plain text summary",
       "deadline_or_time": "Exact date/time or null",
       "action_link": "Direct URL or null",
       "action_required": "Concrete next step"
     }
     ```
4. **WhatsApp Dispatcher:**
   - URL-encode formatted Option B template and issue HTTP GET/POST to CallMeBot API.
   - Include fallback rate limiting to prevent spamming WhatsApp if a flood of emails arrives simultaneously.
5. **Deployment Artifacts:**
   - Clean `requirements.txt`, `.env.example`, `Dockerfile`, and a simple deployment guide for free cloud hosting (Render / Railway / PythonAnywhere).
