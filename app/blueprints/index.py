from flask import Blueprint, render_template, request, redirect, url_for, current_app, flash
from llm_functions import call_llm, generate_reply_for_email, process_incoming_email, preprocess_incoming_email
from mailfetcher import fetch_and_store_raw_mails
from models import get_latest_email_id, get_raw_mail_by_id, get_last_raw_mail_id

index_bp = Blueprint(
    'index', __name__,
    template_folder='../templates'
)

def raw_mail_transform(msg_ids):
    """Transform raw email data into a more usable format."""
    for id in msg_ids:
        process_incoming_email(preprocess_incoming_email(get_raw_mail_by_id(id).get('raw_message', '')))
    

@index_bp.route("/", methods=["GET", "POST"])
def index():
    answer = None
    if request.method == "POST":
        action = request.form.get("action")
        if action == "ask_ai":
            user_prompt = request.form.get("prompt")
            if user_prompt:
                answer, token_info = call_llm(user_prompt)
        elif action == "answer_latest":
            print("Generating reply for latest email...")
            latest_id = get_latest_email_id()
            if latest_id:
                answer = generate_reply_for_email(latest_id)
            else:
                answer = "No emails found in the database."
            print(answer)
    return render_template("index.html", answer=answer)



@index_bp.route("/init_dump", methods=["POST"])
def init_dump():
    with current_app.app_context():
        new_msgs = fetch_and_store_raw_mails(current_app)
    flash("Initial email dump completed!")
    raw_mail_transform(new_msgs)
    flash("Raw emails transformed and processed.")
    return redirect(url_for('index.index'))

@index_bp.route("/test_action", methods=["POST"])
def test_action():
    """A test action to demonstrate functionality."""
    print("Test action executed successfully!")
    output = preprocess_incoming_email(get_raw_mail_by_id(get_last_raw_mail_id()).get('raw_message', ''))
    output = process_incoming_email(output)
    print(output)
    return redirect(url_for('index.index'))
