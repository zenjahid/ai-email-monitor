# 📬 AI Email Reading Agent

An intelligent email monitoring system that reads incoming emails, uses AI to determine importance, and displays important notifications on a live dashboard.

**Built for TQTech — Software Engineer 2 (AI Automation Engineer) Assignment**

> **🔗 Live Demo:** [`https://ai-email-monitor.onrender.com`](https://ai-email-monitor.onrender.com) 
---

## ✨ Features

- **📧 Multi-source email reading** — Mock data (built-in) or IMAP (Gmail/Outlook/any)
- **🤖 AI-powered classification** — Rule-based (built-in), OpenAI, OpenAI-compatible (OpenRouter, Groq, Together AI), or local LLM (Ollama)
- **📊 Live dashboard** — Auto-refreshing notification display with priority badges, categories, and AI reasoning
- **⚙️ Configurable via UI** — Change email source and AI provider from the settings page without restarting
- **🔒 Duplicate prevention** — Processed emails are stored in SQLite and never shown twice
- **🐳 Docker-ready** — Single `docker compose up --build` to run the full system

---

## 🏗️ Architecture

```
┌───────────────────────────────────────────────────────────────┐
│                        Flask Application                       │
│  ┌──────────────┐  ┌──────────────┐  ┌─────────────────────┐  │
│  │ Email Reader  │─▶│  Classifier  │─▶│   Dashboard (Web)   │  │
│  │ (Mock/IMAP)   │  │ (API + Rules)│  │ Notifications +     │  │
│  │               │  │              │  │ Settings Page       │  │
│  └──────┬───────┘  └──────┬───────┘  └─────────┬───────────┘  │
│         │                 │                     │              │
│         ▼                 ▼                     ▼              │
│  ┌─────────────────────────────────────────────────────────┐  │
│  │                    SQLite Database                       │  │
│  │  (processed_emails + settings key-value store)           │  │
│  └─────────────────────────────────────────────────────────┘  │
│                                                               │
│  ┌─────────────────────────────────────────────────────────┐  │
│  │           Background Scheduler Thread                    │  │
│  │  Every N seconds: fetch → classify → store → repeat     │  │
│  └─────────────────────────────────────────────────────────┘  │
└───────────────────────────────────────────────────────────────┘
```

### Classifier Decision Flow

```
New Email
    │
    ├─▶ Provider = rule_based ─────────────────▶ Rule-Based Classifier
    │
    ├─▶ Provider = openai ───▶ OpenAI API ──┐
    ├─▶ Provider = openai_compat ──▶ OpenRouter / Groq / etc. ──┤
    └─▶ Provider = local ──────▶ Ollama ────┘
                                              │
                                     ┌────────┴────────┐
                                     │ Success?         │
                                     ├─ Yes ──▶ Return  │
                                     └─ No ───▶ Fallback│
                                                 │
                                                 ▼
                                        Rule-Based Classifier
                                              │
                                              ▼
                                     Store in SQLite
```

---

## 🚀 Quick Start

### Option 1: Docker (Recommended)

```bash
# Clone the repository
git clone https://github.com/zenjahid/ai-mail-monitor ai-email-monitor
cd ai-email-monitor

# Copy environment template (edit if needed)
cp .env.example .env

# Build and start
docker compose up --build
```

Open **http://localhost:5000** in your browser.

### Option 2: Local Development

```bash
# 1. Clone and enter the project
git clone https://github.com/zenjahid/ai-mail-monitor ai-email-monitor
cd ai-email-monitor

# 2. Create virtual environment
python -m venv venv

# 3. Activate it
# Windows:
venv\Scripts\activate
# macOS/Linux:
# source venv/bin/activate

# 4. Install dependencies
pip install -r requirements.txt

# 5. Copy environment template
cp .env.example .env

# 6. Run the application
python main.py
```

Open **http://localhost:5000** in your browser.

---

## 📖 Usage

### Dashboard

The main dashboard shows all emails the AI has flagged as important. Each notification displays:

| Field        | Description                                               |
| ------------ | --------------------------------------------------------- |
| **Priority** | 🔴 HIGH / 🟡 MEDIUM / 🟢 LOW (color-coded badge)          |
| **Sender**   | Email address of the sender                               |
| **Subject**  | Email subject line                                        |
| **Category** | Classification category (e.g. PAYMENT_ISSUE, SERVER_DOWN) |
| **Reason**   | AI's justification for flagging it                        |
| **Time**     | When the email was received (relative time)               |

The dashboard auto-refreshes every 10 seconds. Stats at the top show total processed emails, important count, and ignored count.

### Settings Page

Navigate to **⚙️ Settings** to configure:

**Email Source:**

- **Mock Data** — Uses the built-in `data/mock_emails.json` dataset. Works immediately without any credentials. You can edit the data inline from the settings page.
- **IMAP** — Connect to any IMAP server (Gmail, Outlook, self-hosted). For Gmail, use an [App Password](https://support.google.com/accounts/answer/185833).

**AI Provider:**

- **Rule-based** — Keyword/pattern matching. No API key needed. Works offline.
- **OpenAI API** — Uses the official OpenAI API. Requires an API key.
- **OpenAI-Compatible** — Works with OpenRouter, Groq, Together AI, or any OpenAI-compatible endpoint.
- **Local LLM (Ollama)** — Connect to a local Ollama instance (e.g., `http://localhost:11434`).

Changes take effect on the next poll cycle.

---

## 🤖 How the AI Classifier Works

### Rule-Based Classifier (Fallback)

The rule-based classifier uses **regular expression pattern matching** against the email subject and body. It categorises emails based on keyword presence:

| Priority         | Keywords                                                                                        | Category                                                |
| ---------------- | ----------------------------------------------------------------------------------------------- | ------------------------------------------------------- |
| 🔴 HIGH          | `server down`, `outage`, `payment failed`, `ddos`, `urgent`, `asap`, `unauthorized transaction` | SERVER_DOWN, PAYMENT_ISSUE, SECURITY_ALERT, FRAUD_ALERT |
| 🟡 MEDIUM        | `complaint`, `unhappy`, `discrepancy`, `budget alert`, `pipeline failed`                        | CLIENT_COMPLAINT, BUDGET_ALERT, CI_FAILURE              |
| 🟢 LOW (ignored) | `newsletter`, `unsubscribe`, `flash sale`, `won.*million`, `order shipped`                      | NEWSLETTER, SPAM, AUTOMATED, PROMOTION                  |

If no rule matches, the email is classified as `not important` with a default `GENERAL` category.

### API Classifier (OpenAI / OpenAI-Compatible / Ollama)

When an API provider is configured, the system:

1. Sends the email subject and body to the LLM with a **system prompt** instructing it to return JSON
2. The LLM responds with: `{"important": bool, "priority": "HIGH|MEDIUM|LOW", "category": "...", "reason": "..."}`
3. If the API call succeeds, the structured result is used
4. If the API call **fails** (timeout, auth error, rate limit), the system **falls back** to the rule-based classifier

The system prompt is designed to produce consistent, structured output. Example:

```
System: You are an email classification assistant...
User: Subject: URGENT: Production server is down
       Body: Our main server has been down for 30 minutes...
Response: {"important": true, "priority": "HIGH", "category": "SERVER_DOWN", "reason": "Urgent server outage reported"}
```

---

## 🧪 Mock Email Dataset

The built-in mock dataset ([`data/mock_emails.json`](data/mock_emails.json)) contains 20 emails with a realistic mix:

| Type                 | Count | Examples                                                        |
| -------------------- | ----- | --------------------------------------------------------------- |
| 🔴 HIGH importance   | 7     | Server down, payment failure, DDoS attack, fraud alert          |
| 🟡 MEDIUM importance | 2     | Client complaint, budget alert                                  |
| 🟢 LOW (ignored)     | 11    | Newsletters, spam, shipping confirmations, social notifications |

The mock reader cycles through emails in batches of 5, wrapping around when exhausted, so the system continuously processes "new" emails.

### Managing Mock Emails from the Dashboard

You can add, edit, or delete mock emails directly from the **Settings** page without needing a text editor:

**1. Delete individual emails** — In the "Mock Emails" list, click the **×** button next to any email to remove it. This calls the [`POST /api/mock-data/delete`](app/dashboard/routes.py:192) API.

**2. Edit the full dataset** — In the "Raw JSON Data" textarea, you can:

- **Add** new emails by pasting in a JSON object with `id`, `from`, `subject`, `body`, and `received_at` fields
- **Modify** existing emails by editing their fields
- **Remove** emails by deleting their JSON objects
- **Bulk replace** the entire array

Then click **"Save Mock Data"** to persist. This calls the [`POST /api/mock-data`](app/dashboard/routes.py:234) API which validates the JSON, writes to [`data/mock_emails.json`](data/mock_emails.json), and reloads the reader so the next poll cycle uses the updated data.

**3. Reset processed state** — Clicking **"Clear all"** in the Notifications dropdown calls [`POST /api/mock-data/clear`](app/dashboard/routes.py:266) which deletes all processed email records from the database, allowing previously-seen emails to show up as new again.

> **Tip:** Switch to **Mock Data** source on the Settings page whenever you want to test with custom email scenarios. Changes take effect on the next poll cycle (default: every 120 seconds) or immediately if you restart the app.

---

## 🐳 Docker Setup

### Prerequisites

- Docker Engine 20.10+
- Docker Compose 2.x

### Build & Run

```bash
docker compose up --build
```

### Environment Variables

Configure via `.env` file or `docker-compose.yml` environment section. See [`.env.example`](.env.example) for all options.

### Volumes

- `./data:/data` — Persists SQLite database and any credential files
- `./.env:/app/.env:ro` — Mounts environment configuration (read-only)

---

## ⚙️ Configuration Reference

| Variable                 | Default                             | Description                                                   |
| ------------------------ | ----------------------------------- | ------------------------------------------------------------- |
| `EMAIL_SOURCE`           | `mock`                              | Email source: `mock` or `imap`                                |
| `IMAP_HOST`              | `imap.gmail.com`                    | IMAP server hostname                                          |
| `IMAP_PORT`              | `993`                               | IMAP server port                                              |
| `IMAP_USER`              | —                                   | IMAP username                                                 |
| `IMAP_PASS`              | —                                   | IMAP password or app password                                 |
| `PROVIDER`               | `rule_based`                        | AI provider: `openai`, `openai_compat`, `local`, `rule_based` |
| `OPENAI_API_KEY`         | —                                   | OpenAI API key                                                |
| `OPENAI_MODEL`           | `gpt-4o-mini`                       | OpenAI model name                                             |
| `OPENAI_COMPAT_BASE_URL` | `https://openrouter.ai/api/v1`      | Base URL for OpenAI-compatible API                            |
| `OPENAI_COMPAT_API_KEY`  | —                                   | API key for OpenAI-compatible provider                        |
| `OPENAI_COMPAT_MODEL`    | `anthropic/claude-3-haiku`          | Model name for OpenAI-compatible provider                     |
| `OLLAMA_BASE_URL`        | `http://host.docker.internal:11434` | Ollama server URL                                             |
| `OLLAMA_MODEL`           | `llama3.2`                          | Ollama model name                                             |
| `POLL_INTERVAL`          | `120`                               | Seconds between email polls                                   |
| `DATABASE_PATH`          | `data/emails.db`                    | Path to SQLite database file                                  |

---

## 📁 Project Structure

```
ai-email-monitor/
├── app/
│   ├── email_reader/          # Email fetching (mock, IMAP)
│   │   ├── base.py            # Abstract EmailReader interface
│   │   ├── mock.py            # JSON-based mock reader
│   │   └── imap.py            # IMAP SSL reader
│   ├── classifier/            # AI classification engine
│   │   ├── base.py            # Abstract Classifier + ClassificationResult
│   │   ├── rule_based.py      # Keyword-based fallback
│   │   └── api.py             # OpenAI / OpenAI-compat / Ollama
│   ├── dashboard/             # Flask web UI
│   │   ├── routes.py          # API + page routes
│   │   └── templates/         # Jinja2 HTML templates
│   ├── models/                # Data layer
│   │   ├── database.py        # SQLite init + connection management
│   │   └── repository.py      # CRUD for emails + settings
│   └── scheduler.py           # Background polling loop
├── data/
│   ├── mock_emails.json       # 20 built-in test emails
│   └── emails.db              # SQLite database (auto-created)
├── config.py                  # Environment-based configuration
├── main.py                    # Application entry point
├── requirements.txt
├── Dockerfile
├── docker-compose.yml
├── .env.example               # Configuration template (no secrets)
├── .gitignore
├── README.md                  # This file
└── plans/
    └── implementation-plan.md # Original project plan
```

---

## 🧑‍💻 Development

### Adding New Mock Emails

Edit `data/mock_emails.json` and add entries following this structure:

```json
{
  "id": "msg-021",
  "from": "sender@example.com",
  "subject": "Email subject line",
  "body": "Email body content...",
  "received_at": "2026-06-10T12:00:00Z"
}
```

### Adding New Classification Rules

Edit `app/classifier/rule_based.py` and add entries to the `RULES` list:

```python
(
    re.compile(r"\b(your_keyword_here)\b", re.IGNORECASE),
    ("label", "HIGH", "CATEGORY", "Reason for classification"),
),
```

---

## 📋 Grading Criteria Coverage

| Criterion                      | Marks  | How It's Met                                                                       |
| ------------------------------ | ------ | ---------------------------------------------------------------------------------- |
| AI importance detection        | **40** | Rule-based classifier + API classifier (OpenAI/OpenAI-compat/Ollama) with fallback |
| Dashboard notification display | **10** | Flask dashboard with priority badges, categories, AI reasoning, live auto-refresh  |
| Email reading / mock data      | **20** | Mock JSON dataset (mandatory) + IMAP reader                                        |
| Duplicate prevention           | **10** | SQLite `processed_emails` table with `email_id` primary key, `INSERT OR IGNORE`    |
| Docker setup                   | **10** | `Dockerfile` + `docker-compose.yml` with volume mounts                             |
| README & documentation         | **5**  | Full setup guide, architecture diagram, AI explanation, configuration reference    |
| Code quality                   | **5**  | Type hints, docstrings, modular design, consistent naming, error handling          |

---

## ⚠️ Limitations

- The **rule-based classifier** is limited to keyword matching and may miss nuanced importance signals. For production use, configure an API-based provider.
- The **mock reader** cycles through the same dataset repeatedly. Real email sources provide genuine new emails.
- The dashboard auto-refreshes but does not support **push notifications** (WebSocket). This is a static polling implementation.
- SQLite is suitable for single-user/small-scale use. For multi-user, consider PostgreSQL.
