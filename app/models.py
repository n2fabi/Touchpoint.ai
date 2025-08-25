# app/models.py
from bson import ObjectId
from flask import current_app
from datetime import datetime

# ---- Customers ----
def find_customers(filter_q={}, limit=100):
    db = current_app.db
    return list(db.customers.find(filter_q).limit(limit))

def get_customer(customer_id):
    db = current_app.db
    return db.customers.find_one({'_id': ObjectId(customer_id)})


# ---- Emails ----
def insert_email(from_name, from_email, to_name, to_email, subject, message, summary=None, tone=None, phrases=None, language=None, timestamp=None, files=None):
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


#raw mail from email provider
def get_raw_mail_collection():
    """Shortcut to the raw_mail collection."""
    return current_app.db.raw_mail

# ---- raw_mail ----

def insert_raw_mail(raw_message):
    """Insert a raw Gmail message into raw_mail DB."""
    coll = get_raw_mail_collection()
    doc = {
        "_id": raw_message["id"],   # Gmail-ID direkt als Primärschlüssel (STRING!)
        "raw_message": raw_message,
        "processed": False
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
