from flask import flash
from dotenv import load_dotenv
import os
from openai import OpenAI
import json
from models import insert_email, get_email, insert_llm_usage
from datetime import datetime
import base64
from datetime import datetime
from email.utils import parseaddr
import inspect

load_dotenv()


def call_llm(prompt):
    """Fragt die OpenAI API mit dem gegebenen Prompt."""
    client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

    response = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[{"role": "user", "content": prompt}],
        max_tokens=300
    )

    # Extrahieren, was wir brauchen
    answer_text = response.choices[0].message.content
    usage_info = {
        "prompt_tokens": response.usage.prompt_tokens,
        "completion_tokens": response.usage.completion_tokens,
        "total_tokens": response.usage.total_tokens
    }
    model_used = response.model
    finish_reason = response.choices[0].finish_reason

    # Optional ins Log
    print(f"[OpenAI] Model: {model_used}, Finish: {finish_reason}, Usage: {usage_info}")
    print(answer_text)
    return answer_text, usage_info

def llm_json_response(prompt,purpose: str = None):
    """Fragt die OpenAI API und erzwingt strukturiertes JSON-Output."""
    if purpose is None:
        purpose = inspect.stack()[1].function

    client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

    response = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[{"role": "user", "content": prompt}],
        response_format={"type": "json_object"}  # Enforce JSON output
    )

    answer_json = response.choices[0].message.content
    usage_info = {
        "prompt_tokens": response.usage.prompt_tokens,
        "completion_tokens": response.usage.completion_tokens,
        "total_tokens": response.usage.total_tokens,
        "purpose": purpose  
    }
    model_used = response.model
    finish_reason = response.choices[0].finish_reason

    print(f"[OpenAI] Model: {model_used}, Finish: {finish_reason}, Usage: {usage_info}")
    print(answer_json)

    insert_llm_usage(
        user_id="jane_doe",  # Placeholder, später aus Session o.ä.
        purpose=purpose,
        prompt_tokens=usage_info["prompt_tokens"],
        completion_tokens=usage_info["completion_tokens"],
        tokens_used=usage_info["total_tokens"]
    )

    return answer_json, usage_info

def preprocess_incoming_email(raw_email_doc: dict, labels: list, id: str = None):
    """
    Extract necessary fields (From, To, Subject, Body, Timestamp) from raw Gmail message dict.
    Decodes Base64 body content and handles multipart messages.
    If no display name is found in From/To headers, use the part before '@' of the email.
    """
    payload = raw_email_doc.get("payload", {})
    headers = {h["name"].lower(): h["value"] for h in payload.get("headers", [])}

    # ---- Extract From / To ----
    def safe_parse(header_value: str):
        """Return (name, email) with fallback to local-part if name missing."""
        name, email = parseaddr(header_value or "")
        if not email:
            return "", ""  # completely empty / malformed
        if not name:
            # fallback: take local-part (before '@')
            local_part = email.split("@")[0]
            name = local_part
        return name, email

    from_name, from_email = safe_parse(headers.get("from", ""))
    to_name, to_email = safe_parse(headers.get("to", ""))

    # ---- Other metadata ----
    subject = headers.get("subject", "")
    internal_ts = raw_email_doc.get("internalDate")
    timestamp = datetime.utcfromtimestamp(int(internal_ts) / 1000) if internal_ts else None

    # ---- Extract message body ----
    def decode_base64(data):
        if not data:
            return ""
        return base64.urlsafe_b64decode(data.encode("utf-8")).decode("utf-8", errors="ignore")

    body_text = ""
    if "parts" in payload:  # Multipart message
        for part in payload["parts"]:
            mime_type = part.get("mimeType", "")
            data = part.get("body", {}).get("data", "")
            if mime_type == "text/plain":
                body_text += decode_base64(data)
    else:
        # Single part message
        data = payload.get("body", {}).get("data", "")
        body_text = decode_base64(data)

    return {
        "from_name": from_name,
        "from_email": from_email,
        "to_name": to_name,
        "to_email": to_email,
        "subject": subject,
        "message_text": body_text.strip(),
        "timestamp": timestamp,
        "unread": "UNREAD" in labels,
        "raw_id": id
    }



