"""Azure OpenAI structured-output seam — stdlib urllib, disk-cached, provider swap = this one file.

Used by the audit graph and evals. Requires AZURE_OPENAI_ENDPOINT and AZURE_OPENAI_API_KEY
(AZURE_OPENAI_CHAT_DEPLOYMENT optional, default "sentinel-judge").
"""

import hashlib
import json
import os
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

MODEL = "gpt-4.1-mini"  # cache-key identity — the real model, not the deployment alias; bump together with extract.py's MODEL — both key caches on it
CACHE_DIR = Path(__file__).parents[2] / "data" / "cache" / "llm"


def generate_json(prompt: str, schema: dict, *, cache: bool = True) -> dict:
    """One structured-output call: prompt + json_schema -> parsed JSON object."""
    key_material = "\x00".join((MODEL, prompt, json.dumps(schema, sort_keys=True)))  # separator kills prompt/schema boundary ambiguity
    cache_path = CACHE_DIR / (hashlib.sha256(key_material.encode()).hexdigest() + ".json")
    if cache and cache_path.exists():
        return json.loads(cache_path.read_text(encoding="utf-8"))
    endpoint = os.environ.get("AZURE_OPENAI_ENDPOINT") or sys.exit(
        "AZURE_OPENAI_ENDPOINT not set — set it to your Azure OpenAI resource endpoint"
    )
    api_key = os.environ.get("AZURE_OPENAI_API_KEY") or sys.exit(
        "AZURE_OPENAI_API_KEY not set — set it to your Azure OpenAI resource key"
    )
    deployment = os.environ.get("AZURE_OPENAI_CHAT_DEPLOYMENT", "sentinel-judge")
    url = f"{endpoint.rstrip('/')}/openai/v1/chat/completions"
    body = json.dumps(
        {
            "model": deployment,
            "temperature": 0,
            "messages": [{"role": "user", "content": prompt}],
            "response_format": {
                "type": "json_schema",
                "json_schema": {"name": "response", "strict": True, "schema": schema},
            },
        }
    ).encode()
    req = urllib.request.Request(
        url, data=body, headers={"Content-Type": "application/json", "api-key": api_key}
    )
    for attempt in (1, 2):
        try:
            with urllib.request.urlopen(req, timeout=60) as resp:
                payload = json.load(resp)
            break
        except urllib.error.HTTPError as e:
            if e.code == 429 and attempt == 1:
                time.sleep(int(e.headers.get("Retry-After") or 60))
                continue
            raise RuntimeError(f"Azure OpenAI HTTP {e.code}: {e.read().decode(errors='replace')}") from None
        except urllib.error.URLError as e:
            if attempt == 1:
                time.sleep(5)  # transient connection drops kill long runs; one retry, then loud
                continue
            raise RuntimeError(f"Azure OpenAI network failure after retry: {e.reason}") from None
    choices = payload.get("choices") or []
    if not choices:
        raise RuntimeError(f"Azure OpenAI returned no choices: {json.dumps(payload)[:500]}")
    message = choices[0]["message"]
    if message.get("refusal"):
        raise RuntimeError(f"Azure OpenAI refused: {message['refusal']}")
    finish_reason = choices[0].get("finish_reason")
    if finish_reason != "stop":
        raise RuntimeError(f"Azure OpenAI finished with reason {finish_reason!r}, not 'stop'")
    text = message["content"]
    try:
        result = json.loads(text)
    except json.JSONDecodeError:
        raise RuntimeError(f"Azure OpenAI output is not valid JSON: {text[:500]}") from None
    if cache:
        CACHE_DIR.mkdir(parents=True, exist_ok=True)
        cache_path.write_text(json.dumps(result), encoding="utf-8")
    return result
