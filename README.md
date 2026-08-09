# Sentinel

Compliance copilot for UK financial promotions. Audits fintech marketing copy against the [FCA Handbook](https://www.handbook.fca.org.uk/) and flags potential breaches with cited evidence.

The premise: agentic RAG systems in regulated domains are only deployable if you can prove they work. So this is built eval-first — the golden dataset and regression gate come before the pipeline, and every retrieval/prompt/model change has to pass the eval suite in CI before it merges.

## Rough shape (will evolve)

- FCA Handbook ingestion with rule-aware chunking (sourcebook / chapter / rule-id metadata)
- Hybrid retrieval: BM25 + dense with reranking, in Postgres/pgvector
- LangGraph audit workflow: claim decomposition → per-claim retrieval → structured compliance judgement → human-review routing for low-confidence calls
- Eval suite as the backbone: FCA-sourced golden set + deterministic metrics, wired into CI as a merge gate

## Status

Phases 1–3 built the pipeline; the ground truth was then rebuilt before production hardening (Phase 4).

- **Phase 1** — FCA Handbook ingestion via its JSON API, provision-level chunking (CONC 3: 86 chunks), golden dataset written *before* any pipeline code.
- **Phase 2** — in-memory retrieval (BM25 + dense embeddings + RRF) with a deterministic eval harness. Measured headline: dense-only beat the naive hybrid, so that's what shipped.
- **Phase 3** — LangGraph audit agent (claim decomposition → per-claim retrieval → structured judgement → human-in-the-loop interrupt gate), judge-accuracy evals, four more measured retrieval arms (the best one beat dense on both gated metrics and was deliberately *not* adopted — it was tuned on the eval set), and an `fca-handbook` MCP server.
- **Ground truth v2 (2026-08)** — an audit of the original golden set found its labels were LLM-generated end to end and never human-adjudicated, so its headline metrics measured cross-model agreement, not accuracy. The set and every number resting on it were deleted in the same commit and replaced with an FCA-sourced dataset: every label now carries a `label_authority` block quoting the FCA publication that names the pattern and the rule ([`evals/README.md`](evals/README.md)). Scope narrowed to financial promotions. Metrics re-baseline lands with the Azure provider swap.

Try it (needs `GEMINI_API_KEY`):

```
uv sync
uv run python -m sentinel.ingest CONC 3 && uv run python -m sentinel.embed
uv run python -m sentinel.audit "Get a loan in 5 minutes! No credit check impact!"
uv run python -m sentinel.eval_retrieval --mode all
uv run python -m sentinel.eval_judge --mode judge
```

## Note

Portfolio/research project. Not legal or compliance advice.
