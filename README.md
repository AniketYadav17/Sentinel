# Sentinel

Compliance copilot for UK financial promotions. Audits fintech marketing copy against the [FCA Handbook](https://www.handbook.fca.org.uk/) and flags potential breaches with cited evidence.

The premise: an agentic RAG system in a regulated domain is only deployable if you can prove it works. So the build order is eval-first. The golden dataset came before the pipeline, and the offline suite (unit tests plus the structural-integrity checks on `golden.jsonl` and `holdout.jsonl`) runs in CI on every push and pull request. The metric evals, meaning retrieval, judge accuracy and end-to-end, need live model calls. Those are run by hand and published with their numbers and their misses in [`evals/README.md`](evals/README.md). CI does not gate them.

## Rough shape (will evolve)

- FCA Handbook ingestion with rule-aware chunking (sourcebook / chapter / rule-id metadata)
- Hybrid retrieval: BM25 + dense with score fusion, in Postgres/pgvector
- LangGraph audit workflow: claim decomposition → per-claim retrieval → structured compliance judgement → human-review routing for low-confidence calls
- Eval suite as the backbone: FCA-sourced golden set plus deterministic metrics. The offline half runs in CI; the metric half is run and published by hand.

## Status

Phases 1 to 3 built the pipeline. The ground truth was then rebuilt before production hardening (Phase 4).

- Phase 1: FCA Handbook ingestion via its JSON API, provision-level chunking (CONC 3: 86 chunks), golden dataset written *before* any pipeline code.
- Phase 2: in-memory retrieval (BM25 + dense embeddings + RRF) with a deterministic eval harness. Measured headline: dense-only beat the naive hybrid, so that is what shipped.
- Phase 3: LangGraph audit agent (claim decomposition → per-claim retrieval → structured judgement → human-in-the-loop interrupt gate), judge-accuracy evals, four more measured retrieval arms, and an `fca-handbook` MCP server. The best of those arms beat dense on both gated metrics and was deliberately *not* adopted, because it had been tuned on the eval set.
- Ground truth v2 (2026-08): an audit of the original golden set found its labels were LLM-generated end to end and never human-adjudicated, so its headline metrics measured cross-model agreement rather than accuracy. The set and every number resting on it were deleted in the same commit and replaced with an FCA-sourced dataset. Every label now carries a `label_authority` block quoting the FCA publication that names the pattern and the rule ([`evals/README.md`](evals/README.md)). Scope narrowed to financial promotions.
- Re-baseline v2 (2026-08): Azure OpenAI (`text-embedding-3-large` dense, `gpt-4.1-mini` judge) re-baselined against the v2 golden set alongside a Gemini control, both at 768 dims. The provider swap went through the same seams as every swap before it, one file each for embeddings and chat, with no new dependencies, and the eval suite is what had to prove it still worked. Judge accuracy came out at .971 on both providers with byte-identical confusion matrices: the same one miss, in the same conservative direction, from two unrelated model families. The residency cost is real and measured at dense retrieval (recall@5 -0.069, MRR -0.108, and a full miss on `prominence-review` recall@3), and fusion recovers most of it. End-to-end accuracy was .308, root-caused to a decomposer that extracts only what a promotion *says* and never what it *omits*, while most golden breaches are omission breaches. That omission-blindness finding now has its first fix landed: e2e 0.308 → 0.500 via the retrieval-driven omission scan, with the mechanism and the remaining gap documented in evals/README.
- Multimodal and tuning (2026-08): the image-promotion slice landed. `extract.py` turns a promotion image into a layout-annotated transcription through the same Azure OpenAI deployment as the rest of the pipeline, wired into the CLI via `--media`. An independent, FCA-authored holdout (`evals/holdout.jsonl`) was built through that seam from nine of FG15-04's own 2015 social-media-guidance example images. Its power limits are stated up front: the retrieval comparison rests on claims from a single promotion, and the end-to-end comparison moves in whole-example increments across only nine examples. Adjudicated against that holdout, the omission scan's retrieval depth moved to K=12 on two-dataset evidence, an eval-set sweep peak plus an independent, pre-registered holdout direction. Weighted retrieval fusion stays held, because the same holdout was underpowered to adjudicate it. Full tables, the adjudication protocol and the scored predictions are in [`evals/README.md`](evals/README.md).

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
