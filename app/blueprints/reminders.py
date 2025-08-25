from apscheduler.schedulers.background import BackgroundScheduler
from datetime import datetime, timedelta
from flask import current_app, Blueprint, render_template, request, session, flash
from pymongo import DESCENDING
from dotenv import load_dotenv
import os
from llm_functions import generate_reminder_email, generate_reply_for_email
from bson.objectid import ObjectId
from mailfetcher import send_email

load_dotenv()

scheduler = None
reminders_bp = Blueprint("reminders", __name__, url_prefix="/reminders")

USER_EMAIL = os.getenv("USER_EMAIL")


def get_threads(db, days=3):
    """Gruppiert E-Mails nach Partner-E-Mail-Adresse und prüft, ob eine Antwort fällig ist."""
    emails = list(db.emails.find().sort("timestamp", DESCENDING))
    threads = {}
    threshold = datetime.utcnow() - timedelta(days=days)

    for mail in emails:
        sender = mail["from"]["email"]
        recipient = mail["to"]["email"] if isinstance(mail["to"], dict) else mail["to"]

        if sender == USER_EMAIL:
            partner = recipient
            direction = "outgoing"
        else:
            partner = sender
            direction = "incoming"

        if partner not in threads:
            threads[partner] = {"latest": mail, "needs_reply": False}

        if direction == "incoming":
            outgoing_after = db.emails.find_one({
                "from.email": USER_EMAIL,
                "to.email": partner,
                "timestamp": {"$gt": mail["timestamp"]}
            })
            if not outgoing_after:
                threads[partner]["needs_reply"] = True
                threads[partner]["reason"] = "waiting_for_reply"
        elif direction == "outgoing":
            incoming_after = db.emails.find_one({
                "from.email": partner,
                "to.email": USER_EMAIL,
                "timestamp": {"$gt": mail["timestamp"]}
            })
            if not incoming_after and mail["timestamp"] <= threshold:
                threads[partner]["needs_reply"] = True
                threads[partner]["reason"] = "follow_up"

        # Immer die neueste E-Mail speichern
        if mail["timestamp"] > threads[partner]["latest"]["timestamp"]:
            threads[partner]["latest"] = mail

    return threads



def get_reminders_list(db, days=3):
    """Erzeugt eine Liste für das Template ohne DB-Insert."""
    threads = get_threads(db, days=days)
    reminder_list = []

    for partner, data in threads.items():
        if not data["needs_reply"]:
            continue

        mail = data["latest"]
        # Bestimme, wer zuletzt geschrieben hat
        if mail["from"]["email"] == USER_EMAIL:
            last_messenger = {"name": mail["from"].get("name", "Ich"), "email": mail["from"]["email"]}
        else:
            last_messenger = {"name": mail["from"].get("name", "Unknown"), "email": mail["from"]["email"]}

        # Grund für Reminder
        reason = data.get("reason", "unknown")

        reminder_list.append({
            "email_id": mail["_id"],
            "customer": last_messenger,
            "timestamp": mail["timestamp"],
            "subject": mail.get("subject", "(kein Betreff)"),
            "preview": mail.get("message", "")[:300],
            "reason": reason
        })

    return reminder_list



def init_reminder(app):
    """Optional: Scheduler, falls du automatisch prüfen willst."""
    global scheduler
    scheduler = BackgroundScheduler()
    scheduler.add_job(
        func=lambda: reminder_job(app),
        trigger='interval',
        minutes=60,
        id='reminder_job',
        replace_existing=True
    )
    scheduler.start()


def reminder_job(app):
    """Nur Debug-Zwecke: prints Reminder-Liste."""
    with app.app_context():
        db = current_app.db
        reminders = get_reminders_list(db, days=0)
        print(f"Found {len(reminders)} reminders:")
        for r in reminders:
            print(f"- {r['partner']}: {r['subject']}")


@reminders_bp.route("/", methods=["GET"])
def list_reminders():
    db = current_app.db
    page = max(1, int(request.args.get("page", 1)))
    per_page = 50
    skip = (page - 1) * per_page

    reminders = get_reminders_list(db, days=0)

    search_query = request.args.get("q", "").strip()
    if search_query:
        reminders = [r for r in reminders if search_query.lower() in r["partner"].lower()]

    has_next = len(reminders) > skip + per_page
    reminders_page = reminders[skip:skip + per_page]

    return render_template(
        "reminders.html",
        reminders=reminders_page,
        page=page,
        has_next=has_next,
        search_term=search_query
    )

@reminders_bp.route("/<email_id>", methods=["GET", "POST"])
def reminder_detail(email_id):
    db = current_app.db
    try:
        email = db.emails.find_one({"_id": ObjectId(email_id)})
        if not email:
            return "Email not found", 404
    except Exception as e:
        return f"Invalid ID or error: {str(e)}", 400

    reminders = get_reminders_list(db, days=0)
    reason = None
    for r in reminders:
        if str(r["email_id"]) == str(email["_id"]):
            reason = r["reason"]
            break

    answer = session.get(f"answer_{email_id}")
    action = request.form.get("action")

    if request.method == "POST":
        if action == "answer_email":
            answer = generate_reply_for_email(email_id)
            session[f"answer_{email_id}"] = answer

        elif action == "generate_reminder_email":
            answer = generate_reminder_email(email_id)
            session[f"answer_{email_id}"] = answer

        elif action == "rewrite_email":
            edited_text = request.form.get("edited_message")
            # Use your rewrite logic (adapt as needed)
            answer = generate_reminder_email(email_id, edited_text)
            session[f"answer_{email_id}"] = answer

        elif action == "send_email":
            if not answer:
                print("Keine Antwort zum Senden!", "error")
            else:
                try:
                    send_email(
                        sender="janedoefenschmirtz@gmail.com",
                        to=answer["to"],
                        subject=answer["subject"],
                        body_text=answer["body_text"]
                    )
                    print("E-Mail erfolgreich gesendet!", "success")
                    session.pop(f"answer_{email_id}", None)
                except Exception as e:
                    print(f"Fehler beim Senden: {str(e)}", "error")

    return render_template(
        "reminder_detail.html",
        email=email,
        answer=answer,
        reason=reason
    )