import asyncio

import pytest

pytest.importorskip("mcp")

from sentinel.mcp_server import make_server


class FakeIndex:
    chunks = [{"rule_id": "CONC 3.3.1", "designation": "R", "section": "CONC 3.3", "text": "clear and fair"}]

    def search_bm25(self, query, k):
        return self.chunks[:k]

    def search_dense(self, vector, k):
        return self.chunks[:k]


def test_tools_registered():
    server = make_server(FakeIndex())
    tools = asyncio.run(server.list_tools())
    assert {t.name for t in tools} == {"search_handbook", "get_provision"}


def test_get_provision_and_unknown_id():
    server = make_server(FakeIndex())
    assert asyncio.run(server.call_tool("get_provision", {"rule_id": "CONC 3.3.1"}))
    with pytest.raises(Exception, match="unknown rule_id"):
        asyncio.run(server.call_tool("get_provision", {"rule_id": "NOPE"}))


def test_search_handbook_bm25_dispatch():
    server = make_server(FakeIndex())
    result = asyncio.run(server.call_tool("search_handbook", {"query": "fair", "mode": "bm25", "k": 1}))
    # call_tool returns (content_blocks, structured_output); structured_output is {"result": [...]}
    # for a tool annotated -> list[dict].
    _, structured = result
    assert structured["result"][0]["rule_id"] == "CONC 3.3.1"


def test_search_handbook_unknown_mode_raises():
    server = make_server(FakeIndex())
    with pytest.raises(Exception, match="Input should be 'dense' or 'bm25'|unknown mode"):
        asyncio.run(server.call_tool("search_handbook", {"query": "q", "mode": "nope"}))


def test_search_handbook_dense_without_key_raises_runtimeerror_not_systemexit(monkeypatch):
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    server = make_server(FakeIndex())
    with pytest.raises(Exception, match="GEMINI_API_KEY"):
        asyncio.run(server.call_tool("search_handbook", {"query": "q"}))
    # the assertion that matters: this must NOT raise SystemExit — pytest.raises(Exception) would not catch SystemExit, so passing proves the guard


def test_search_handbook_dense_dispatch(monkeypatch):
    import sentinel.embed

    monkeypatch.setattr(sentinel.embed, "embed_texts", lambda texts, task_type: [[1.0, 0.0]])
    server = make_server(FakeIndex())
    result = asyncio.run(server.call_tool("search_handbook", {"query": "q", "mode": "dense", "k": 1}))
    _, structured = result
    assert structured["result"][0]["rule_id"] == "CONC 3.3.1"
