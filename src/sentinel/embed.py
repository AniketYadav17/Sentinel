"""Azure OpenAI embeddings through llm.py's shared transport — stdlib urllib, zero deps.

Usage: python -m sentinel.embed   ->  data/embeddings/<chapter>.jsonl
Requires AZURE_OPENAI_ENDPOINT and AZURE_OPENAI_API_KEY
(AZURE_OPENAI_EMBED_DEPLOYMENT optional, default "sentinel-embed").
"""

import json
import math
import os
import sys
from pathlib import Path

from sentinel.index import read_jsonl
from sentinel.llm import post

MODEL = "text-embedding-3-large"  # cache-key identity — the real model, not the deployment alias
DIM = 768  # smaller than the 3072 default; we normalize ourselves below
BATCH = 100  # texts per request


def embed_texts(texts: list[str]) -> list[list[float]]:
    """L2-normalized DIM-dim vectors, one per text."""
    deployment = os.environ.get("AZURE_OPENAI_EMBED_DEPLOYMENT", "sentinel-embed")
    out: list[list[float]] = []
    for start in range(0, len(texts), BATCH):
        batch = texts[start : start + BATCH]
        payload = post("embeddings", {"model": deployment, "input": batch, "dimensions": DIM})
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
        chunks = read_jsonl(cf)
        vectors = embed_texts([c["text"] for c in chunks])
        out = out_dir / cf.name
        with out.open("w", encoding="utf-8") as f:
            for c, v in zip(chunks, vectors):
                f.write(json.dumps({"rule_id": c["rule_id"], "vector": v}) + "\n")
        print(f"{cf.name}: {len(vectors)} vectors -> {out}")


if __name__ == "__main__":
    main()
