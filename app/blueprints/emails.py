from flask import Blueprint, render_template, request
from bson.objectid import ObjectId
from models import find_emails, mark_email_read  # deine Mongo-Verbindung
from llm_functions import generate_reply_for_email, rewrite_email, friendlier_email, professional_email
from mailfetcher import generate_and_send_email, label_as_read, get_gmail_service  # Funktion zum Senden von E-Mails
from flask import session, current_app
import os
from background_tasks import refresh_emails
from collections import defaultdict
from datetime import datetime, timedelta
import calendar

emails_bp = Blueprint("emails", __name__, url_prefix="/emails")

USER_EMAIL = os.getenv("USER_EMAIL")

def group_emails_by_date(emails):
    today = datetime.now().date()
    grouped = defaultdict(list)

    for mail in emails:
        ts = mail["timestamp"]
        mail_date = ts.date()

        if mail_date == today:
            key = "Heute"
        elif mail_date == today - timedelta(days=1):
            key = "Gestern"
        elif mail_date.isocalendar()[1] == today.isocalendar()[1] and mail_date.year == today.year:
            key = "Diese Woche"
        elif mail_date.month == today.month and mail_date.year == today.year:
            key = "Diesen Monat"
        else:
            key = f"{calendar.month_name[mail_date.month]} {mail_date.year}"

        grouped[key].append(mail)

    # Reihenfolge festlegen
    ordered = {}
    for section in ["Heute", "Gestern", "Diese Woche", "Diesen Monat"]:
        if section in grouped:
            ordered[section] = sorted(grouped[section], key=lambda m: m["timestamp"], reverse=True)

    # Ältere Monate sortieren
    other_sections = sorted(
        [(k, v) for k, v in grouped.items() if k not in ordered],
        key=lambda kv: datetime.strptime(kv[0], "%B %Y"),
        reverse=True
    )
    for k, v in other_sections:
        ordered[k] = sorted(v, key=lambda m: m["timestamp"], reverse=True)

    return ordered



@emails_bp.route("/", methods=["GET"])
def list_emails():
    # Pagination
    page = int(request.args.get("page", 1))
    per_page = 50
    skip = (page - 1) * per_page

    # Suche
    search_query = request.args.get("search", "").strip()
    filter_q = {}
    if search_query:
        filter_q = {
            "$or": [
                {"message": {"$regex": search_query, "$options": "i"}},
                {"customer.name": {"$regex": search_query, "$options": "i"}},
                {"customer.email": {"$regex": search_query, "$options": "i"}},
                {"to": {"$regex": search_query, "$options": "i"}},
                {"from": {"$regex": search_query, "$options": "i"}}
            ]
        }

    # Emails laden
    emails = find_emails(filter_q)
    emails = sorted(emails, key=lambda x: x.get("timestamp", 0), reverse=True)
    emails = emails[skip:skip + per_page + 1]

    # Gruppieren nach Datum
    grouped_emails = group_emails_by_date(emails)

    has_next = False

    unread_count = sum(1 for e in emails if e.get("unread", False))


    # Prüfen ob es mehr gibt
    has_next = len(emails) > per_page
    if has_next:
        emails = emails[:-1]

    return render_template(
        "emails.html",
        grouped_emails=grouped_emails,
        page=page,
        has_next=has_next,
        search_term=search_query,
        unread_count=unread_count
    )

from flask import session

@emails_bp.route("/<email_id>", methods=["GET", "POST"])
def view_email(email_id):
    try:
        email_list = find_emails({"_id": ObjectId(email_id)})
        if not email_list:
            return "Email not found", 404
        email = email_list[0]
    except Exception as e:
        return f"Invalid ID or error: {str(e)}", 400

    # Mark email as read
    mark_email_read(email_id)
    service = get_gmail_service()
    label_as_read(service, email.get("raw_id", []))
    with current_app.app_context():
        refresh_emails(current_app)

    # Antwort aus Session laden, falls vorhanden
    answer = session.get(f"answer_{email_id}")

    if request.method == "POST":
        action = request.form.get("action")

        if action == "answer_email":
            answer = generate_reply_for_email(email_id)
            session[f"answer_{email_id}"] = answer

        elif action == "rewrite_email":
            edited_text = request.form.get("edited_message")
            answer = rewrite_email(email_id, edited_text)
            session[f"answer_{email_id}"] = answer

        elif action == "make_friendly":
            edited_text = request.form.get("edited_message")
            answer = friendlier_email(email_id, edited_text)
            session[f"answer_{email_id}"] = answer

        elif action == "make_professional":
            edited_text = request.form.get("edited_message")
            answer = professional_email(email_id, edited_text)
            session[f"answer_{email_id}"] = answer
            print("E-Mail erfolgreich professionell umgeschrieben!", "success")

        elif action == "send_email":
            generate_and_send_email(USER_EMAIL, answer)

    return render_template("email_detail.html", email=email, answer=answer)
