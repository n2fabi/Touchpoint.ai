from apscheduler.schedulers.background import BackgroundScheduler
from datetime import datetime, timedelta
from flask import current_app, Blueprint, render_template, request, session, redirect, url_for
from pymongo import DESCENDING
from dotenv import load_dotenv
import os
from llm_functions import generate_reminder_email, generate_reply_for_email, rewrite_email, friendlier_email, professional_email
from bson.objectid import ObjectId
from mailfetcher import generate_and_send_email
from background_tasks import sidebar_cache, get_reminders_list
from models import mark_email_ignored


load_dotenv()

scheduler = None
reminders_bp = Blueprint("reminders", __name__, url_prefix="/reminders")

USER_EMAIL = os.getenv("USER_EMAIL")




@reminders_bp.route("/", methods=["GET"])
def list_reminders():
    db = current_app.db
    page = max(1, int(request.args.get("page", 1)))
    per_page = 50
    skip = (page - 1) * per_page

    reminders = get_reminders_list(db, days=1)

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

@reminders_bp.route("/<email_id>/ignore", methods=["POST"])
def ignore_reminder(email_id):
    db = current_app.db
    try:
        email = db.emails.find_one({"_id": ObjectId(email_id)})
        if not email:
            return "Email not found", 404
    except Exception as e:
        return f"Invalid ID or error: {str(e)}", 400

    # Letzte Nachricht dieses Chats markieren
    mark_email_ignored(email_id)
    # Redirect zurück zur Übersicht
    return redirect(url_for('reminders.list_reminders'))


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
            use_rag = request.form.get("use_rag") == "1"
            answer = generate_reply_for_email(email_id, use_rag=use_rag)
            session[f"answer_{email_id}"] = answer

        elif action == "generate_reminder_email":
            answer = generate_reminder_email(email_id)
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

    return render_template(
        "reminder_detail.html",
        email=email,
        answer=answer,
        reason=reason
    )