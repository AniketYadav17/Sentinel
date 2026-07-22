"""Ragas faithfulness + context precision over a sample of judge rationales (optional group evals-llm)."""

import json
import os
import random
import sys
from pathlib import Path

from sentinel.eval_judge import RESULTS_PATH

RAGAS_SAMPLE = 50


def run_ragas_mode(root: Path) -> None:
    try:
        from langchain_google_genai import ChatGoogleGenerativeAI
        from ragas import EvaluationDataset, evaluate
        from ragas.llms import LangchainLLMWrapper
        from ragas.metrics import Faithfulness, LLMContextPrecisionWithoutReference
    except ImportError:
        raise SystemExit("ragas group not installed — run: uv sync --group evals-llm") from None
    if not RESULTS_PATH.exists():
        raise SystemExit("no judge results — run python -m sentinel.eval_judge --mode judge first")
    rows = [json.loads(l) for l in RESULTS_PATH.read_text(encoding="utf-8").splitlines() if l]
    rows = random.Random(0).sample(rows, min(RAGAS_SAMPLE, len(rows)))
    dataset = EvaluationDataset.from_list([
        {"user_input": r["claim"], "response": r["pred"]["rationale"], "retrieved_contexts": r["contexts"]}
        for r in rows
    ])
    api_key = os.environ.get("GEMINI_API_KEY") or sys.exit(
        "GEMINI_API_KEY not set — create one at aistudio.google.com and set the env var"
    )
    from sentinel.llm import MODEL

    llm = LangchainLLMWrapper(ChatGoogleGenerativeAI(model=MODEL, google_api_key=api_key))
    result = evaluate(dataset, metrics=[Faithfulness(llm=llm), LLMContextPrecisionWithoutReference(llm=llm)])
    print(f"\n== ragas ({len(rows)} sampled rationales) ==\n{result}")
