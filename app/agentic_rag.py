"""
Agentic RAG backend for Touchpoint.ai (MVP).
- Stores product JSON documents in MongoDB ("products" collection)
- Stores embeddings in ChromaDB with persistent storage
- Offers search_rag(...) and agentic_answer(...) functions
"""

from typing import List, Dict, Any, Optional
from datetime import datetime
import os
import uuid
import numpy as np
from flask import current_app
from chromadb import HttpClient
import json
from llm_calls import llm_json_response, call_llm
from models import get_email


from dotenv import load_dotenv
load_dotenv()



# ----------------------------
# Config
# ----------------------------
OPENAI_KEY = os.getenv("OPENAI_API_KEY", None)
USE_OPENAI = bool(OPENAI_KEY)

# Initialize Chroma client
chroma_client = HttpClient(host="chroma", port=8000)

collection = chroma_client.get_or_create_collection("product_embeddings")



# ----------------------------
# Utilities
# ----------------------------
def _get_db():
    """Return Mongo DB handle"""
    return current_app.db

def _now():
    return datetime.utcnow()

def _normalize_vec(v: np.ndarray) -> np.ndarray:
    norm = np.linalg.norm(v)
    return v / norm if norm > 0 else v


# ----------------------------
# Chunking
# ----------------------------
def chunk_text(text: str, max_chars: int = 800, overlap: int = 100) -> List[str]:
    if not text:
        return []

    paragraphs = [p.strip() for p in text.split('\n') if p.strip()]
    chunks = []
    for p in paragraphs:
        if len(p) <= max_chars:
            chunks.append(p)
            continue
        start = 0
        while start < len(p):
            end = min(start + max_chars, len(p))
            chunks.append(p[start:end].strip())
            if end == len(p):
                break
            start = max(0, end - overlap)
    return chunks


# ----------------------------
# Embeddings
# ----------------------------
def embed_texts(texts: List[str]) -> List[List[float]]:
    if not texts:
        return []

    if USE_OPENAI:
        from openai import OpenAI
        client = OpenAI(api_key=OPENAI_KEY)
        model_name = os.getenv("OPENAI_EMBEDDING_MODEL", "text-embedding-3-small")

        embeddings = []
        BATCH = 20
        for i in range(0, len(texts), BATCH):
            batch = texts[i:i+BATCH]
            resp = client.embeddings.create(model=model_name, input=batch)
            for item in resp.data:
                embeddings.append(item.embedding)
        return embeddings

    raise RuntimeError("No embeddings backend available. Set OPENAI_API_KEY.")


# ----------------------------
# Ingest
# ----------------------------
def ingest_product_json(product_json: Dict[str, Any], ingest_to_embeddings: bool = True) -> str:
    """
    Save product JSON in MongoDB and embeddings in ChromaDB.
    """
    db = _get_db()
    products = db.products

    product_id = product_json.get("id") or f"prod-{uuid.uuid4().hex[:8]}"
    doc = {
        "id": product_id,
        "title": product_json.get("title", ""),
        "description": product_json.get("description", ""),
        "info": product_json.get("info", {}),
        "raw": product_json,
        "created_at": _now()
    }
    print(doc)
    # Upsert in Mongo
    products.update_one({"id": product_id}, {"$set": doc}, upsert=True)

    if ingest_to_embeddings:
        _ingest_product_embeddings(product_id, doc)

    return product_id


def _semantic_chunkify(product_id: str, product_doc: Dict[str, Any]) -> List[tuple[str, str]]:
    """
    Generate concise, semantically self-contained chunks for ingestion into RAG.
    Uses LLM to create information-dense sentences without fluff or redundancy.
    """
    structured_info = product_doc.get("info", {})
    base_chunks = []

    # Always include title
    if product_doc.get("title"):
        base_chunks.append(("title", product_doc["title"]))

    # Chunk description (if long, keep original chunking)
    if product_doc.get("description"):
        for c in chunk_text(product_doc["description"]):
            base_chunks.append(("description", c))

    # Include raw key-value pairs from info
    for k, v in structured_info.items():
        base_chunks.append((f"info.{k}", str(v)))

    # Prompt for semantic compression
    prompt = f"""
You are a knowledge distillation assistant preparing data for a Retrieval-Augmented Generation (RAG) system.

Task:
Convert the given product metadata into a list of short, semantically self-contained facts.
These facts will be embedded and retrieved independently, so they must include enough context to make sense without the rest of the document.

Guidelines:
- Each fact must be a single sentence.
- Each fact must explicitly mention both the product (by name or reference) and the attribute/value.
- Facts should be information-dense and avoid unnecessary words.
- Do not produce multiple paraphrases of the same fact.
- Do not include explanations, marketing language, or invented information.
- Use a neutral, factual style.
- Cover all provided metadata fields, but skip empty ones.

Input:
Product ID: {product_id}
Title: {product_doc.get("title")}
Description: {product_doc.get("description")}
Structured Info: {json.dumps(structured_info, indent=2)}

Output:
Return valid JSON in this format:
{{
  "semantic_facts": [
    "fact 1",
    "fact 2",
    "fact 3"
  ]
}}
"""

    try:
        response, _ = llm_json_response(prompt, response_format={"type": "json"})
        semantic_facts = response.get("semantic_facts", [])
        semantic_chunks = [(f"semantic_fact.{i}", fact) for i, fact in enumerate(semantic_facts)]
        return base_chunks + semantic_chunks
    except Exception as e:
        print(f"[WARN] Semantic chunkify failed: {e}")
        return base_chunks

