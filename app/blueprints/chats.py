from flask import Blueprint, render_template, request, session, flash
from bson.objectid import ObjectId
from models import find_emails  # Mongo Helper
from llm_functions import generate_reply_from_chat
from mailfetcher import send_email

chats_bp = Blueprint("chats", __name__, url_prefix="/chats")


@chats_bp.route("/", methods=["GET"])
def list_chats():
    emails = find_emails({})
    emails = sorted(emails, key=lambda x: x.get("timestamp", 0), reverse=True)

    my_email = "janedoefenschmirtz@gmail.com"

    chats = {}
    for mail in emails:
        contact = mail["from"]["email"]

        # Eigene Adresse überspringen
        if contact == my_email:
            continue

        if contact not in chats:
            chats[contact] = {
                "name": mail["from"].get("name", contact),
                "email": contact,
                "last_summary": mail.get("summary", mail.get("message", "")[:100])
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
                    session.pop(f"answer_{contact_email}", None)
                except Exception as e:
                    print(f"Fehler beim Senden: {str(e)}", "error")

    return render_template(
        "chat_detail.html",
        contact=contact_email,
        messages=chat_messages,
        answer=answer
    )

