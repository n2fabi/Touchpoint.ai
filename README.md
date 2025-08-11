# Touchpoint.ai

A lightweight CRM leveraging AI to stay in contact with customers and create customer‑centric introductions to new products

# Lightweight CRM with LLM Support — MVP

**Summary:** This repository contains a minimal Flask web app as an MVP for a lightweight CRM with LLM support. The targeted product-driven scenario is: new product → filter relevant customers → generate a personalized email draft (or bullet points) → mark customer as “contacted” → send a reminder after 3 working days if no reply.

---

## Repository contents

* `app/` — Flask application (Blueprints: customers, products, interactions, llm, email, scheduler)
* `scripts/` — helper scripts (e.g. `seed_data.py`)
* `requirements.txt` — Python dependencies
* `Dockerfile` — (optional) container build
* `README.md` — this file

---

## MVP features (scope for 2 weeks / 40 h)

* Customers CRUD (CSV/JSON import possible)
* Create products (description + markers)
* LLM pipeline: marker extraction + matching + email draft / bullet points
* Review UI for email draft + send button (sets `last_contacted`)
* Reminder job: checks 3 **working days** after `last_contacted` and sends/creates a reminder if no `replied` interaction exists
* SMTP-based sending (mailbox integration later)

---

## Recommended tech stack

* Backend: **Flask**
* DB: **MongoDB** (Atlas or local)
* DB driver: **PyMongo** / Flask-PyMongo
* LLM: OpenAI (or another provider API)
* Background / scheduler: **APScheduler** (MVP), later Celery + Redis
* Email: SMTP (`smtplib`) for MVP; Gmail IMAP/OAuth later

---

## Prerequisites

* Python 3.10+ or 3.11
* MongoDB (local or Atlas)
* OpenAI API key (or another LLM key)

---

## Environment variables (example)

```bash
# Flask
FLASK_APP=app
FLASK_ENV=development

# MongoDB
MONGO_URI=mongodb://localhost:27017/crm_db

# LLM / OpenAI
OPENAI_API_KEY=sk-...

# SMTP (optional) — only for sending in MVP
SMTP_HOST=smtp.example.com
SMTP_PORT=587
SMTP_USERNAME=your@address
SMTP_PASSWORD=secret

# Other (deployment-specific)
SECRET_KEY=changeme
```

---

## Installation & start (local)

```bash
git clone <repo-url>
cd <repo>
python -m venv .venv
source .venv/bin/activate  # Linux/Mac
.venv\\Scripts\\activate     # Windows
pip install -r requirements.txt

# Optional: seed the DB
python scripts/seed_data.py

# Start
flask run --host=0.0.0.0 --port=5000
```

---

## Important endpoints (overview)

> The implementation is organized in the `app/` folder using Blueprints.

* `GET /customers` — list customers
* `POST /customers` — create a customer (JSON)
* `GET /customers/<id>` — customer details + interactions
* `GET /products` — list products
* `POST /products` — create a product (description, markers)
* `POST /products/<id>/match` — LLM: find relevant customers & generate draft
* `POST /interactions` — store a new interaction (email/call)
* `POST /send_email` — send an email (SMTP) and set `last_contacted`

---

## Data model (example documents)

**customers**

```json
{
  "_id": "ObjectId",
  "name": "Acme GmbH",
  "email": "kontakt@acme.de",
  "tags": ["fintech", "DACH"],
  "notes": ["2025-07-01: Messekontakt"],
  "meta": {"timezone":"Europe/Berlin"},
  "last_contacted": null
}
```

**products**

```json
{
  "_id": "ObjectId",
  "title": "Produkt X",
  "description": "Long description...",
  "markers": ["AI","Automation"],
  "created_at": "ISODate"
}
```

**interactions**

```json
{
  "_id": "ObjectId",
  "customer_id": "ObjectId",
  "type": "email",
  "direction": "outgoing",
  "content": "...",
  "timestamp": "ISODate",
  "status": "sent|replied|no_reply"
}
```

---

## Architecture & notes

* **LLM pipeline:** Keep input tokens small: only include the last 3 interactions + tags + short customer info in the prompt. Use `temperature=0.2-0.6` for controlled creativity.
* **Matching:** Start with keyword/tag filters (indexed in Mongo); later move to semantic matching with embeddings + vector DB.
* **Reminder:** APScheduler checks DB entries regularly; the job worker should be idempotent.

---

## Development organization (recommendation)

Use an issue board with the following epics/issues for the sprint:

1. Repo + basic skeleton
2. DB + seed script
3. Customers CRUD
4. Products CRUD
5. LLM integration (prompts + tests)
6. Matching & draft UI
7. Email sending + mark contacted
8. Scheduler / reminder
9. Docs + deploy

---

## ToDo / roadmap (after MVP)

* Mailbox integration (IMAP/Gmail OAuth) for automatic capture of replies
* Embeddings + vector DB for semantic matching
* Multi-user, auth, roles
* Asynchronous workers (Celery) + scalable deployment
* Tests (unit + e2e)

---
