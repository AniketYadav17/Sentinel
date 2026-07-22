import asyncio

import pytest

pytest.importorskip("mcp")

from sentinel.mcp_server import make_server


class FakeIndex:
    chunks = [{"rule_id": "CONC 3.3.1", "designation": "R", "section": "CONC 3.3", "text": "clear and fair"}]

    def search_bm25(self, query, k):
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
