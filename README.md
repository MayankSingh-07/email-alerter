# 📬 AI Email Classifier & WhatsApp Alerter

> Continuous 24/7 background service that monitors your **College** and **Personal** Gmail accounts, classifies incoming emails using ultra-fast LLMs (**Groq / Llama 3.3 70B**), and instantly notifies you on **WhatsApp** via CallMeBot whenever urgent, actionable, or priority messages arrive.

---

## 🌟 Key Features

- **Dual-Account IMAP Monitoring**: Independently polls college and personal Gmail accounts via SSL.
- **Intelligent LLM Triage**: Uses Groq (`llama-3.3-70b-versatile`) to classify priority into:
  - `P1_URGENT` / `P2_ACTION_REQUIRED`: Triggers instant WhatsApp notification with a concise summary and deadline.
  - `P3_FYI` / `P4_NOISE`: Logged and recorded in SQLite database, avoiding notification spam.
- **Idempotency & Deduplication**: SQLite-backed state tracking ensures you are never alerted twice for the same message ID.
- **Graceful Lifecycle Management**: Clean SIGINT/SIGTERM handling for seamless container updates and shutdown.
- **Production-Ready & 100% Free**: Operates entirely within free-tier limits of Gmail IMAP, Groq, CallMeBot, and Render/Docker.

---

## 🏗️ Architecture & Flow

```
┌────────────────────────┐      ┌────────────────────────┐
│  College Gmail (IMAP)  │      │  Personal Gmail (IMAP) │
└───────────┬────────────┘      └───────────┬────────────┘
            │                               │
            └───────────────┬───────────────┘
                            ▼
              ┌───────────────────────────┐
              │    EmailMonitorService    │
              │  (Every 300s by default)  │
              └─────────────┬─────────────┘
                            ▼
              ┌───────────────────────────┐
              │    SQLite Deduplication   │ ──(Already seen)──► Ignore
              └─────────────┬─────────────┘
                            │ (New unread)
                            ▼
              ┌───────────────────────────┐
              │ Groq LLM (Llama 3.3 70B)  │
              │ JSON Structured Decision  │
              └─────────────┬─────────────┘
                            │
            ┌───────────────┴───────────────┐
            │                               │
   [P1_URGENT / P2_ACTION]            [P3_FYI / P4_NOISE]
            │                               │
            ▼                               ▼
┌──────────────────────────┐      ┌───────────────────┐
│ CallMeBot WhatsApp API   │      │ Persist to SQLite │
│ Instant Push to Phone    │      │ (No Notification) │
└──────────────────────────┘      └───────────────────┘
```

---

## 🔑 Prerequisites & API Setup

### 1. Gmail App Passwords (College & Personal)
Standard Gmail passwords will not work with IMAP when 2-Factor Authentication (2FA) is enabled. You must generate a dedicated **16-character App Password**:
1. Log into your Google Account: [https://myaccount.google.com/security](https://myaccount.google.com/security)
2. Ensure **2-Step Verification** is turned ON.
3. In the search bar at the top, type **"App passwords"** and click on it.
4. Enter an app name (e.g., `Email Alerter`) and click **Create**.
5. Copy the generated 16-character password (e.g. `abcd efgh ijkl mnop`).
6. Repeat this process for both your college and personal Gmail accounts.

### 2. Groq Cloud API Key
1. Sign up / Log in to [Groq Console](https://console.groq.com).
2. Navigate to **API Keys** in the left sidebar.
3. Click **Create API Key**, name it (e.g., `email-alerter`), and copy the `gsk_...` key.
4. Free tier includes generous rate limits with fast inference on `llama-3.3-70b-versatile`.

### 3. CallMeBot WhatsApp Gateway
CallMeBot provides a free gateway to send WhatsApp messages to your own number via a simple HTTP GET API:
1. Save the CallMeBot phone number to your phone contacts:
   - Phone: `+34 644 51 95 23` (or check [CallMeBot Instructions](https://www.callmebot.com/blog/free-api-whatsapp-messages/))
2. Open WhatsApp and send the following message to that contact:
   ```text
   I allow callmebot to send me messages
   ```
3. CallMeBot will reply within a few seconds with:
   ```text
   CallMeBot API Activated. Your APIKey is: 123456
   ```
4. Note your phone number in full international format (e.g., `+919876543210`) and the API key.

---

## ⚙️ Environment Configuration

Copy `.env.example` to `.env` and fill in your credentials:

```bash
cp .env.example .env
```

Edit `.env`:
```ini
# Gmail Credentials
COLLEGE_GMAIL_USER=your_college_email@college.edu
COLLEGE_GMAIL_PASSWORD=abcdefghijklmnop
PERSONAL_GMAIL_USER=your_personal_email@gmail.com
PERSONAL_GMAIL_PASSWORD=abcdefghijklmnop

# Groq Cloud
GROQ_API_KEY=gsk_your_groq_api_key_here

# CallMeBot WhatsApp
CALLMEBOT_PHONE=+919876543210
CALLMEBOT_API_KEY=123456

# Configuration
POLL_INTERVAL_SECONDS=300
DB_PATH=data/alerts.db
```

---

## 🚀 Running Locally

### Option 1: Native Virtual Environment
```bash
# 1. Create and activate virtual environment
python3 -m venv .venv
source .venv/bin/activate

# 2. Install dependencies
pip install -r requirements.txt

# 3. Initial Baseline Run (Recommended for first run)
# Marks existing unread emails as processed without sending WhatsApp alerts
python main.py --baseline

# 4. Run a single poll cycle to verify alerts
python main.py --once -v

# 5. Start continuous daemon
python main.py --daemon
```

### Option 2: Docker
```bash
# 1. Build Docker image
docker build -t email-classifier-alerter .

# 2. Run with volume mount for persistent SQLite database
docker run -d \
  --name email-alerter \
  --restart unless-stopped \
  --env-file .env \
  -v $(pwd)/data:/app/data \
  email-classifier-alerter
```

---

## ☁️ 1-Click Cloud Deployment (Render Free Tier)

Render provides free background worker services using blueprint deployment (`render.yaml`).

### Deployment Steps:
1. Push this repository to GitHub or GitLab.
2. Log into [Render Dashboard](https://dashboard.render.com/).
3. Click **New +** and select **Blueprint**.
4. Connect your repository. Render will automatically detect `render.yaml`.
5. In the environment variable setup step, fill in the non-synced secret variables:
   - `COLLEGE_GMAIL_USER`
   - `COLLEGE_GMAIL_PASSWORD`
   - `PERSONAL_GMAIL_USER`
   - `PERSONAL_GMAIL_PASSWORD`
   - `GROQ_API_KEY`
   - `CALLMEBOT_PHONE`
   - `CALLMEBOT_API_KEY`
6. Click **Apply Blueprint**. Render will build and spin up the worker daemon running 24/7.

---

## 🧪 Testing & Verification

Run the full automated test suite:

```bash
# Run all unit, integration, and smoke tests
pytest tests/ -v
```

CLI options overview:
```text
python main.py --help
options:
  -h, --help    show this help message and exit
  --once        Run a single polling cycle and exit
  --baseline    Initial sync: mark existing unread emails as processed without dispatching WhatsApp alerts
  --daemon      Run continuous polling loop (default mode)
  -v, --verbose Enable debug logging output
```

---

## 🔒 Security Best Practices

- **Never commit `.env` or database files**: Protected by `.gitignore`.
- **Minimal Permissions**: The Docker image runs as an unprivileged non-root user (`appuser`).
- **Read-Only Email Operations**: IMAP connections only fetch message headers and bodies without deleting or altering your emails.
