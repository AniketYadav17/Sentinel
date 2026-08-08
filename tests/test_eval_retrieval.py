import hashlib
import json

import pytest

from sentinel.eval_retrieval import load_claims, normalize_rule_id, query_vectors, retrieve, score
from sentinel.index import Index


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("CONC 3.3.1R", "CONC 3.3.1"),
        ("CONC 3.3.10G", "CONC 3.3.10"),
        ("CONC 3.3.4G(2)", "CONC 3.3.4"),
        ("CONC 3.5.7R(1)(c)", "CONC 3.5.7"),
        ("CONC 3.3.1R(1A)", "CONC 3.3.1"),
        ("CONC 3.3.1", "CONC 3.3.1"),
        ("CONC 5A.2.1R", "CONC 5A.2.1"),
        ("CONC 3.3.9AR", "CONC 3.3.9A"),
    ],
)
def test_normalize_rule_id(raw, expected):
    assert normalize_rule_id(raw) == expected


def test_score_hand_computed():
    s = score({"A", "B"}, ["X", "A", "Y", "Z", "Q", "R", "S", "T", "U", "B"])
    assert s["recall@3"] == 0.5   # A of {A,B} in top 3
    assert s["hit@3"] == 1.0
    assert s["recall@5"] == 0.5
    assert s["recall@10"] == 1.0  # B arrives at rank 10
    assert s["mrr"] == 0.5        # first relevant at rank 2


def test_score_no_relevant_retrieved():
    s = score({"A"}, ["X", "Y"])
    assert s["recall@3"] == 0.0
    assert s["hit@10"] == 0.0
    assert s["mrr"] == 0.0


def test_load_claims_skips_out_of_corpus_and_counts(tmp_path):
    golden = tmp_path / "golden.jsonl"
    example = {
        "area": "misleading-3.3",
        "claims": [
            {"claim": "guaranteed approval", "rules": ["CONC 3.3.3R", "CONC 99.1.1R"]},
            {"claim": "cites nothing in corpus", "rules": ["CONC 99.1.1R"]},
        ],
    }
    golden.write_text(json.dumps(example) + "\n", encoding="utf-8")
    claims, skipped = load_claims(golden, corpus_rule_ids={"CONC 3.3.3"})
    assert skipped == 1
    assert claims == [
        {"query": "guaranteed approval", "relevant": {"CONC 3.3.3"}, "area": "misleading-3.3"}
    ]


CHUNKS = [
    {"rule_id": "CONC 3.3.3", "text": "guaranteed approval regardless of status"},
    {"rule_id": "CONC 3.4.1", "text": "high cost short term credit risk warning"},
]
VECS = [[1.0, 0.0], [0.0, 1.0]]


def test_retrieve_dispatches_by_mode():
    idx = Index(CHUNKS, VECS)
    assert retrieve(idx, "bm25", "guaranteed approval", None, k=1) == ["CONC 3.3.3"]
    assert retrieve(idx, "dense", "anything", [0.0, 1.0], k=1) == ["CONC 3.4.1"]
    assert retrieve(idx, "hybrid", "guaranteed approval", [1.0, 0.0], k=1) == ["CONC 3.3.3"]


def test_query_vectors_caches_and_reuses(tmp_path, monkeypatch):
    calls = []

    def fake_embed(texts, task_type):
        calls.append(list(texts))
        assert task_type == "RETRIEVAL_QUERY"
        return [[1.0, 0.0]] * len(texts)

    monkeypatch.setattr("sentinel.eval_retrieval.embed_texts", fake_embed)
    cache = tmp_path / "queries.jsonl"

    first = query_vectors(["q1", "q2"], cache)
    assert first == [[1.0, 0.0], [1.0, 0.0]]
    assert calls == [["q1", "q2"]]

    second = query_vectors(["q1", "q2", "q3"], cache)  # only q3 is a miss
    assert second == [[1.0, 0.0]] * 3
    assert calls == [["q1", "q2"], ["q3"]]


def test_query_vector_cache_key_is_model_and_dim_scoped(tmp_path, monkeypatch):
    """A vector cached under the pre-fix text-only key must NOT be served after the fix."""
    calls = []

    def fake_embed(texts, task_type):
        calls.append(list(texts))
        return [[1.0, 0.0]] * len(texts)

    monkeypatch.setattr("sentinel.eval_retrieval.embed_texts", fake_embed)
    cache = tmp_path / "queries.jsonl"
    stale_key = hashlib.sha256("q1".encode()).hexdigest()  # old key scheme: text only
    cache.write_text(json.dumps({"sha": stale_key, "vector": [9.9, 9.9]}) + "\n", encoding="utf-8")

    vectors = query_vectors(["q1"], cache)

    assert calls == [["q1"]]        # stale entry was a miss -> re-embedded
    assert vectors == [[1.0, 0.0]]  # the stale vector was never served
