# tests/test_index.py
import pytest

from sentinel.index import Index, tokenize

CHUNKS = [
    {"rule_id": "A 1", "text": "the cat sat on the mat"},
    {"rule_id": "A 2", "text": "dogs chase the ball in the park"},
    {"rule_id": "A 3", "text": "representative apr must be shown"},
]
# unit vectors: A 1 -> x-axis, A 2 -> y-axis, A 3 -> diagonal
VECS = [[1.0, 0.0], [0.0, 1.0], [0.7071, 0.7071]]


def make_index() -> Index:
    return Index(CHUNKS, VECS)


def test_tokenize_lowercases_and_strips_punctuation():
    assert tokenize("Cats, DOGS; (mats)") == ["cats", "dogs", "mats"]


def test_bm25_ranks_matching_doc_first():
    assert make_index().search_bm25("representative apr", k=1)[0]["rule_id"] == "A 3"


def test_bm25_unknown_terms_return_k_results_without_crashing():
    assert len(make_index().search_bm25("zzz unseen words", k=3)) == 3


def test_dense_ranks_by_cosine():
    assert make_index().search_dense([1.0, 0.0], k=2)[0]["rule_id"] == "A 1"


def test_hybrid_rrf_rewards_consensus():
    # bm25 for "the cat sat": A 1, A 2, A 3.  dense for [0,1]: A 2, A 3, A 1.
    # RRF(k=60): A 2 = 1/62+1/61 = .03252 beats A 1 = 1/61+1/63 = .03227.
    top = make_index().search_hybrid("the cat sat", [0.0, 1.0], k=3)
    assert [c["rule_id"] for c in top] == ["A 2", "A 1", "A 3"]


def test_mismatched_chunk_and_vector_counts_raise():
    with pytest.raises(ValueError, match="re-run"):
        Index(CHUNKS, VECS[:2])
