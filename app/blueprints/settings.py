from flask import Blueprint, render_template, request, flash, redirect, url_for, current_app
from mailfetcher import fetch_and_store_raw_mails, raw_mail_transform


settings_bp = Blueprint("settings", __name__, url_prefix="/settings")

@settings_bp.route("/", methods=["GET", "POST"])
def index():
    if request.method == "POST":
        # Beispiel: Einstellungen speichern
        flash("Settings updated successfully!")
        # Hier könntest du z.B. Einstellungen aus dem Formular verarbeiten
    return render_template("settings.html")

# Weitere Grundfunktionalitäten können hier ergänzt werden, z.B.:
@settings_bp.route("/update_key", methods=["POST"])
def update_key():
    new_key = request.form.get("new_key")
    # Hier könntest du den neuen Schlüssel speichern oder validieren
    flash("API Key updated!")
    return redirect(url_for('settings.index'))

@settings_bp.route("/init_dump", methods=["POST"])
def init_dump():
    with current_app.app_context():
        new_msgs = fetch_and_store_raw_mails(current_app)
    flash("Initial email dump completed!")
    raw_mail_transform(new_msgs)
    flash("Raw emails transformed and processed.")
    return redirect(url_for('settings.index'))