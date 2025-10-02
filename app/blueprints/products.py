# app/blueprints/products.py
from flask import Blueprint, render_template, request, redirect, url_for, flash, current_app, jsonify
from werkzeug.utils import secure_filename
import json
import os

from agentic_rag import ingest_product_json, agentic_answer

products_bp = Blueprint("products", __name__, url_prefix="/products", template_folder="../../templates")

ALLOWED_EXT = {"json"}  # MVP: allow JSON uploads for structured products

def allowed_file(filename):
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXT

@products_bp.route("/", methods=["GET"])
def index():
    # list stored products
    db = current_app.db
    prods = list(db.products.find({}, {"raw":1, "title":1, "id":1, "created_at":1}).sort("created_at", -1))
    return render_template("products.html", products=prods)

@products_bp.route("/upload", methods=["POST"])
def upload_product():
    """
    Upload a JSON product file (or paste JSON via textarea).
    The file should match the product JSON structure.
    """
    if "file" in request.files and request.files["file"].filename:
        f = request.files["file"]
        if not allowed_file(f.filename):
            flash("Unsupported file type. Please upload a .json file.")
            return redirect(url_for("products.index"))
        text = f.read().decode("utf-8")
        try:
            data = json.loads(text)
        except Exception as e:
            flash(f"Invalid JSON: {e}")
            return redirect(url_for("products.index"))
    else:
        # or from textarea
        json_text = request.form.get("json_text", "").strip()
        if not json_text:
            flash("No input provided.")
            return redirect(url_for("products.index"))
        try:
            data = json.loads(json_text)
        except Exception as e:
            flash(f"Invalid JSON: {e}")
            return redirect(url_for("products.index"))

    # insert product into DB and optionally into embeddings
    try:
        prod_id = ingest_product_json(data, ingest_to_embeddings=False)  # only store product for now
        flash(f"Product saved (id={prod_id}). Use 'Index into RAG' to create embeddings.")
    except Exception as e:
        flash(f"Error saving product: {e}")
    return redirect(url_for("products.index"))

@products_bp.route("/index_into_rag/<product_id>", methods=["POST"])
def index_into_rag(product_id):
    """
    Trigger ingestion of a product into embeddings (chunks + vectors).
    """
    db = current_app.db
    doc = db.products.find_one({"id": product_id})
    if not doc:
        flash("Product not found.")
        return redirect(url_for("products.index"))
    try:
        ingest_product_json(doc["raw"], ingest_to_embeddings=True)
        flash("Product indexed into RAG DB.")
    except Exception as e:
        flash(f"Indexing error: {e}")
    return redirect(url_for("products.index"))

@products_bp.route("/rag_chat", methods=["GET", "POST"])
def rag_chat():
    answer = None
    sources = []
    query = ""
    if request.method == "POST":
        query = request.form.get("query", "").strip()
        if query:
            res = agentic_answer(query, top_k=5)
            answer = res.get("answer")
            sources = res.get("sources", [])
    return render_template("rag_chat.html", answer=answer, sources=sources, query=query)
