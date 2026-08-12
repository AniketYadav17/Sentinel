# Sentinel

Compliance copilot for UK financial promotions. Audits fintech marketing copy against the [FCA Handbook](https://www.handbook.fca.org.uk/) and flags potential breaches with cited evidence.

The premise: agentic RAG systems in regulated domains are only deployable if you can prove they work. So this is built eval-first — the golden dataset and regression gate come before the pipeline, and every retrieval/prompt/model change has to pass the eval suite in CI before it merges.

## Rough shape (will evolve)

- FCA Handbook ingestion with rule-aware chunking (sourcebook / chapter / rule-id metadata)
- Hybrid retrieval: BM25 + dense with score fusion, in Postgres/pgvector
- LangGraph audit workflow: claim decomposition → per-claim retrieval → structured compliance judgement → human-review routing for low-confidence calls
- Eval suite as the backbone: FCA-sourced golden set + deterministic metrics, wired into CI as a merge gate

## Status

Phases 1–3 built the pipeline; the ground truth was then rebuilt before production hardening (Phase 4).

- **Phase 1** — FCA Handbook ingestion via its JSON API, provision-level chunking (CONC 3: 86 chunks), golden dataset written *before* any pipeline code.
- **Phase 2** — in-memory retrieval (BM25 + dense embeddings + RRF) with a deterministic eval harness. Measured headline: dense-only beat the naive hybrid, so that's what shipped.
- **Phase 3** — LangGraph audit agent (claim decomposition → per-claim retrieval → structured judgement → human-in-the-loop interrupt gate), judge-accuracy evals, four more measured retrieval arms (the best one beat dense on both gated metrics and was deliberately *not* adopted — it was tuned on the eval set), and an `fca-handbook` MCP server.
- **Ground truth v2 (2026-08)** — an audit of the original golden set found its labels were LLM-generated end to end and never human-adjudicated, so its headline metrics measured cross-model agreement, not accuracy. The set and every number resting on it were deleted in the same commit and replaced with an FCA-sourced dataset: every label now carries a `label_authority` block quoting the FCA publication that names the pattern and the rule ([`evals/README.md`](evals/README.md)). Scope narrowed to financial promotions.
- **Re-baseline v2 (2026-08)** — Azure OpenAI (`text-embedding-3-large` dense, `gpt-4.1-mini` judge) re-baselined against the v2 golden set alongside a Gemini control, both at 768 dims. The provider swap went through the same seams as every swap before it — one file each for embeddings and chat, zero new dependencies — and the eval suite is what had to prove it still worked. Judge accuracy: **.971 on both providers, with byte-identical confusion matrices** — the same one miss, in the same conservative direction, from two unrelated model families. The residency cost is real and measured at dense retrieval (recall@5 −0.069, MRR −0.108, and a full miss on `prominence-review` recall@3) but fusion recovers most of it. End-to-end accuracy was **.308**, root-caused to a decomposer that extracts only what a promotion *says* and never what it *omits*, while most golden breaches are omission breaches. That omission-blindness finding now has its first fix landed: e2e **0.308 → 0.500** via the retrieval-driven omission scan — mechanism and remaining gap documented in evals/README.
- **Multimodal + tuning (2026-08)** — the image-promotion slice landed: `extract.py` turns a promotion image into a layout-annotated transcription through the same Azure OpenAI deployment as the rest of the pipeline, wired into the CLI via `--media`. An independent, FCA-authored holdout (`evals/holdout.jsonl`) was built through that seam from nine of FG15-04's own 2015 social-media-guidance example images, with its power limits disclosed up front rather than glossed over (the retrieval comparison rests on claims from a single promotion; the end-to-end comparison moves in whole-example increments across only nine examples). Adjudicated against that holdout, the omission scan's retrieval depth moved to **K=12** on two-dataset evidence — an eval-set sweep peak plus an independent, pre-registered holdout direction. Weighted retrieval fusion stays **held**: the same holdout was underpowered to adjudicate it, and that limit is stated rather than smoothed over. Full tables, the adjudication protocol, and the scored predictions: [`evals/README.md`](evals/README.md).

Try it (needs `AZURE_OPENAI_ENDPOINT`, `AZURE_OPENAI_API_KEY`, `AZURE_OPENAI_EMBED_DEPLOYMENT` (default `sentinel-embed`), `AZURE_OPENAI_CHAT_DEPLOYMENT` (default `sentinel-judge`)):

```
uv sync
uv run python -m sentinel.ingest CONC 3 && uv run python -m sentinel.embed
uv run python -m sentinel.audit "Get a loan in 5 minutes! No credit check impact!"
uv run python -m sentinel.eval_retrieval --mode all
uv run python -m sentinel.eval_judge --mode judge
```

## Note

Portfolio/research project. Not legal or compliance advice.
