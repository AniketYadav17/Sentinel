"""fca-handbook MCP server: read-only handbook retrieval for any MCP client (optional group: mcp).

Usage: python -m sentinel.mcp_server   (stdio transport)
Dense mode needs GEMINI_API_KEY for query embedding; bm25 mode is fully offline.
"""

from pathlib import Path
from typing import Literal

from mcp.server.fastmcp import FastMCP


def make_server(index) -> FastMCP:
    server = FastMCP("fca-handbook")

    @server.tool()
    def search_handbook(query: str, mode: Literal["dense", "bm25"] = "dense", k: int = 5) -> list[dict]:
        """Search FCA Handbook provisions. mode: dense (semantic, needs GEMINI_API_KEY) or bm25 (offline)."""
        if mode == "dense":
            from sentinel.embed import embed_texts

            try:
                chunks = index.search_dense(embed_texts([query])[0], k)
            except SystemExit as e:
                raise RuntimeError(str(e)) from None
        elif mode == "bm25":
            chunks = index.search_bm25(query, k)
        else:
            raise ValueError(f"unknown mode {mode!r} — use dense or bm25")
        return [{"rule_id": c["rule_id"], "designation": c["designation"], "section": c["section"], "text": c["text"]} for c in chunks]

    @server.tool()
    def get_provision(rule_id: str) -> dict:
        """Fetch one provision chunk by exact rule id, e.g. 'CONC 3.3.1'."""
        for c in index.chunks:
            if c["rule_id"] == rule_id:
                return c
        raise ValueError(f"unknown rule_id {rule_id!r}")

    return server


def main() -> None:
    from sentinel.index import Index

    make_server(Index.load(Path(__file__).parents[2] / "data")).run()


if __name__ == "__main__":
    main()
