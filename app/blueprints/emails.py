from flask import Blueprint, render_template, request, redirect, url_for
from bson.objectid import ObjectId
from models import find_emails  # deine Mongo-Verbindung
from llm_functions import generate_reply_for_email, rewrite_email
from mailfetcher import send_email  # Funktion zum Senden von E-Mails
from flask import flash, session

emails_bp = Blueprint("emails", __name__, url_prefix="/emails")


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

    # Prüfen ob es mehr gibt
    has_next = len(emails) > per_page
    if has_next:
        emails = emails[:-1]

    return render_template(
        "emails.html",
        emails=emails,
        page=page,
        has_next=has_next,
        search_term=search_query  # Name hier an Template angepasst
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

        elif action == "send_email":
            if not answer:
                print("Keine Antwort zum Senden!")
            else:
                try:
                    send_email(
                        sender="janedoefenschmirtz@gmail.com",
                        to=answer["to"],
                        subject=answer["subject"],
                        body_text=answer["body_text"]
                    )
                    print("E-Mail erfolgreich gesendet!", "success")
                    # Nach dem Senden Session löschen
                    session.pop(f"answer_{email_id}", None)
                except Exception as e:
                    print(f"Fehler beim Senden: {str(e)}", "error")

    return render_template("email_detail.html", email=email, answer=answer)
