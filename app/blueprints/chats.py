from flask import Blueprint, render_template, request, session, flash
from bson.objectid import ObjectId
from models import find_emails  # Mongo Helper
from llm_functions import generate_reply_from_chat
from mailfetcher import generate_and_send_email
from dotenv import load_dotenv
import os

chats_bp = Blueprint("chats", __name__, url_prefix="/chats")

USER_EMAIL = os.getenv("USER_EMAIL")


@chats_bp.route("/", methods=["GET"])
def list_chats():
    emails = find_emails({})
    emails = sorted(emails, key=lambda x: x.get("timestamp", 0), reverse=True)

    chats = {}
    for mail in emails:
        contact = mail["from"]["email"]

        # Eigene Adresse überspringen
        if contact == USER_EMAIL:
            continue

        if contact not in chats:
            chats[contact] = {
                "name": mail["from"].get("name", contact),
                "email": contact,
                "last_summary": mail.get("summary", mail.get("message", "")[:100]),
                "last_timestamp": mail.get("timestamp")  # <-- hinzugefügt
            }

    return render_template("chats.html", chats=chats.values())



@chats_bp.route("/<contact_email>", methods=["GET", "POST"])
def view_chat(contact_email):
    emails = find_emails({
        "$or": [
            {"from.email": contact_email},
            {"to.email": contact_email}
        ]
    })
    emails = sorted(emails, key=lambda x: x.get("timestamp", 0))

    chat_messages = []
    for mail in emails:
        direction = "incoming" if mail["from"]["email"] == contact_email else "outgoing"
        chat_messages.append({
            "id": str(mail["_id"]),
            "direction": direction,
            "summary": mail.get("summary", mail.get("message", "")[:200]),
            "timestamp": mail.get("timestamp")
        })

    answer = session.get(f"answer_{contact_email}")
    action = request.form.get("action")

    if request.method == "POST":
        email_id = request.form.get("email_id")
        user_message = request.form.get("message", "")

        if action == "generate_email":
            answer = generate_reply_from_chat(email_id, user_message)
            session[f"answer_{contact_email}"] = answer

        elif action == "rewrite_email":
            edited_text = request.form.get("edited_message")
            # Use your rewrite logic (adapt as needed)
            answer = generate_reply_from_chat(email_id, edited_text)
            session[f"answer_{contact_email}"] = answer

        elif action == "send_email":
            generate_and_send_email(USER_EMAIL, answer)

    # Chats-Liste für die Sidebar
    all_emails = find_emails({})
    chat_dict = {}
    for mail in all_emails:
        contact = mail["from"]["email"]
        if contact == USER_EMAIL:
            continue
        if contact not in chat_dict:
            chat_dict[contact] = {
                "name": mail["from"].get("name", contact),
                "email": contact,
                "last_timestamp": mail.get("timestamp")
            }
    chats = list(chat_dict.values())

    return render_template(
        "chat_detail.html",
        contact=contact_email,
        messages=chat_messages,
        answer=answer,
        message_text=user_message if request.method == "POST" else "",
        chats=chats
    )

