"""Gemini embeddings via the batch REST endpoint — stdlib urllib, zero deps.

Usage: python -m sentinel.embed   ->  data/embeddings/<chapter>.jsonl
Requires GEMINI_API_KEY in the environment (free key: aistudio.google.com).
"""

import json
import math
import os
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

MODEL = "gemini-embedding-001"
URL = f"https://generativelanguage.googleapis.com/v1beta/models/{MODEL}:batchEmbedContents"
DIM = 768  # smaller than the 3072 default; we normalize ourselves below
BATCH = 100  # API max per batchEmbedContents call
SLEEP_SECONDS = 1.0  # politeness between batches, same policy as ingest.py


def embed_texts(texts: list[str], task_type: str) -> list[list[float]]:
    """L2-normalized DIM-dim vectors, one per text.

    task_type: "RETRIEVAL_DOCUMENT" for corpus chunks, "RETRIEVAL_QUERY" for queries.
    """
    key = os.environ.get("GEMINI_API_KEY") or sys.exit(
        "GEMINI_API_KEY not set — create one at aistudio.google.com and set the env var"
    )
    out: list[list[float]] = []
    for start in range(0, len(texts), BATCH):
        batch = texts[start : start + BATCH]
        body = json.dumps(
            {
                "requests": [
                    {
                        "model": f"models/{MODEL}",
                        "content": {"parts": [{"text": t}]},
                        "taskType": task_type,
                        "outputDimensionality": DIM,
                    }
                    for t in batch
                ]
            }
        ).encode()
        req = urllib.request.Request(
            URL, data=body, headers={"Content-Type": "application/json", "x-goog-api-key": key}
        )
        try:
            with urllib.request.urlopen(req, timeout=60) as resp:
                payload = json.load(resp)
        except urllib.error.HTTPError as e:
            raise RuntimeError(f"Gemini API HTTP {e.code}: {e.read().decode(errors='replace')}") from None
        embeddings = payload.get("embeddings") or []
        if len(embeddings) != len(batch):
            raise RuntimeError(f"Gemini returned {len(embeddings)} embeddings for {len(batch)} texts")
        for e in embeddings:
            v = e["values"]
            norm = math.sqrt(sum(x * x for x in v))
            if not norm:
                raise RuntimeError("zero-norm embedding from Gemini")
            out.append([x / norm for x in v])
        if start + BATCH < len(texts):
            time.sleep(SLEEP_SECONDS)
    return out


def main() -> None:
    root = Path(__file__).parents[2]
    chunk_files = sorted((root / "data" / "chunks").glob("*.jsonl"))
    if not chunk_files:
        sys.exit("no chunk files in data/chunks — run python -m sentinel.ingest first")
    out_dir = root / "data" / "embeddings"
    out_dir.mkdir(parents=True, exist_ok=True)
    for cf in chunk_files:
        chunks = [json.loads(line) for line in cf.read_text(encoding="utf-8").splitlines() if line]
        vectors = embed_texts([c["text"] for c in chunks], "RETRIEVAL_DOCUMENT")
        out = out_dir / cf.name
        with out.open("w", encoding="utf-8") as f:
            for c, v in zip(chunks, vectors):
                f.write(json.dumps({"rule_id": c["rule_id"], "vector": v}) + "\n")
        print(f"{cf.name}: {len(vectors)} vectors -> {out}")


if __name__ == "__main__":
    main()
