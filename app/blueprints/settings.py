from flask import Blueprint, render_template, request, flash, redirect, url_for, current_app, session
from mailfetcher import fetch_and_store_raw_mails, raw_mail_transform

settings_bp = Blueprint("settings", __name__, url_prefix="/settings")

@settings_bp.route("/", methods=["GET", "POST"])
def index():
    if request.method == "POST":
        email_signature = request.form.get("email_signature", "")
        formatting_style = request.form.get("formatting_style", "default")
        reminder_days = request.form.get("reminder_days", 7)

        # Hier speichern wir in der Session (oder später in Mongo/DB)
        session["email_signature"] = email_signature
        session["formatting_style"] = formatting_style
        session["reminder_days"] = reminder_days

        flash("Settings updated successfully!", "success")
        return redirect(url_for("settings.index"))

    # Vorbelegen aus Session
    email_signature = session.get("email_signature", "")
    formatting_style = session.get("formatting_style", "default")
    reminder_days = session.get("reminder_days", 7)

    return render_template(
        "settings.html",
        email_signature=email_signature,
        formatting_style=formatting_style,
        reminder_days=reminder_days,
    )

@settings_bp.route("/update_key", methods=["POST"])
def update_key():
    new_key = request.form.get("new_key")
    flash("API Key updated!", "info")
    return redirect(url_for('settings.index'))

@settings_bp.route("/init_dump", methods=["POST"])
def init_dump():
    with current_app.app_context():
        new_msgs = fetch_and_store_raw_mails(current_app)
    print("Initial email dump completed!")
    raw_mail_transform(new_msgs)
    print("Raw emails transformed and processed.")
    flash("E-Mails erfolgreich neu geladen!", "info")
    return redirect(url_for('settings.index'))
