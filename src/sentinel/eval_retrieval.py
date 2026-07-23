"""Score retrieval against the golden set: recall@k, hit@k, MRR per mode.

Usage: python -m sentinel.eval_retrieval [--mode bm25|dense|dense-ctx|hybrid|weighted|weighted-sweep|rerank|all] [--alpha 0.5]
Ground truth is each claim's cited rule ids, normalized to chunk granularity.
"""

import argparse
import hashlib
import json
import re
import sys
from collections import defaultdict
from pathlib import Path

from sentinel.embed import embed_texts
from sentinel.index import Index
from sentinel.rerank import rerank, RERANK_POOL

KS = (3, 5, 10)


def normalize_rule_id(rule: str) -> str:
    """'CONC 3.3.4G(2)' -> 'CONC 3.3.4' (the chunker's rule_id granularity)."""
    base = rule.split("(")[0].strip()
    m = re.fullmatch(r"(.*\d[A-Z]?)[RG]", base)
    return m.group(1) if m else base


def score(relevant: set[str], retrieved: list[str]) -> dict:
    out = {}
    for k in KS:
        top = set(retrieved[:k])
        out[f"recall@{k}"] = len(relevant & top) / len(relevant)
        out[f"hit@{k}"] = 1.0 if relevant & top else 0.0
    out["mrr"] = next((1 / (i + 1) for i, r in enumerate(retrieved) if r in relevant), 0.0)
    return out


def load_claims(golden_path: Path, corpus_rule_ids: set[str]) -> tuple[list[dict], int]:
    """One eval query per golden claim; claims whose cited rules are absent from the corpus are skipped and counted."""
    claims, skipped = [], 0
    for line in golden_path.read_text(encoding="utf-8").splitlines():
        if not line:
            continue
        example = json.loads(line)
        for c in example["claims"]:
            relevant = {normalize_rule_id(r) for r in c["rules"]} & corpus_rule_ids
            if relevant:
                claims.append({"query": c["claim"], "relevant": relevant, "area": example["area"]})
            else:
                skipped += 1
    return claims, skipped


def retrieve(index: Index, mode: str, query: str, query_vector, k: int = 10, alpha: float = 0.5) -> list[str]:
    if mode == "bm25":
        chunks = index.search_bm25(query, k)
    elif mode == "dense" or mode == "dense-ctx":
        chunks = index.search_dense(query_vector, k)
    elif mode == "weighted":
        chunks = index.search_weighted(query, query_vector, alpha, k)
    elif mode == "rerank":
        dense_chunks = index.search_dense(query_vector, RERANK_POOL)
        from sentinel.rerank import ce_scorer
        chunks = rerank(query, dense_chunks, ce_scorer, k)
    else:
        chunks = index.search_hybrid(query, query_vector, k)
    return [c["rule_id"] for c in chunks]


def query_vectors(queries: list[str], cache_path: Path) -> list[list[float]]:
    """Embed queries with a sha256-keyed JSONL cache so re-runs are offline."""
    sha = lambda text: hashlib.sha256(text.encode()).hexdigest()
    cache: dict[str, list[float]] = {}
    if cache_path.exists():
        for line in cache_path.read_text(encoding="utf-8").splitlines():
            if line:
                rec = json.loads(line)
                cache[rec["sha"]] = rec["vector"]
    missing = [q for q in dict.fromkeys(queries) if sha(q) not in cache]
    if missing:
        vectors = embed_texts(missing, "RETRIEVAL_QUERY")
        cache_path.parent.mkdir(parents=True, exist_ok=True)
        with cache_path.open("a", encoding="utf-8") as f:
            for q, v in zip(missing, vectors):
                cache[sha(q)] = v
                f.write(json.dumps({"sha": sha(q), "vector": v}) + "\n")
    return [cache[sha(q)] for q in queries]


def _print_table(mode: str, rows: list[dict]) -> None:
    metrics = [f"recall@{k}" for k in KS] + [f"hit@{k}" for k in KS] + ["mrr"]
    mean = lambda rs: {m: sum(r[m] for r in rs) / len(rs) for m in metrics}
    print(f"\n== {mode} ({len(rows)} claims) ==")
    header = f"{'':<22}" + "".join(f"{m:>10}" for m in metrics)
    print(header)
    line = lambda label, agg: print(f"{label:<22}" + "".join(f"{agg[m]:>10.3f}" for m in metrics))
    line("overall", mean(rows))
    by_area = defaultdict(list)
    for r in rows:
        by_area[r["area"]].append(r)
    for area in sorted(by_area):
        line(area, mean(by_area[area]))


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--mode", choices=("bm25", "dense", "dense-ctx", "hybrid", "weighted", "weighted-sweep", "rerank", "all"), default="all")
    parser.add_argument("--alpha", type=float, default=0.5)
    args = parser.parse_args()

    root = Path(__file__).parents[2]

    if args.mode == "weighted-sweep":
        modes = ("weighted",)
    else:
        modes = ("bm25", "dense", "hybrid", "weighted") if args.mode == "all" else (args.mode,)

    # Build lazy-loading index map: only load indexes when modes require them
    indexes: dict[str, Index] = {}
    if any(m in modes for m in ("bm25", "dense", "hybrid", "weighted", "rerank")):
        indexes["default"] = Index.load(root / "data")
    if "dense-ctx" in modes:
        indexes["ctx"] = Index.load(root / "data", embeddings_dir="embeddings_ctx")

    # Use the first available index to load claims (every argparse mode populates one)
    corpus_index = indexes.get("ctx") or indexes.get("default")

    claims, skipped = load_claims(root / "evals" / "golden.jsonl", {c["rule_id"] for c in corpus_index.chunks})
    if not claims:
        sys.exit("no scorable claims — is the corpus ingested and golden.jsonl present?")
    print(f"{len(corpus_index.chunks)} chunks, {len(claims)} claims scored, {skipped} skipped (cited rules not in corpus)")

    queries = [c["query"] for c in claims]
    vectors = (
        query_vectors(queries, root / "data" / "embeddings" / "queries.jsonl")
        if any(m != "bm25" for m in modes)
        else [None] * len(claims)
    )

    if args.mode == "weighted-sweep":
        print("\nweighted-sweep results (alpha tuned on the golden set — overfitting risk, see spec):")
        for alpha in [i / 10 for i in range(11)]:
            rows = [
                score(c["relevant"], retrieve(indexes["default"], "weighted", c["query"], v, alpha=alpha)) | {"area": c["area"]}
                for c, v in zip(claims, vectors)
            ]
            overall = {m: sum(r[m] for r in rows) / len(rows) for m in ["recall@5", "mrr"]}
            print(f"  alpha={alpha:.1f}: recall@5={overall['recall@5']:.3f}, mrr={overall['mrr']:.3f}")
    else:
        for mode in modes:
            index = indexes.get("ctx") if mode == "dense-ctx" else indexes.get("default")
            rows = [
                score(c["relevant"], retrieve(index, mode, c["query"], v, alpha=args.alpha)) | {"area": c["area"]}
                for c, v in zip(claims, vectors)
            ]
            _print_table(mode, rows)


if __name__ == "__main__":
    main()
