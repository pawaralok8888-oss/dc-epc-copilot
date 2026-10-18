"""One Gemini vision call: nameplate image -> {model, rating, tag} JSON.
Setup:  pip install google-genai pydantic python-dotenv
        put GEMINI_API_KEY=... in .env (get one at https://aistudio.google.com/apikey)
Run:    python src/vision/gemini_test.py [image_path]
"""
import os, sys
from pathlib import Path
from dotenv import load_dotenv
from pydantic import BaseModel
from google import genai
from google.genai import types

load_dotenv()

class Nameplate(BaseModel):
    model: str | None
    rating_value: float | None
    unit: str | None
    tag: str | None
    confidence: float  # 0-1, how legible the plate is

PROMPT = ("Read this equipment nameplate photo. Return model, rating_value (number), unit, tag, "
          "and confidence (0-1; use low values if text is blurry or unreadable). "
          "Use null for any field you cannot read. Do not guess.")

def read_nameplate(path: str, model_name: str = "gemini-3.8-flash") -> Nameplate:
    client = genai.Client(api_key=os.environ["GEMINI_API_KEY"])
    img = Path(path).read_bytes()
    resp = client.models.generate_content(
        model=model_name,
        contents=[types.Part.from_bytes(data=img, mime_type="image/png"), PROMPT],
        config=types.GenerateContentConfig(
            response_mime_type="application/json",
            response_schema=Nameplate,
            temperature=0,
        ),
    )
    return resp.parsed

if __name__ == "__main__":
    default = Path(__file__).resolve().parents[2] / "data/photos/PH-05_brk-05.png"
    p = sys.argv[1] if len(sys.argv) > 1 else str(default)
    print(read_nameplate(p).model_dump_json(indent=2))
