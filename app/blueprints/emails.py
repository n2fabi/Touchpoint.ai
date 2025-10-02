from flask import Blueprint, render_template, request, redirect, url_for
from bson.objectid import ObjectId
from models import find_emails, mark_email_read, get_last_incoming_email_id
from llm_functions import generate_reply_for_email, rewrite_email, friendlier_email, professional_email, generate_email_from_prompt
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
            key = "Today"
        elif mail_date == today - timedelta(days=1):
            key = "Yesterday"
        elif mail_date.isocalendar()[1] == today.isocalendar()[1] and mail_date.year == today.year:
            key = "This Week"
        elif mail_date.month == today.month and mail_date.year == today.year:
            key = "This Month"
        else:
            key = f"{calendar.month_name[mail_date.month]} {mail_date.year}"

        grouped[key].append(mail)

    # Reihenfolge festlegen
    ordered = {}
    for section in ["Today", "Yesterday", "This Week", "This Month"]:
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
            use_rag = request.form.get("use_rag") == "1"
            answer = generate_reply_for_email(email_id, use_rag=use_rag)
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

@emails_bp.route("/delete/<email_id>", methods=["POST"])
def delete_email(email_id):
    db = current_app.db
    db.emails.delete_one({"_id": ObjectId(email_id)})
    db.raw_emails.delete_one({"email_id": email_id})
    return redirect(url_for('emails.list_emails'))





@emails_bp.route("/new_email", methods=["GET", "POST"])
def new_email():
    answer = None

    if request.method == "POST":
        action = request.form.get("action")

        if action == "write_email":
            # Normale Email-Eingabe (User schreibt selbst)
            answer = {
                "from": request.form.get("from") or USER_EMAIL,
                "to": request.form.get("to"),
                "subject": request.form.get("subject"),
                "body_html": request.form.get("body_html"),
            }

        elif action == "generate_from_prompt":
            # LLM generiert Email aus Prompt
            prompt_text = request.form.get("prompt")
            email_reciever = request.form.get("to")
            email_id = None
            if email_reciever != None:
                email_id = get_last_incoming_email_id(email_reciever)
            answer = generate_email_from_prompt(prompt_text, email_id)
            

        elif action == "send_email":
            # Antwort aus hidden fields
            email_data = {
                "from": request.form.get("from"),
                "to": request.form.get("to"),
                "subject": request.form.get("subject"),
                "body_html": request.form.get("body_html"),
            }
            generate_and_send_email(USER_EMAIL, email_data)
            return redirect(url_for("emails.list_emails"))

    return render_template("new_email.html", answer=answer)
