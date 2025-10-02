# app/models.py
from bson import ObjectId
from flask import current_app
from datetime import datetime
from pymongo import DESCENDING

USER_EMAIL = "janedoefenschmirtz@gmail.com"




# ---- Customers ----
def find_customers(filter_q={}, limit=100):
    db = current_app.db
    return list(db.customers.find(filter_q).limit(limit))

def get_customer(customer_id):
    db = current_app.db
    return db.customers.find_one({'_id': ObjectId(customer_id)})


# ---- Emails ----
def insert_email(from_name, from_email, to_name, to_email, subject, message, summary=None, tone=None, phrases=None, language=None, unread=False, raw_id=None, timestamp=None, files=None):
    """Speichert eine neue E-Mail in MongoDB."""
    db = current_app.db
    doc = {
        "from": {"name": from_name, "email": from_email},
        "to": {"name": to_name, "email": to_email},
        "subject": subject,
        "message": message,
        "summary": summary or [],
        "tone": tone or {},
        "phrases": phrases or {},
        "language": language or "English",
        "files": files or [],
        "unread": unread,
        "raw_id": raw_id,
        "timestamp": timestamp  # Add timestamp
    }
    result = db.emails.insert_one(doc)
    return str(result.inserted_id)

def find_emails(filter_q={}, limit=100):
    """Liest E-Mails aus der DB."""
    db = current_app.db
    return list(db.emails.find(filter_q).limit(limit))

def get_email(email_id):
    """Holt eine E-Mail nach ID."""
    db = current_app.db
    return db.emails.find_one({'_id': ObjectId(email_id)})

def get_latest_email_id():
    """
    Fetches the most recent email id from the DB, sorted by timestamp.
    """
    db = current_app.db
    doc = db.emails.find_one(sort=[("timestamp", -1)])
    return str(doc['_id']) if doc else None

def mark_email_read(email_id):
    """Markiert eine E-Mail als gelesen."""
    db = current_app.db
    return db.emails.update_one(
        {"_id": ObjectId(email_id)},
        {"$set": {"unread": False}}
    )

def mark_email_ignored(email_id):
    """Markiert eine E-Mail als ignoriert."""
    db = current_app.db
    return db.emails.update_one(
        {"_id": ObjectId(email_id)},
        {"$set": {"touchpoint_ignored": True}}
    )

def get_last_incoming_email_id(partner_email):
    db = current_app.db
    mail = db.emails.find_one(
        {"from.email": partner_email, "to.email": USER_EMAIL},
        sort=[("timestamp", DESCENDING)]
    )
    return mail["_id"] if mail else None


# ---- raw_mail ----
#raw mail from email provider
def get_raw_mail_collection():
    """Shortcut to the raw_mail collection."""
    return current_app.db.raw_mail

def insert_raw_mail(raw_message, labels=None):
    """Insert a raw Gmail message into raw_mail DB."""
    coll = get_raw_mail_collection()
    doc = {
        "_id": raw_message["id"],   # Gmail-ID direkt als Primärschlüssel (STRING!)
        "raw_message": raw_message,
        "processed": False,
        "labels": labels or []  # Fallback auf leere Liste, wenn keine Labels angegeben sind
    }
    return coll.insert_one(doc)

def find_raw_mails(filter_q={}, limit=100):
    """Fetch raw Gmail messages."""
    coll = get_raw_mail_collection()
    return list(coll.find(filter_q).limit(limit))

def get_raw_mail_by_id(mail_id: str):
    """Fetch raw Gmail message by Gmail-ID (string)."""
    coll = get_raw_mail_collection()
    return coll.find_one({'_id': mail_id})   # <-- ohne ObjectId

def delete_raw_mail(mail_id: str):
    coll = get_raw_mail_collection()
    return coll.delete_one({'_id': mail_id})  # <-- ohne ObjectId

def mark_raw_mail_processed(mail_id: str):
    coll = get_raw_mail_collection()
    return coll.update_one(
        {"_id": mail_id},                     # <-- ohne ObjectId
        {"$set": {"processed": True}}
    )

def get_last_raw_mail_id():
    """Return only the Gmail-ID of the most recently inserted raw mail."""
    coll = get_raw_mail_collection()
    doc = coll.find_one(sort=[("_id", -1)])  # newest first
    return str(doc["_id"]) if doc else None


# ---- LLM-Usage ----
from datetime import datetime, timedelta
from flask import current_app


def insert_llm_usage(user_id, purpose, prompt_tokens, completion_tokens, tokens_used):
    """Speichert eine LLM-Nutzung in der DB."""
    db = current_app.db
    doc = {
        "user_id": user_id,
        "purpose": purpose,
        "prompt_tokens": prompt_tokens,
        "completion_tokens": completion_tokens,
        "tokens_used": tokens_used,
        "timestamp": datetime.utcnow()
    }
    return db.llm_usage.insert_one(doc)


def get_llm_usage_stats(user_id, days=7):
    """Aggregiert einfache Statistiken über alle LLM-Aufrufe im Zeitraum."""
    db = current_app.db
    since = datetime.utcnow() - timedelta(days=days)
    pipeline = [
        {"$match": {"user_id": user_id, "timestamp": {"$gte": since}}},
        {"$group": {
            "_id": None,
            "total_requests": {"$sum": 1},
            "total_tokens": {"$sum": "$tokens_used"},
            "avg_tokens": {"$avg": "$tokens_used"},
            "last_request": {"$max": "$timestamp"}
        }}
    ]
    result = list(db.llm_usage.aggregate(pipeline))
    return result[0] if result else {
        "total_requests": 0,
        "total_tokens": 0,
        "avg_tokens": 0,
        "last_request": None
    }


def get_tokens_used_this_week(user_id):
    """Tokens diese Woche und Vergleich zu letzter Woche."""
    db = current_app.db
    now = datetime.utcnow()
    start_of_week = now - timedelta(days=now.weekday())  # Montag dieser Woche
    start_last_week = start_of_week - timedelta(days=7)

    # Tokens diese Woche
    tokens_this_week = db.llm_usage.aggregate([
        {"$match": {
            "user_id": user_id,
            "timestamp": {"$gte": start_of_week}
        }},
        {"$group": {"_id": None, "total": {"$sum": "$tokens_used"}}}
    ])
    tokens_this_week = list(tokens_this_week)
    tokens_this_week = tokens_this_week[0]["total"] if tokens_this_week else 0

    # Tokens letzte Woche
    tokens_last_week = db.llm_usage.aggregate([
        {"$match": {
            "user_id": user_id,
            "timestamp": {"$gte": start_last_week, "$lt": start_of_week}
        }},
        {"$group": {"_id": None, "total": {"$sum": "$tokens_used"}}}
    ])
    tokens_last_week = list(tokens_last_week)
    tokens_last_week = tokens_last_week[0]["total"] if tokens_last_week else 0

    # Prozentänderung
    change = 0
    if tokens_last_week > 0:
        change = ((tokens_this_week - tokens_last_week) / tokens_last_week) * 100

    return {
        "tokens_this_week": tokens_this_week,
        "tokens_last_week": tokens_last_week,
        "change_percent": round(change, 2)
    }


def get_free_replies_left(user_id, daily_limit=5):
    """
    Für das Free-Modell: Wie viele E-Mails darf ein User heute noch beantworten?
    """
    db = current_app.db
    start_of_day = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
    replies_today = db.llm_usage.count_documents({
        "user_id": user_id,
        "timestamp": {"$gte": start_of_day}
    })
    return max(0, daily_limit - replies_today)
