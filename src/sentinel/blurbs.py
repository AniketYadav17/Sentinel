"""Contextual-retrieval blurbs: one Gemini blurb per chunk, then re-embed blurb+text.

Usage: python -m sentinel.blurbs   ->  data/blurbs/*.jsonl + data/embeddings_ctx/*.jsonl
One-time ~86 calls for CONC 3; blurbs cached via the llm.py disk cache.
"""

import json
from pathlib import Path

from sentinel.embed import embed_texts
from sentinel.llm import generate_json

BLURB_SCHEMA = {"type": "OBJECT", "properties": {"blurb": {"type": "STRING"}}, "required": ["blurb"]}


def blurb_prompt(chunk: dict) -> str:
    return (
        "One to two sentences situating this FCA Handbook provision for a retrieval system: what it"
        " governs and when it applies. No preamble.\n"
        f"Sourcebook {chunk['sourcebook']}, chapter {chunk['chapter']}, section {chunk['section']},"
        f" provision {chunk['rule_id']}{chunk['designation']}.\n\n{chunk['text']}"
    )


def contextual_text(chunk: dict, blurb: str) -> str:
    return blurb + "\n" + chunk["text"]


def main() -> None:
    root = Path(__file__).parents[2]
    chunk_files = sorted((root / "data" / "chunks").glob("*.jsonl"))
    if not chunk_files:
        raise SystemExit("no chunk files in data/chunks — run python -m sentinel.ingest first")
    (root / "data" / "blurbs").mkdir(parents=True, exist_ok=True)
    (root / "data" / "embeddings_ctx").mkdir(parents=True, exist_ok=True)
    for cf in chunk_files:
        chunks = [json.loads(l) for l in cf.read_text(encoding="utf-8").splitlines() if l]
        blurbed = [(c, generate_json(blurb_prompt(c), BLURB_SCHEMA)["blurb"]) for c in chunks]
        with (root / "data" / "blurbs" / cf.name).open("w", encoding="utf-8") as f:
            for c, b in blurbed:
                f.write(json.dumps({"rule_id": c["rule_id"], "blurb": b}) + "\n")
        vectors = embed_texts([contextual_text(c, b) for c, b in blurbed], "RETRIEVAL_DOCUMENT")
        with (root / "data" / "embeddings_ctx" / cf.name).open("w", encoding="utf-8") as f:
            for (c, _), v in zip(blurbed, vectors):
                f.write(json.dumps({"rule_id": c["rule_id"], "vector": v}) + "\n")
        print(f"{cf.name}: {len(blurbed)} blurbs + ctx vectors")


if __name__ == "__main__":
    main()
