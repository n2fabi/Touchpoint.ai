from flask import Blueprint, render_template, request, current_app
from llm_calls import call_llm
from datetime import datetime, timedelta
from bson.objectid import ObjectId
import os

index_bp = Blueprint(
    'index', __name__,
    template_folder='../templates'
)

USER_EMAIL = os.getenv("USER_EMAIL")


# --- KPI Functions ---
def get_emails_sent_stats(db):
    now = datetime.utcnow()
    start_this_week = now - timedelta(days=now.weekday())
    start_last_week = start_this_week - timedelta(days=7)

    # count sent mails (from me)
    this_week = db.emails.count_documents({
        "from.email": USER_EMAIL,
        "timestamp": {"$gte": start_this_week, "$lt": now}
    })
    last_week = db.emails.count_documents({
        "from.email": USER_EMAIL,
        "timestamp": {"$gte": start_last_week, "$lt": start_this_week}
    })

    change = ((this_week - last_week) / last_week * 100) if last_week > 0 else None
    return this_week, change


def get_emails_received_stats(db):
    now = datetime.utcnow()
    start_this_week = now - timedelta(days=now.weekday())
    start_last_week = start_this_week - timedelta(days=7)

    this_week = db.emails.count_documents({
        "to.email": USER_EMAIL,
        "timestamp": {"$gte": start_this_week, "$lt": now}
    })
    last_week = db.emails.count_documents({
        "to.email": USER_EMAIL,
        "timestamp": {"$gte": start_last_week, "$lt": start_this_week}
    })

    change = ((this_week - last_week) / last_week * 100) if last_week > 0 else None
    return this_week, change


def get_avg_response_time(db):
    """
    Berechnet die durchschnittliche Antwortzeit (in Stunden).
    Annahme: Antwort = eine E-Mail von USER_EMAIL auf eine letzte eingegangene Mail desselben Partners.
    """
    pipeline = [
        {"$match": {"$or": [{"from.email": USER_EMAIL}, {"to.email": USER_EMAIL}]}},
        {"$sort": {"timestamp": 1}},
        {
            "$group": {
                "_id": {"partner": {"$cond": [
                    {"$eq": ["$from.email", USER_EMAIL]}, "$to.email", "$from.email"
                ]}},
                "emails": {"$push": {"from": "$from.email", "to": "$to.email", "ts": "$timestamp"}}
            }
        }
    ]
    threads = list(db.emails.aggregate(pipeline))
    response_times = []

    for t in threads:
        emails = t["emails"]
        for i in range(1, len(emails)):
            prev, curr = emails[i-1], emails[i]
            if prev["to"] == USER_EMAIL and curr["from"] == USER_EMAIL:
                delta = (curr["ts"] - prev["ts"]).total_seconds() / 3600
                response_times.append(delta)

    if not response_times:
        return None, None

    avg_this_week = sum(response_times) / len(response_times)

    # todo: refine for "last week" vs "this week"
    # For now: dummy comparison
    return round(avg_this_week, 2), -10.0


def get_top_partners(db, limit=5):
    pipeline = [
        {"$match": {"$or": [{"from.email": USER_EMAIL}, {"to.email": USER_EMAIL}]}},
        {"$project": {
            "partner": {"$cond": [
                {"$eq": ["$from.email", USER_EMAIL]}, "$to.email", "$from.email"
            ]}
        }},
        {"$group": {"_id": "$partner", "count": {"$sum": 1}}},
        {"$sort": {"count": -1}},
        {"$limit": limit}
    ]
    return [doc["_id"] for doc in db.emails.aggregate(pipeline)]


def get_tokens_used_stats(db):
    # Placeholder – du kannst hier dein Token-Tracking integrieren
    now = datetime.utcnow()
    start_this_week = now - timedelta(days=now.weekday())
    start_last_week = start_this_week - timedelta(days=7)

    # Annahme: du loggst Tokens in einer Collection "usage"
    this_week = db.usage.count_documents({"timestamp": {"$gte": start_this_week, "$lt": now}})
    last_week = db.usage.count_documents({"timestamp": {"$gte": start_last_week, "$lt": start_this_week}})

    change = ((this_week - last_week) / last_week * 100) if last_week > 0 else None
    return this_week, change


def get_free_replies_left(user_id=None):
    # Demo: Fixwert oder simple Daily Reset
    DAILY_LIMIT = 5
    # TODO: Zähle heutige Antworten aus DB (z. B. "actions" collection)
    used_today = 2
    return DAILY_LIMIT - used_today


# --- ROUTE ---
@index_bp.route("/", methods=["GET", "POST"])
def index():
    db = current_app.db
    answer = None

    emails_sent, emails_sent_change = get_emails_sent_stats(db)
    emails_received, emails_received_change = get_emails_received_stats(db)
    avg_response, avg_response_change = get_avg_response_time(db)
    top_partners = get_top_partners(db)
    tokens_used, tokens_used_change = get_tokens_used_stats(db)
    free_replies_left = get_free_replies_left()

    kpis = {
        "emails_sent": emails_sent,
        "emails_sent_change": emails_sent_change,
        "emails_received": emails_received,
        "emails_received_change": emails_received_change,
        "avg_response_time": avg_response,
        "avg_response_change": avg_response_change,
        "free_replies_left": free_replies_left,
        "top_partners": top_partners,
        "tokens_used": tokens_used,
        "tokens_used_change": tokens_used_change
    }

    if request.method == "POST":
        action = request.form.get("action")
        if action == "ask_ai":
            user_prompt = request.form.get("prompt")
            if user_prompt:
                answer, token_info = call_llm(user_prompt)

    return render_template("index.html", answer=answer, kpis=kpis)

@index_bp.route("/_health")
def health():
    return "ok", 200
