"""Image promotions -> layout-annotated text through the same Azure OpenAI deployment as llm.py.

Used by audit.py's --media flag. Requires AZURE_OPENAI_ENDPOINT and AZURE_OPENAI_API_KEY
(AZURE_OPENAI_CHAT_DEPLOYMENT optional, default "sentinel-judge"). Output is free text (no
response_format) meant to enter the audit graph as input_text, fenced there like any other
untrusted communication — image-borne instructions become inert transcription.
"""

import base64
import hashlib
import json
import os
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

MODEL = "gpt-4.1-mini"  # cache-key identity — the real model behind sentinel-judge, not the deployment alias; bump alongside llm.py's MODEL on a provider swap
CACHE_DIR = Path(__file__).parents[2] / "data" / "cache" / "extract"

SUPPORTED_EXTENSIONS = {"jpg": "jpeg", "jpeg": "jpeg", "png": "png", "gif": "gif", "webp": "webp"}

ANNOTATE_PROMPT = (
    "Transcribe ALL text in this promotional image verbatim. Prefix every line with a layout"
    " annotation: [position · relative size · emphasis or contrast], e.g. `[headline · large ·"
    " bold] DRIVE AWAY TODAY` or `[footer · small · low-contrast] Warning: ...`. Transcribe"
    " exactly — never paraphrase, never omit small print. If a required-looking disclosure is"
    " partially legible, transcribe what is visible and annotate `[illegible]` for the rest."
    " Output only the annotated transcription."
)


def annotate_image(path: Path) -> str:
    """One vision call: image bytes -> layout-annotated transcription (free text, disk-cached)."""
    path = Path(path)
    ext = path.suffix.lstrip(".").lower()
    media_type = SUPPORTED_EXTENSIONS.get(ext)
    if media_type is None:
        raise SystemExit(
            f"{path}: unsupported image extension {ext!r} — convert to png first"
            f" ({ext!r} unsupported by the vision API)"
        )
    data = path.read_bytes()
    key_material = MODEL.encode() + b"\x00" + ANNOTATE_PROMPT.encode() + b"\x00" + data
    cache_path = CACHE_DIR / (hashlib.sha256(key_material).hexdigest() + ".txt")
    if cache_path.exists():
        return cache_path.read_text(encoding="utf-8")
    endpoint = os.environ.get("AZURE_OPENAI_ENDPOINT") or sys.exit(
        "AZURE_OPENAI_ENDPOINT not set — set it to your Azure OpenAI resource endpoint"
    )
    api_key = os.environ.get("AZURE_OPENAI_API_KEY") or sys.exit(
        "AZURE_OPENAI_API_KEY not set — set it to your Azure OpenAI resource key"
    )
    deployment = os.environ.get("AZURE_OPENAI_CHAT_DEPLOYMENT", "sentinel-judge")
    url = f"{endpoint.rstrip('/')}/openai/v1/chat/completions"
    data_url = f"data:image/{media_type};base64,{base64.b64encode(data).decode()}"
    body = json.dumps(
        {
            "model": deployment,
            "temperature": 0,
            "messages": [
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": ANNOTATE_PROMPT},
                        {"type": "image_url", "image_url": {"url": data_url}},
                    ],
                }
            ],
        }
    ).encode()
    req = urllib.request.Request(
        url, data=body, headers={"Content-Type": "application/json", "api-key": api_key}
    )
    # Third copy of this retry loop (llm.py has the first two call sites) — ledgered debt,
    # a shared retry helper is deferred to a future refactor, not this task.
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
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    cache_path.write_text(text, encoding="utf-8")
    return text
