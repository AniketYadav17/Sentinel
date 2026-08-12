"""Image promotions -> layout-annotated text through the same Azure OpenAI deployment as llm.py.

Used by audit.py's --media flag. Requires AZURE_OPENAI_ENDPOINT and AZURE_OPENAI_API_KEY
(AZURE_OPENAI_CHAT_DEPLOYMENT optional, default "sentinel-judge"). Output is free text (no
response_format) meant to enter the audit graph as input_text, fenced there like any other
untrusted communication — image-borne instructions become inert transcription.
"""

import base64
import hashlib
import os
from pathlib import Path

from sentinel.llm import chat_content, post

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
    data_url = f"data:image/{media_type};base64,{base64.b64encode(data).decode()}"
    text = chat_content(
        post(
            "chat/completions",
            {
                "model": os.environ.get("AZURE_OPENAI_CHAT_DEPLOYMENT", "sentinel-judge"),
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
            },
        )
    )
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    cache_path.write_text(text, encoding="utf-8")
    return text
