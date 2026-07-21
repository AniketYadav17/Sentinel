# Sentinel

Compliance copilot for UK fintech communications. Audits marketing copy, T&Cs and support responses against the [FCA Handbook](https://www.handbook.fca.org.uk/) and flags potential breaches with cited evidence.

The premise: agentic RAG systems in regulated domains are only deployable if you can prove they work. So this is built eval-first — the golden dataset and regression gate come before the pipeline, and every retrieval/prompt/model change has to pass the eval suite in CI before it merges.

## Rough shape (will evolve)

- FCA Handbook ingestion with rule-aware chunking (sourcebook / chapter / rule-id metadata)
- Hybrid retrieval: BM25 + dense with reranking, in Postgres/pgvector
- LangGraph audit workflow: claim decomposition → per-claim retrieval → structured compliance judgement → human-review routing for low-confidence calls
- Eval suite as the backbone: hand-labelled golden set + Ragas metrics, wired into CI as a merge gate

## Status

Just started — laying down the scaffold. First milestone: a hand-labelled golden set of audit examples *before* any pipeline code. Eval-first, in that order on purpose.

## Note

Portfolio/research project. Not legal or compliance advice.
