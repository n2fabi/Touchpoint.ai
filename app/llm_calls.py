from openai import OpenAI
import os
import inspect
from models import insert_llm_usage

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

    insert_llm_usage(
        user_id="jane_doe",  # Placeholder, später aus Session o.ä.
        purpose=purpose,
        prompt_tokens=usage_info["prompt_tokens"],
        completion_tokens=usage_info["completion_tokens"],
        tokens_used=usage_info["total_tokens"]
    )

    return answer_json, usage_info

