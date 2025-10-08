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

# Touchpoint.ai — RAG

## Index into RAG (what happens)

* **Chunking:** keep description paragraphs; convert `info` facts into short, deterministic sentences (e.g., “Touchpoint.ai price is 49 €/seat.”).
* **Metadata:** only scalar fields (e.g., `product_id`, `source`, `type`, `synonyms` as a single comma-separated string).
* **Storage:** embeddings in **Chroma**; text+meta mirror in Mongo (`product_chunks`) for inspection/editing.

## Agentic RAG (answering)

1. **Decompose** the user query into atomic sub-questions.
2. **HyDE**: create a brief pseudo-answer per sub-question.
3. **Combined search**: query vectors with both question and HyDE; apply **MMR** to diversify hits.
4. **Constrained answer**: respond strictly from retrieved context; otherwise return “No information found.”

## Authoring Best Practices

* **Description:** short, factual, neutral paragraphs; avoid fluff and marketing.
* **Facts (`info`):** flat keys and concise values; prefer stable, numeric/text fields.
* **Synonyms:** list all aliases in one comma-separated string (not an array).
* **Images:** optional; stored but not embedded as vectors.

## Maintenance

* **Edit & Re-index** products after any change to description/facts/synonyms.
* **Reset Vector DB** to clear Chroma; re-index afterward.
* **Delete Product** removes entries from Mongo (`products`, `product_chunks`) and Chroma.

## Common Pitfalls

* **Non-scalar metadata** (lists/dicts) in Chroma → flatten to strings first.
* **Empty/invalid JSON** → ingestion fails silently or with errors.
* **Forgetting to re-index** after edits → stale or missing retrieval results.

## Quick Checklist

* [ ] Clean, factual description
* [ ] Compact, flat `info` facts
* [ ] Synonyms flattened to a single string
* [ ] Indexed into RAG and verified via a test question
