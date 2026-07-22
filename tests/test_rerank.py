from sentinel.rerank import rerank

CHUNKS = [{"rule_id": "A", "text": "aaa"}, {"rule_id": "B", "text": "bb"}, {"rule_id": "C", "text": "c"}]


def test_rerank_orders_by_scorer_and_truncates():
    scorer = lambda pairs: [float(len(t)) for _, t in pairs]  # favors longer text
    out = rerank("q", CHUNKS, scorer, k=2)
    assert [c["rule_id"] for c in out] == ["A", "B"]


def test_rerank_passes_query_text_pairs():
    seen = []
    rerank("the query", CHUNKS, lambda pairs: (seen.extend(pairs), [0.0] * len(pairs))[1], k=1)
    assert seen[0] == ("the query", "aaa")
