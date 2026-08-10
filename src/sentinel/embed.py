"""Azure OpenAI embeddings via the REST endpoint — stdlib urllib, zero deps.

Usage: python -m sentinel.embed   ->  data/embeddings/<chapter>.jsonl
Requires AZURE_OPENAI_ENDPOINT and AZURE_OPENAI_API_KEY in the environment
(AZURE_OPENAI_EMBED_DEPLOYMENT optional, default "sentinel-embed").
"""

import json
import math
import os
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

MODEL = "text-embedding-3-large"  # cache-key identity — the real model, not the deployment alias
DIM = 768  # smaller than the 3072 default; we normalize ourselves below
BATCH = 100  # texts per request


def embed_texts(texts: list[str]) -> list[list[float]]:
    """L2-normalized DIM-dim vectors, one per text."""
    endpoint = os.environ.get("AZURE_OPENAI_ENDPOINT") or sys.exit(
        "AZURE_OPENAI_ENDPOINT not set — set it to your Azure OpenAI resource endpoint"
    )
    key = os.environ.get("AZURE_OPENAI_API_KEY") or sys.exit(
        "AZURE_OPENAI_API_KEY not set — set it to your Azure OpenAI resource key"
    )
    deployment = os.environ.get("AZURE_OPENAI_EMBED_DEPLOYMENT", "sentinel-embed")
    url = f"{endpoint.rstrip('/')}/openai/v1/embeddings"
    out: list[list[float]] = []
    for start in range(0, len(texts), BATCH):
        batch = texts[start : start + BATCH]
        body = json.dumps({"model": deployment, "input": batch, "dimensions": DIM}).encode()
        req = urllib.request.Request(
            url, data=body, headers={"Content-Type": "application/json", "api-key": key}
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
        embeddings = payload.get("data") or []
        if len(embeddings) != len(batch):
            raise RuntimeError(f"Azure OpenAI returned {len(embeddings)} embeddings for {len(batch)} texts")
        for e in embeddings:
            v = e["embedding"]
            norm = math.sqrt(sum(x * x for x in v))
            if not norm:
                raise RuntimeError("zero-norm embedding from Azure OpenAI")
            out.append([x / norm for x in v])
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
        vectors = embed_texts([c["text"] for c in chunks])
        out = out_dir / cf.name
        with out.open("w", encoding="utf-8") as f:
            for c, v in zip(chunks, vectors):
                f.write(json.dumps({"rule_id": c["rule_id"], "vector": v}) + "\n")
        print(f"{cf.name}: {len(vectors)} vectors -> {out}")


if __name__ == "__main__":
    main()