def process_incoming_email(input_dict: dict):
    """
    Takes a preprocessed email dict and uses the LLM to convert it into our DB format.
    """
    print(input_dict)

    # Nur die beiden Felder für das LLM-Prompt auswählen
    llm_input = {
        "subject": input_dict.get("subject", ""),
        "message_text": input_dict.get("message_text", "")
    }

    # Prompt für das LLM
    prompt = f"""
    You are an assistant that summarizes emails, extracts tone and personality 
    and turns it into a JSON structure.

    Input:
    {json.dumps(llm_input, ensure_ascii=False)}

    Return a JSON in the following format:
    {{
    "summary": "<rewrite message_text as a short chat-style message in the email's language>",
    "tone": {{
        "formality": "<for example: formal, informal, friendly, professional>",
        "phrases": "<for example: 'Best regards', 'Cheers', Hi', 'Dear'>,",
        "language": "<for example: English, German, French>"
    }}
    }}"""

    # LLM-Aufruf (deine bestehende Funktion)
    llm_output, token_info = llm_json_response(prompt)

    # JSON aus LLM-Response parsen
    try:
        parsed = json.loads(llm_output)
    except json.JSONDecodeError:
        raise ValueError("LLM-Response was no valid JSON")

    # Email in DB einfügen
    insert_email(
        from_name=input_dict.get("from_name", ""),
        from_email=input_dict.get("from_email", ""),
        to_name=input_dict.get("to_name", ""),
        to_email=input_dict.get("to_email", ""),
        subject=input_dict.get("subject", ""),
        message=input_dict.get("message_text", ""),
        summary=parsed.get("summary", ""),
        tone=parsed.get("tone", {}),
        phrases=parsed.get("phrases", ""),
        language=parsed.get("language", "English"),
        unread=input_dict.get("unread", False),
        raw_id=input_dict.get("raw_id"),
        timestamp=input_dict.get("timestamp")
    )

    return parsed


def generate_reply_for_email(email_id: str):
    """
    Fetches an email from the DB and generates a reply as JSON.
    """
    email_data = get_email(email_id)
    if not email_data:
        raise ValueError("Email not found")

    prompt = f"""
    You are an AI email assistant. Write a personalized reply 
    to the following email. You are Jane Doe, a sales representative of TouchpointAI.
    The email you are replying to has the following content and metadata:
    Message: {email_data['message']}
    Tone: {email_data.get('tone', {}).get('formality', 'neutral')}
    Phrases: {email_data.get('tone', {}).get('phrases', '')}
    Language: {email_data.get('tone', {}).get('language', 'English')}

    Return the reply **only** as JSON in the following format:
    {{
        "body_text": "<Formatted version of the reply, including any necessary context from the original email>",
    }}
    """

    llm_output,token_info = llm_json_response(prompt)

    try:
        parsed = json.loads(llm_output)
    except json.JSONDecodeError:
        raise ValueError("LLM output was not valid JSON")
    parsed['to'] = f"{email_data['from']['email']}"
    parsed['from'] = f"{email_data['to']['email']}"
    parsed['subject'] = f"Re: {email_data.get('subject', 'No Subject')}"
    return parsed

def generate_reminder_email(email_id: str):
    """
    Generates a reminder email for a given email ID.
    """
    email_data = get_email(email_id)
    if not email_data:
        raise ValueError("Email not found")

    prompt = f"""
    You are an AI assistant. I sent my client an email, but they haven't replied yet.
    Write a polite reminder email to follow up. This is the original email:
    Message:
    {email_data['message']}

    Return the reminder email **only** as JSON in the following format:
    {{
        "body_text": "<Formatted version of the reminder email, including any necessary context from the original email>",
    }}
    """

    llm_output, token_info = llm_json_response(prompt)

    try:
        parsed = json.loads(llm_output)
    except json.JSONDecodeError:
        raise ValueError("LLM output was not valid JSON")
    parsed['to'] = f"{email_data['to']['email']}"
    parsed['from'] = f"{email_data['from']['email']}"
    parsed['subject'] = f"{email_data.get('subject', 'No Subject')}"
    return parsed

