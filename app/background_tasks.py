from apscheduler.schedulers.background import BackgroundScheduler
from flask import current_app
from datetime import datetime
from mailfetcher import fetch_and_store_raw_mails, raw_mail_transform
from pymongo import DESCENDING
from dotenv import load_dotenv
import os
from flask import Blueprint
from datetime import timedelta
import time
from pymongo.errors import ServerSelectionTimeoutError



load_dotenv()


# Globaler Cache für Sidebar-Daten
sidebar_cache = {
    "unread_count": 0,
    "reminders_count": 0,
    "last_update": None
}

USER_EMAIL = os.getenv("USER_EMAIL")

def get_db(app, retries=5, delay=2):
    """Versucht mehrfach, die MongoDB-Verbindung herzustellen."""
    for _ in range(retries):
        try:
            return app.db
        except ServerSelectionTimeoutError:
            print("MongoDB noch nicht bereit, warte...", flush=True)
            time.sleep(delay)
    raise Exception("MongoDB nicht erreichbar nach mehreren Versuchen")

def safe_refresh_emails(app):
    try:
        with app.app_context():
            db = get_db(app)
            sidebar_cache["unread_count"] = db.emails.count_documents({"unread": True})
            sidebar_cache["last_update"] = datetime.utcnow()
    except Exception as e:
        print("Error in refresh_emails:", e, flush=True)

def safe_refresh_reminders(app):
    try:
        with app.app_context():
            db = get_db(app)
            sidebar_cache["reminders_count"] = len(get_reminders_list(db, days=1))
    except Exception as e:
        print("Error in refresh_reminders:", e, flush=True)

def safe_load_and_transform_raw_mails(app):
    try:
        with app.app_context():
            db = get_db(app)
            msg_ids = fetch_and_store_raw_mails(app)
            raw_mail_transform(msg_ids)
    except Exception as e:
        print("Error in load_and_transform_raw_mails:", e, flush=True)

def load_and_transform_raw_mails(app):
    """Rohdaten aus raw_mail DB holen und transformieren."""
    with app.app_context():
        msg_ids = fetch_and_store_raw_mails(app)
        raw_mail_transform(msg_ids)

def refresh_emails(app):
    """Neue Mails holen und Cache aktualisieren."""
    with app.app_context():

        # Unread Count aktualisieren
        db = current_app.db
        sidebar_cache["unread_count"] = db.emails.count_documents({"unread": True})
        sidebar_cache["last_update"] = datetime.utcnow()


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

        #skip ignored emails
        if mail.get("touchpoint_ignored", False):
            continue

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
            "receiver": partner,
            "timestamp": mail["timestamp"],
            "subject": mail.get("subject", "(kein Betreff)"),
            "preview": mail.get("message", "")[:300],
            "reason": reason
        })

    return reminder_list


def refresh_reminders(app):
    """Reminder zählen und Cache aktualisieren."""
    with app.app_context():
        db = current_app.db
        sidebar_cache["reminders_count"] = len(get_reminders_list(db, days=1))

def refresh_sidebar_cache(app):
    """Aktualisiert den Sidebar-Cache."""
    with app.app_context():
        db = current_app.db
        sidebar_cache["unread_count"] = db.emails.count_documents({"unread": True})
        sidebar_cache["reminders_count"] = len(get_reminders_list(db, days=1))
        sidebar_cache["last_update"] = datetime.utcnow()

from apscheduler.schedulers.background import BackgroundScheduler

def init_background(app):
    """Scheduler starten und Jobs registrieren."""
    scheduler = BackgroundScheduler()

    # Intervalle etwas großzügiger setzen
    scheduler.add_job(lambda: safe_refresh_emails(app), "interval", seconds=10, id="refresh_emails")
    scheduler.add_job(lambda: safe_refresh_reminders(app), "interval", seconds=10, id="refresh_reminders")
    scheduler.add_job(lambda: safe_load_and_transform_raw_mails(app), "interval", minutes=2, id="load_and_transform_raw_mails")

    scheduler.start()
    print("Background scheduler gestartet.", flush=True)

