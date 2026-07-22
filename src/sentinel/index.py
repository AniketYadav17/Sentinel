"""In-memory hybrid retrieval: hand-rolled Okapi BM25 + cosine + RRF.

The corpus is a few hundred provision chunks, so plain Python lists are
plenty. This class is the seam a pgvector-backed store replaces in Phase 4.
"""

import json
import math
from collections import Counter
from pathlib import Path

K1, B = 1.5, 0.75  # standard Okapi BM25 constants
RRF_K = 60


def tokenize(text: str) -> list[str]:
    return "".join(c.lower() if c.isalnum() else " " for c in text).split()


class Index:
    def __init__(self, chunks: list[dict], vectors: list[list[float]]) -> None:
        if len(chunks) != len(vectors):
            raise ValueError(
                f"{len(chunks)} chunks but {len(vectors)} vectors — re-run python -m sentinel.embed"
            )
        if not chunks:
            raise ValueError("empty chunk data — re-run python -m sentinel.ingest")
        if len({len(v) for v in vectors}) != 1:
            raise ValueError("corpus vectors have mixed dimensions — re-run python -m sentinel.embed")
        self.chunks = chunks
        self.vectors = vectors
        docs = [tokenize(c["text"]) for c in chunks]
        self._tfs = [Counter(d) for d in docs]
        self._lens = [len(d) for d in docs]
        self._avgdl = sum(self._lens) / len(docs)
        self._df = Counter(term for d in docs for term in set(d))

    @classmethod
    def load(cls, data_dir: Path) -> "Index":
        chunk_files = sorted((data_dir / "chunks").glob("*.jsonl"))
        if not chunk_files:
            raise FileNotFoundError("no chunk files in data/chunks — run python -m sentinel.ingest first")
        chunks: list[dict] = []
        vectors: list[list[float]] = []
        for cf in chunk_files:
            ef = data_dir / "embeddings" / cf.name
            if not ef.exists():
                raise FileNotFoundError(f"{ef} missing — run python -m sentinel.embed")
            emb = {r["rule_id"]: r["vector"] for r in _read_jsonl(ef)}
            for c in _read_jsonl(cf):
                if c["rule_id"] not in emb:
                    raise ValueError(f"no embedding for {c['rule_id']} — re-run python -m sentinel.embed")
                chunks.append(c)
                vectors.append(emb[c["rule_id"]])
        return cls(chunks, vectors)

    def search_bm25(self, query: str, k: int = 10) -> list[dict]:
        return [self.chunks[i] for i in self._top(self._bm25_scores(query), k)]

    def search_dense(self, query_vector: list[float], k: int = 10) -> list[dict]:
        return [self.chunks[i] for i in self._top(self._dense_scores(query_vector), k)]

    def search_hybrid(self, query: str, query_vector: list[float], k: int = 10) -> list[dict]:
        fused = [0.0] * len(self.chunks)
        for scores in (self._bm25_scores(query), self._dense_scores(query_vector)):
            for rank, i in enumerate(self._top(scores, len(fused))):
                fused[i] += 1.0 / (RRF_K + rank + 1)
        return [self.chunks[i] for i in self._top(fused, k)]

    def search_weighted(self, query: str, query_vector: list[float], alpha: float = 0.5, k: int = 10) -> list[dict]:
        def norm(scores: list[float]) -> list[float]:
            lo, hi = min(scores), max(scores)
            return [(s - lo) / (hi - lo) if hi > lo else 0.0 for s in scores]

        bm25, dense = norm(self._bm25_scores(query)), norm(self._dense_scores(query_vector))
        return [self.chunks[i] for i in self._top([alpha * d + (1 - alpha) * b for b, d in zip(bm25, dense)], k)]

    def _bm25_scores(self, query: str) -> list[float]:
        n = len(self.chunks)
        scores = [0.0] * n
        for term in tokenize(query):
            df = self._df.get(term)
            if not df:
                continue
            idf = math.log(1 + (n - df + 0.5) / (df + 0.5))
            for i in range(n):
                tf = self._tfs[i][term]
                if tf:
                    scores[i] += idf * tf * (K1 + 1) / (
                        tf + K1 * (1 - B + B * self._lens[i] / self._avgdl)
                    )
        return scores

    def _dense_scores(self, query_vector: list[float]) -> list[float]:
        if len(query_vector) != len(self.vectors[0]):
            raise ValueError(
                f"query vector dim {len(query_vector)} != corpus dim {len(self.vectors[0])}"
                " — re-run python -m sentinel.embed and delete data/embeddings/queries.jsonl"
            )
        # vectors are L2-normalized, so dot product == cosine
        return [sum(a * b for a, b in zip(query_vector, v)) for v in self.vectors]

    @staticmethod
    def _top(scores: list[float], k: int) -> list[int]:
        return sorted(range(len(scores)), key=scores.__getitem__, reverse=True)[:k]


def _read_jsonl(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line]