def generate_reply_from_chat(email_id: str, chat):
    """
    Generates a reply for an email based on a chat.
    """
    email_data = get_email(email_id)
    if not email_data:
        raise ValueError("Email not found")

    prompt = f"""
    You are an AI assistant. Reformulate this text to be a professional email: {chat}
    
    The email you are replying to has the following content and metadata:
    {email_data['message']}
    
    Tone: {email_data.get('tone', {}).get('formality', 'neutral')}
    Phrases: {email_data.get('tone', {}).get('phrases', '')}
    Language: {email_data.get('tone', {}).get('language', 'English')}
    Return the reply **only** as JSON in the following format:
    {{
        "body_text": "<Formatted version of the reply, including any necessary context from the original email, prioritize the chat content, make sure all information from the chat is included>"
    }}
    """
    llm_output, token_info = llm_json_response(prompt)
    try:
        parsed = json.loads(llm_output)
    except json.JSONDecodeError:
        raise ValueError("LLM output was not valid JSON")
    parsed['to'] = f"{email_data['from']['email']}"
    parsed['from'] = f"{email_data['to']['email']}"
    parsed['subject'] = f"Re: {email_data.get('subject', 'No Subject')}"
    return parsed

def rewrite_email(email_id: str, edited_text: str):
    """
    Takes user-edited text and reformulates it as a professional email reply.
    """
    email_data = get_email(email_id)
    if not email_data:
        raise ValueError("Email not found")

    prompt = f"""
    You are an AI assistant. 
    Correct any mistakes in the following text but keep the formating and content: 
    
    {edited_text}

    Return the reply **only** as JSON in the following format:
    {{
        "body_text": "<The corrected and formatted version of the email reply>",
    }}
    """

    llm_output, token_info = llm_json_response(prompt)

    try:
        parsed = json.loads(llm_output)
    except json.JSONDecodeError:
        raise ValueError("LLM output was not valid JSON")

    parsed['to'] = f"{email_data['from']['email']}"
    parsed['from'] = f"{email_data['to']['email']}"
    parsed['subject'] = f"Re: {email_data.get('subject', 'No Subject')}"
    return parsed

def friendlier_email(email_id: str, edited_text: str):
    """
    Takes user-edited text and reformulates it as a more friendly email reply.
    """
    email_data = get_email(email_id)
    if not email_data:
        raise ValueError("Email not found")

    prompt = f"""
    You are a friendly AI assistant. 
    Make the following text more friendly and warm, but keep the formating and content: 
    
    {edited_text}

    Return the reply **only** as JSON in the following format:
    {{
        "body_text": "<The corrected and formatted version of the email reply>",
    }}
    """

    llm_output, token_info = llm_json_response(prompt)

    try:
        parsed = json.loads(llm_output)
    except json.JSONDecodeError:
        raise ValueError("LLM output was not valid JSON")

    parsed['to'] = f"{email_data['from']['email']}"
    parsed['from'] = f"{email_data['to']['email']}"
    parsed['subject'] = f"Re: {email_data.get('subject', 'No Subject')}"
    return parsed

def professional_email(email_id: str, edited_text: str):
    """
    Takes user-edited text and reformulates it as a more professional email reply.
    """
    email_data = get_email(email_id)
    if not email_data:
        raise ValueError("Email not found")

    prompt = f"""
    You are a professional AI assistant. 
    Make the following text more professional and formal, but keep the formating and content: 
    
    {edited_text}

    Return the reply **only** as JSON in the following format:
    {{
        "body_text": "<The corrected and formatted version of the email reply>",
    }}
    """

    llm_output, token_info = llm_json_response(prompt)

    try:
        parsed = json.loads(llm_output)
    except json.JSONDecodeError:
        raise ValueError("LLM output was not valid JSON")

    parsed['to'] = f"{email_data['from']['email']}"
    parsed['from'] = f"{email_data['to']['email']}"
    parsed['subject'] = f"Re: {email_data.get('subject', 'No Subject')}"
    return parsed