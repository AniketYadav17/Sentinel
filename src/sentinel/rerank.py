"""Cross-encoder reranking (optional group: rerank). Scorer is injectable so tests stay offline."""

RERANK_POOL = 20
_MODEL = None


def rerank(query: str, chunks: list[dict], scorer, k: int = 5) -> list[dict]:
    scores = scorer([(query, c["text"]) for c in chunks])
    order = sorted(range(len(chunks)), key=scores.__getitem__, reverse=True)
    return [chunks[i] for i in order[:k]]


def ce_scorer(pairs: list[tuple[str, str]]) -> list[float]:
    global _MODEL
    if _MODEL is None:
        try:
            from sentence_transformers import CrossEncoder
        except ImportError:
            raise SystemExit("rerank group not installed — run: uv sync --group rerank") from None
        _MODEL = CrossEncoder("cross-encoder/ms-marco-MiniLM-L-6-v2")
    return [float(s) for s in _MODEL.predict(pairs)]
