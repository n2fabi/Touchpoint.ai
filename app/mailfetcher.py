import os
import pickle
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from google.auth.transport.requests import Request
from dotenv import load_dotenv
from models import insert_raw_mail, get_raw_mail_by_id
import base64
from email.mime.text import MIMEText
from llm_functions import preprocess_incoming_email, process_incoming_email
from flask import current_app

# Load environment variables
load_dotenv()

# Read settings from .env
CREDENTIALS_PATH = os.getenv("GOOGLE_CREDENTIALS_PATH", "credentials.json")
TOKEN_PATH = os.getenv("GOOGLE_TOKEN_PATH", "token.pickle")
SCOPES = [os.getenv("GMAIL_SCOPES", "https://www.googleapis.com/auth/gmail.modify")]

def get_gmail_service():
    """Authenticate and return Gmail API service, refreshing or re-authorizing if needed."""
    creds = None
    if os.path.exists(TOKEN_PATH):
        with open(TOKEN_PATH, 'rb') as token_file:
            creds = pickle.load(token_file)

    # Prüfen, ob creds fehlen, ungültig sind oder abgelaufen ohne Refresh-Token
    if not creds or not creds.valid:
        try:
            if creds and creds.expired and creds.refresh_token:
                # Versuche Token zu aktualisieren
                creds.refresh(Request())
                print("Token erfolgreich aktualisiert.")
            else:
                # Neuer OAuth-Flow, falls kein gültiger Token vorhanden
                print("Starte neue Authentifizierung...")
                flow = InstalledAppFlow.from_client_secrets_file(
                    CREDENTIALS_PATH, SCOPES
                )
                creds = flow.run_local_server(port=0)
        except Exception as e:
            print(f"Fehler beim Aktualisieren oder Authentifizieren: {e}")
            print("Starte neue Authentifizierung...")
            flow = InstalledAppFlow.from_client_secrets_file(
                CREDENTIALS_PATH, SCOPES
            )
            creds = flow.run_local_server(port=0)

        # Token sichern
        with open(TOKEN_PATH, 'wb') as token_file:
            pickle.dump(creds, token_file)

    return build('gmail', 'v1', credentials=creds)


def label_as_processed(service, message_ids):
    """Add 'processed' label to given Gmail message IDs."""
    labels_list = service.users().labels().list(userId='me').execute().get('labels', [])
    processed_label = next((lbl for lbl in labels_list if lbl['name'] == 'processed'), None)

    if not processed_label:
        processed_label = service.users().labels().create(
            userId='me',
            body={
                'name': 'processed',
                'labelListVisibility': 'labelShow',
                'messageListVisibility': 'show'
            }
        ).execute()

    service.users().messages().batchModify(
        userId='me',
        body={
            'ids': message_ids,
            'addLabelIds': [processed_label['id']]
        }
    ).execute()

def label_as_read(service, message_ids):
    """Remove 'UNREAD' label to given Gmail message IDs."""
    service.users().messages().batchModify(
        userId='me',
        body={
            'ids': message_ids,
            'removeLabelIds': ['UNREAD']
        }
    ).execute()

def fetch_and_store_raw_mails(app):
    """Fetch unprocessed emails from Gmail and store in raw_mail DB."""
    service = get_gmail_service()
    all_msg_ids = []  # <- hier initialisieren

    for label in ['INBOX', 'SENT']:
        results = service.users().messages().list(
            userId='me',
            labelIds=[label],
            q='-label:processed'
        ).execute()

        messages = results.get('messages', [])
        if not messages:
            continue

        with app.app_context():
            for msg in messages:
                msg_data = service.users().messages().get(
                    userId='me', id=msg['id'], format='full'
                ).execute()
                # Check unread status
                label_ids = msg_data.get("labelIds", [])
                insert_raw_mail(msg_data, labels=label_ids)
                print(f"Inserted raw {label}-email {msg['id']} into DB.")

            # processed Label setzen
            msg_ids = [m['id'] for m in messages]
            label_as_processed(service, msg_ids)
            all_msg_ids.extend(msg_ids)

    return all_msg_ids


def create_message(sender, to, subject, body_text):
    """Create a MIMEText email and encode it in base64url."""
    message = MIMEText(body_text, "plain", "utf-8")
    message["to"] = to
    message["from"] = sender
    message["subject"] = subject
    raw = base64.urlsafe_b64encode(message.as_bytes()).decode()
    return {"raw": raw}

def send_email(sender, to, subject, body_text):
    """Send an email using the Gmail API."""
    service = get_gmail_service()
    message = create_message(sender, to, subject, body_text)
    sent_msg = service.users().messages().send(userId="me", body=message).execute()
    print(f"Email sent! Message ID: {sent_msg['id']}")
    with current_app.app_context():
        msg_id = fetch_and_store_raw_mails(current_app)
    raw_mail_transform(msg_id)
    return sent_msg

def raw_mail_transform(msg_ids):
    """Transform raw email data into a more usable format."""
    for id in msg_ids:
        raw_doc = get_raw_mail_by_id(id)
        raw_message = raw_doc.get("raw_message", {})
        labels = raw_doc.get("labels", [])

        email_data = preprocess_incoming_email(raw_message, labels, id)
        process_incoming_email(email_data)

def generate_and_send_email(user_email, answer):
    """Generate and send an email based on logged in user and LLM answer."""
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
        except Exception as e:
            print(f"Fehler beim Senden: {str(e)}", "error")


if __name__ == "__main__":
    from app import create_app
    app = create_app()
    fetch_and_store_raw_mails(app)

