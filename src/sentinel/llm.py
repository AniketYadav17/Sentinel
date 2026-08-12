"""Azure OpenAI seam — stdlib urllib, disk-cached, provider swap = this one file.

`post` (plus `chat_content` for chat-shaped payloads) is the shared transport: embed.py
and extract.py call it too, so the retry and error contract lives in exactly one place.
Requires AZURE_OPENAI_ENDPOINT and AZURE_OPENAI_API_KEY
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
USAGE_LOG = Path(__file__).parents[2] / "data" / "usage.jsonl"
CONSUMED: list[str] = []  # cache keys this process used — hits and misses both, so a replay can be compared to the run that published the number


def fingerprint() -> str:
    """Digest of the cache entries this process consumed. Same inputs -> same string."""
    if not CONSUMED:
        return "0 entries, sha256:-"
    digest = hashlib.sha256("\x00".join(sorted(CONSUMED)).encode()).hexdigest()
    return f"{len(set(CONSUMED))} entries, sha256:{digest[:12]}"


def _log_usage(path: str, deployment: str | None, usage: dict | None, seconds: float) -> None:
    """One row per LIVE call. Cache hits never reach post(), so this is first-run cost, not per-replay cost."""
    if not usage:
        return
    USAGE_LOG.parent.mkdir(parents=True, exist_ok=True)
    row = {"ts": time.time(), "path": path, "deployment": deployment, "ms": round(seconds * 1000)} | usage
    with USAGE_LOG.open("a", encoding="utf-8") as f:
        f.write(json.dumps(row) + "\n")


def post(path: str, body: dict) -> dict:
    """POST to the Azure OpenAI data plane (path e.g. "chat/completions") — one retry, then loud."""
    # first, ahead of the credential checks: replaying a cached metric needs no Azure account,
    # and if the flag is set the caller has already declared they don't intend to call out
    if os.environ.get("SENTINEL_OFFLINE"):
        raise RuntimeError(
            f"offline replay: {path} needed a live call, but SENTINEL_OFFLINE is set."
            " A published metric that cannot replay from cache is the bug — do not unset this to"
            " make the run pass; the number it would produce is a different number."
        )
    endpoint = os.environ.get("AZURE_OPENAI_ENDPOINT") or sys.exit(
        "AZURE_OPENAI_ENDPOINT not set — set it to your Azure OpenAI resource endpoint"
    )
    api_key = os.environ.get("AZURE_OPENAI_API_KEY") or sys.exit(
        "AZURE_OPENAI_API_KEY not set — set it to your Azure OpenAI resource key"
    )
    req = urllib.request.Request(
        f"{endpoint.rstrip('/')}/openai/v1/{path}",
        data=json.dumps(body).encode(),
        headers={"Content-Type": "application/json", "api-key": api_key},
    )
    for attempt in (1, 2):
        started = time.perf_counter()  # per attempt: a retry times the successful call, not the failure plus its sleep
        try:
            with urllib.request.urlopen(req, timeout=60) as resp:
                payload = json.load(resp)
            _log_usage(path, body.get("model"), payload.get("usage"), time.perf_counter() - started)
            return payload
        except urllib.error.HTTPError as e:  # subclass of URLError — this clause stays first
            if e.code == 429 and attempt == 1:
                time.sleep(int(e.headers.get("Retry-After") or 60))
                continue
            raise RuntimeError(f"Azure OpenAI HTTP {e.code}: {e.read().decode(errors='replace')}") from None
        except urllib.error.URLError as e:
            if attempt == 1:
                time.sleep(5)  # transient connection drops kill long runs; one retry, then loud
                continue
            raise RuntimeError(f"Azure OpenAI network failure after retry: {e.reason}") from None


def chat_content(payload: dict) -> str:
    """The one message string from a chat completion — every non-'stop' outcome raises."""
    choices = payload.get("choices") or []
    if not choices:
        raise RuntimeError(f"Azure OpenAI returned no choices: {json.dumps(payload)[:500]}")
    message = choices[0]["message"]
    if message.get("refusal"):
        raise RuntimeError(f"Azure OpenAI refused: {message['refusal']}")
    finish_reason = choices[0].get("finish_reason")
    if finish_reason != "stop":
        raise RuntimeError(f"Azure OpenAI finished with reason {finish_reason!r}, not 'stop'")
    return message["content"]


def generate_json(prompt: str, schema: dict, *, cache: bool = True) -> dict:
    """One structured-output call: prompt + json_schema -> parsed JSON object."""
    key_material = "\x00".join((MODEL, prompt, json.dumps(schema, sort_keys=True)))  # separator kills prompt/schema boundary ambiguity
    cache_path = CACHE_DIR / (hashlib.sha256(key_material.encode()).hexdigest() + ".json")
    CONSUMED.append(cache_path.stem)
    if cache and cache_path.exists():
        return json.loads(cache_path.read_text(encoding="utf-8"))
    text = chat_content(
        post(
            "chat/completions",
            {
                "model": os.environ.get("AZURE_OPENAI_CHAT_DEPLOYMENT", "sentinel-judge"),
                "temperature": 0,
                "messages": [{"role": "user", "content": prompt}],
                "response_format": {
                    "type": "json_schema",
                    "json_schema": {"name": "response", "strict": True, "schema": schema},
                },
            },
        )
    )
    try:
        result = json.loads(text)
    except json.JSONDecodeError:
        raise RuntimeError(f"Azure OpenAI output is not valid JSON: {text[:500]}") from None
    if cache:
        CACHE_DIR.mkdir(parents=True, exist_ok=True)
        cache_path.write_text(json.dumps(result), encoding="utf-8")
    return result
