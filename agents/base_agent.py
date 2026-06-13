"""
OpenAI SDK base agent wrapper.
All department agents inherit from this.
"""
import os
import json
from dotenv import load_dotenv
from openai import OpenAI

load_dotenv()

_MODEL_NAME = os.getenv("GROQ_MODEL", "openai/gpt-oss-20b")
_client = None


def _get_client():
    global _client
    if _client is None:
        api_key = os.getenv("GROQ_API_KEY", "")
        if not api_key or api_key == "your_groq_api_key_here":
            raise ValueError(
                "\n[ERROR] GROQ_API_KEY not set.\n"
                "  → Open .env and paste your API key.\n"
                "  → Then re-run the demo.\n"
            )
        _client = OpenAI(
            api_key=api_key,
            base_url="https://api.groq.com/openai/v1"
        )
    return _client


def call_llm(system_prompt: str, user_message: str, temperature: float = 0.3) -> str:
    """
    Call LLM with a system + user prompt.
    Returns the text response.
    Falls back to a mock response if API key is not set (demo mode).
    """
    try:
        client = _get_client()
        response = client.chat.completions.create(
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_message}
            ],
            model=_MODEL_NAME,
            temperature=temperature,
            max_tokens=1024,
        )
        return response.choices[0].message.content.strip()
    except ValueError as e:
        raise
    except Exception as e:
        return f"[LLM_ERROR: {str(e)[:120]}]"


def call_llm_json(system_prompt: str, user_message: str, temperature: float = 0.2) -> dict:
    """Call LLM and parse JSON from the response."""
    raw = call_llm(system_prompt, user_message + "\n\nRespond ONLY with valid JSON, do not include any markdown formatting or extra text.", temperature)
    
    raw = raw.strip()
    if raw.startswith("```"):
        raw = raw.split("```")[1]
        if raw.startswith("json"):
            raw = raw[4:]
    try:
        return json.loads(raw)
    except Exception:
        import re
        match = re.search(r'\{.*\}', raw.replace('\n', ''))
        if match:
            try:
                return json.loads(match.group())
            except:
                pass
        return {"raw_response": raw, "parse_error": True}
