import sentinel.blurbs as blurbs

CHUNK = {
    "sourcebook": "CONC",
    "chapter": "3",
    "section": "CONC 3.3",
    "rule_id": "CONC 3.3.1",
    "designation": "R",
    "text": "CONC 3.3.1 R\nFinancial promotions\nmust be clear",
}


def test_blurb_prompt_carries_hierarchy():
    p = blurbs.blurb_prompt(CHUNK)
    assert "CONC 3.3.1" in p and "CONC 3.3" in p and "chapter 3" in p.lower()


def test_contextual_text_prepends_blurb():
    assert blurbs.contextual_text(CHUNK, "Sets the fairness rule.") == "Sets the fairness rule.\n" + CHUNK["text"]


def test_index_load_alternate_embeddings_dir(tmp_path):
    import json

    from sentinel.index import Index

    (tmp_path / "chunks").mkdir()
    (tmp_path / "embeddings_ctx").mkdir()
    (tmp_path / "chunks" / "c.jsonl").write_text(
        json.dumps({"rule_id": "A", "text": "t"}) + "\n", encoding="utf-8"
    )
    (tmp_path / "embeddings_ctx" / "c.jsonl").write_text(
        json.dumps({"rule_id": "A", "vector": [1.0, 0.0]}) + "\n", encoding="utf-8"
    )
    idx = Index.load(tmp_path, embeddings_dir="embeddings_ctx")
    assert idx.chunks[0]["rule_id"] == "A"