def _ingest_product_embeddings(product_id: str, product_doc: Dict[str, Any], overwrite: bool = True):
    if overwrite:
        collection.delete(where={"product_id": product_id})

    chunks = _semantic_chunkify(product_id, product_doc)

    texts = [c[1] for c in chunks]
    vectors = embed_texts(texts)

    for (source, chunk_text_val), vec in zip(chunks, vectors):
        chunk_id = uuid.uuid4().hex
        collection.add(
            ids=[chunk_id],
            documents=[chunk_text_val],
            embeddings=[_normalize_vec(np.array(vec, dtype=float)).tolist()],
            metadatas=[{
                "product_id": product_id,
                "source": source,
                "chunk_text": chunk_text_val
            }]
        )


# ----------------------------
# Search
# ----------------------------
def search_rag(query: str, top_k: int = 5) -> List[Dict[str, Any]]:
    q_vec = embed_texts([query])[0]
    q_vec = _normalize_vec(np.array(q_vec, dtype=float)).tolist()

    results = collection.query(
        query_embeddings=[q_vec],
        n_results=top_k
    )

    hits = []
    for ids, docs, metas, scores in zip(
        results["ids"][0], results["documents"][0], results["metadatas"][0], results["distances"][0]
    ):
        hits.append({
            "product_id": metas.get("product_id"),
            "chunk_id": ids,
            "source": metas.get("source"),
            "chunk_text": docs,
            "score": 1 - scores  # Chroma returns distance → convert to similarity
        })
    return hits


# ----------------------------
# Agentic Answer
# ----------------------------
def decompose_question(query: str) -> List[Dict[str, str]]:
    """
    Decompose a user query into atomic questions with HyDE pseudo answers.
    Always returns a list of dicts with {"question": str, "pseudo_answer": str}.
    """

    prompt = f"""
    You are an assistant that extracts questions for RAG searches.
    Input: an email or user query.
    {query}
    Task:
    - Break questions in it down into single sentence questions.
    - For each question, create a short pseudo-answer (HyDE).
    - Return JSON list with objects like:
      {{"question": "...", "pseudo_answer": "..."}}.
    """

    raw, _ = llm_json_response(prompt)
    print("This is the raw:", raw)

    try:
        needs = json.loads(raw)

        # Case 1: wrapped in {"information_needs": [...]}
        if isinstance(needs, dict) and "information_needs" in needs:
            needs = needs["information_needs"]

        # Case 2: wrapped in {"questions": [...]}
        elif isinstance(needs, dict) and "questions" in needs:
            needs = needs["questions"]

        result = []
        if isinstance(needs, list):
            for n in needs:
                if isinstance(n, dict):
                    result.append({
                        "question": n.get("question", "").strip(),
                        "pseudo_answer": n.get("pseudo_answer", "").strip()
                    })
                elif isinstance(n, str):
                    # fallback if model returned list of strings
                    result.append({"question": n.strip(), "pseudo_answer": ""})

        if not result:
            # fallback: at least original query
            result = [{"question": query, "pseudo_answer": ""}]
        return result

    except Exception as e:
        print("⚠️ parse error in decompose_question:", e, raw)
        return [{"question": query, "pseudo_answer": ""}]


def rag_search_combined(question: str, pseudo_answer: str, top_k: int = 5):
    """
    Run RAG search for both the original question and pseudo-answer.
    Merge and deduplicate results.
    """
    hits_q = search_rag(question, top_k=top_k)
    hits_p = search_rag(pseudo_answer, top_k=top_k) if pseudo_answer else []
    all_hits = hits_q + hits_p

    # Deduplicate by chunk_id or product_id
    seen = set()
    merged = []
    for h in all_hits:
        key = (h["product_id"], h["chunk_id"])
        if key not in seen:
            merged.append(h)
            seen.add(key)

    # Sort by score
    merged = sorted(merged, key=lambda x: x["score"], reverse=True)
    return merged[:top_k]

def evaluate_answer(sub_question: str, context: str) -> Optional[str]:
    """
    Checks if the sub-question can be answered from the given context.
    Returns answer string if found, or None if not present.
    """
    if not call_llm:
        return None

    prompt = f"""
You are a strict evaluation agent.

Sub-question: "{sub_question}"

Context:
{context}

Instructions:
- If the context contains enough info to answer, reply ONLY in this format:
  ANSWER: <your short answer here>
- If the info is missing, reply EXACTLY with:
  NO INFO IN CONTEXT
"""
    ans_text, _ = call_llm(prompt)
    ans_text = ans_text.strip()

    if ans_text.upper().startswith("NO INFO IN CONTEXT"):
        return None
    if ans_text.upper().startswith("ANSWER:"):
        return ans_text[len("ANSWER:"):].strip()
    return None


def agentic_answer(query: str, top_k: int = 5) -> Dict[str, Any]:
    """
    New agentic answer:
    1. Decompose into sub-questions with pseudo answers.
    2. For each sub-question, search with both question + pseudo-answer.
    3. LLM generates final Q/A/Source.
    """
    needs = decompose_question(query)
    print("These are the needs:")
    print(needs)
    results = []

    for item in needs:
        q = item["question"]
        pseudo = item["pseudo_answer"]
        hits = rag_search_combined(q, pseudo, top_k=top_k)

        # Build context
        context = "\n\n".join(
            [f"[Source {i+1}] {h['chunk_text']}" for i, h in enumerate(hits)]
        )

        # Ask LLM for formatted answer
        prompt = f"""
        You are a helpful assistant. Use the given context to answer.

        Question: {q}

        Context:
        {context}

        Instructions:
        - Write the answer as short factual text.
        - If no info is available, say "No information found."
        - Use this format exactly:

        Question: {q}
        Answer: <your answer>
        """
        ans_text, _ = call_llm(prompt)
        results.append(ans_text.strip())

    final_output = "\n\n".join(results)
    return final_output
