"""Gemini structured-output seam — stdlib urllib, disk-cached, provider swap = this one file.

Used by the audit graph and evals. Requires GEMINI_API_KEY (free key: aistudio.google.com).
"""

import hashlib
import json
import os
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

MODEL = "gemini-2.5-flash-lite"
URL = f"https://generativelanguage.googleapis.com/v1beta/models/{MODEL}:generateContent"
CACHE_DIR = Path(__file__).parents[2] / "data" / "cache" / "llm"


def generate_json(prompt: str, schema: dict, *, cache: bool = True) -> dict:
    """One structured-output call: prompt + responseSchema -> parsed JSON object."""
    key_material = MODEL + prompt + json.dumps(schema, sort_keys=True)
    cache_path = CACHE_DIR / (hashlib.sha256(key_material.encode()).hexdigest() + ".json")
    if cache and cache_path.exists():
        return json.loads(cache_path.read_text(encoding="utf-8"))
    api_key = os.environ.get("GEMINI_API_KEY") or sys.exit(
        "GEMINI_API_KEY not set — create one at aistudio.google.com and set the env var"
    )
    body = json.dumps(
        {
            "contents": [{"parts": [{"text": prompt}]}],
            "generationConfig": {
                "temperature": 0,
                "responseMimeType": "application/json",
                "responseSchema": schema,
            },
        }
    ).encode()
    req = urllib.request.Request(
        URL, data=body, headers={"Content-Type": "application/json", "x-goog-api-key": api_key}
    )
    for attempt in (1, 2):
        try:
            with urllib.request.urlopen(req, timeout=60) as resp:
                payload = json.load(resp)
            break
        except urllib.error.HTTPError as e:
            if e.code == 429 and attempt == 1:
                time.sleep(60)  # free tier: one blunt wait outlives any rate window (embed.py precedent)
                continue
            raise RuntimeError(f"Gemini API HTTP {e.code}: {e.read().decode(errors='replace')}") from None
    candidates = payload.get("candidates") or []
    if not candidates:
        raise RuntimeError(f"Gemini returned no candidates: {json.dumps(payload)[:500]}")
    text = candidates[0]["content"]["parts"][0]["text"]
    try:
        result = json.loads(text)
    except json.JSONDecodeError:
        raise RuntimeError(f"Gemini output is not valid JSON: {text[:500]}") from None
    if cache:
        CACHE_DIR.mkdir(parents=True, exist_ok=True)
        cache_path.write_text(json.dumps(result), encoding="utf-8")
    return result
