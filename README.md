# Touchpoint.ai

Lightweight, AI-assisted CRM for **email replies**, **follow-up reminders**, **chat**, and **product knowledge via RAG** (Retrieval-Augmented Generation).

---

## Overview

- **Email Assistant**: Generate, rewrite, and edit HTML emails (TinyMCE). Optional **RAG** toggle to ground answers in product knowledge.
- **Reminders & Threads**: Auto-group conversations per contact and flag **needs reply** / **follow up**.
- **RAG Knowledge Base**: Upload/edit product docs (free text + compact JSON facts), **index into ChromaDB**, reset vector DB, delete products.
- **Agentic RAG**: Question decomposition + **HyDE** pseudo answers → combined search (question + HyDE) with **MMR** → concise, source-grounded replies.

---

## Core Features

- **Email**
  - Reply generation with tone controls (friendly/professional/correct & rewrite)
  - “New Email”: generate from prompt or compose manually (HTML)
  - CC/BCC toggle, attachments, send draft

- **RAG KB**
  - Product upload (JSON): `{ title, description, info, synonyms, images }`
  - Edit product (title/description/JSON facts/synonyms/images)
  - **Index into RAG** (OpenAI embeddings + ChromaDB)
  - **Reset Vector DB** and **Delete Product** (Mongo + RAG)

- **Agentic RAG (QA)**
  - Decompose → HyDE → Dual search (question+HyDE) → **MMR** diversify → answer from context
  - “No information found.” when not grounded

---

## Tech Stack

- **Flask** (Python 3.11), **MongoDB**, **ChromaDB (HTTP)**
- **OpenAI** embeddings (`text-embedding-3-small`)
- **TinyMCE** HTML editor
- Gmail (read/label); app send for outgoing mail

---

## Setup

### Environment (minimal)
bash
FLASK_APP=app
FLASK_ENV=development
SECRET_KEY=changeme

MONGO_URI=mongodb://localhost:27017/touchpoint

OPENAI_API_KEY=sk-...
OPENAI_EMBEDDING_MODEL=text-embedding-3-small

CHROMA_HOST=chroma   # or localhost
CHROMA_PORT=8000

USER_EMAIL=you@example.com
Install & Run
bash
Code kopieren
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

# Start Chroma (example)
docker run -p 8000:8000 chromadb/chroma:latest

# Run the app
flask run --host=0.0.0.0 --port=5000
Using the App
Products (RAG)
Upload JSON or paste (includes title, description, info, optional synonyms, images).

Edit: adjust description & facts.

Index into RAG: creates embeddings + Mongo chunk mirror.

Reset Vector DB: clears Chroma collection.

Delete: removes product from Mongo + RAG.

Tip: Chroma metadata must be scalar. Store synonyms as a comma-separated string; the app normalizes this for metadata.

Emails
Inbox: grouped by day/week; red dot for unread.

Detail: “Answer this E-Mail” → optional Use Product Knowledge (RAG) → HTML preview → edit in TinyMCE → tone controls → send.

New Email: generate from prompt or compose manually (HTML).

RAG Ingestion (Best Practices)
Description: natural paragraphs; keep factual and concise.

JSON facts: compact keys/values (e.g., price: "1.559 €", config.tom1: "08 x 07").

Synonyms: put variations (brand/model/aliases) as a comma-separated list (stored as metadata string).

The pipeline produces short deterministic fact sentences (e.g., Touchpoint.ai price is 49 €/seat.) and embeds them with the description.

Agentic RAG Flow
Decompose user question into atomic sub-questions.

HyDE: generate pseudo answers for each sub-question.

Combined Search: query with question and HyDE; MMR to diversify.

Answer strictly from retrieved context; otherwise: “No information found.”

Maintenance
Reset Vector DB: one-click collection drop & recreate.

Delete Product: remove from Mongo (products, product_chunks) and Chroma.

Roadmap (short)
Multi-user auth/roles

UI to review/edit RAG chunks inline

Async ingestion (Celery/Redis) & batch validators

Retrieval/answer evaluation dashboards

makefile
Code kopieren

::contentReference[oaicite:0]{index=0}
