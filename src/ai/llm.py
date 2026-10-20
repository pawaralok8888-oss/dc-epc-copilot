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


def ask_llm_json(prompt: str, max_tokens: int = 2000):
    key = os.getenv("GEMINI_API_KEY")
    if not key:
        raise RuntimeError("GEMINI_API_KEY is not set. Add it to .env, or use cached results.")
    client = genai.Client(api_key=key)
    response = client.models.generate_content(
        model=MODEL,
        contents=prompt + "\nReturn only valid JSON. No prose, no markdown.",
        config=types.GenerateContentConfig(
            max_output_tokens=max_tokens,
            response_mime_type="application/json",
        ),
    )
    text = (response.text or "").strip()
    if text.startswith("```"):
        text = text.strip("`").removeprefix("json").strip()
    return json.loads(text)
