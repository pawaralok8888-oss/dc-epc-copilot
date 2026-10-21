import json
import os

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

from google import genai
from google.genai import types

MODEL = os.getenv("GEMINI_MODEL", "gemini-3-flash-preview")


def _salvage(text: str):
    # Keep every complete object from a reply that was cut off mid-array.
    end = text.rfind("},")
    if end == -1:
        end = text.rfind("}")
        if end == -1:
            return None
        cut = text[:end + 1]
    else:
        cut = text[:end + 1]
    if not cut.lstrip().startswith("["):
        return None
    try:
        return json.loads(cut + "]")
    except json.JSONDecodeError:
        return None


def ask_llm_json(prompt: str, max_tokens: int = 8000, schema=None):
    key = os.getenv("GEMINI_API_KEY")
    if not key:
        raise RuntimeError("GEMINI_API_KEY is not set. Add it to .env, or use cached results.")

    config = {
        "max_output_tokens": max_tokens,
        "response_mime_type": "application/json",
    }
    if schema is not None:
        config["response_schema"] = schema

    client = genai.Client(api_key=key)
    response = client.models.generate_content(
        model=MODEL,
        contents=prompt + "\nReturn only valid JSON. No prose, no markdown.",
        config=types.GenerateContentConfig(**config),
    )
    text = (response.text or "").strip()
    if text.startswith("```"):
        text = text.strip("`").removeprefix("json").strip()
    try:
        return json.loads(text)
    except json.JSONDecodeError as e:
        partial = _salvage(text)
        if partial is not None:
            print(f"  note: reply was cut off; kept {len(partial)} complete records")
            return partial
        raise RuntimeError(f"Model returned invalid JSON ({e}). Last 200 chars: ...{text[-200:]}")


def ask_llm_text(prompt: str, max_tokens: int = 1000) -> str:
    key = os.getenv("GEMINI_API_KEY")
    if not key:
        raise RuntimeError("GEMINI_API_KEY is not set. Add it to .env.")
    client = genai.Client(api_key=key)
    response = client.models.generate_content(
        model=MODEL,
        contents=prompt,
        config=types.GenerateContentConfig(max_output_tokens=max_tokens),
    )
    return (response.text or "").strip()
