"""Evaluate RAG answer faithfulness and hallucination rate with an LLM judge."""
from __future__ import annotations

import argparse
import json
import re
from typing import Any

from evaluation.eval_utils import load_json, time_call, write_json
from evaluation.metrics import average, percentile
from rag_pipeline.config import GROQ_MODEL
from rag_pipeline.inference.generator import chat_response
from rag_pipeline.inference.retriever import build_scheme_context, fetch_scheme_chunks


JUDGE_SYSTEM_PROMPT = """You evaluate government-scheme RAG answers.
Use only the provided context as ground truth.
Mark an answer faithful only if every factual claim is supported by the context.
Return strict JSON with these keys:
{
  "faithful": true,
  "score": 1,
  "unsupported_claims": []
}
score must be an integer from 1 to 5, where 5 means fully supported.
unsupported_claims must list unsupported or contradicted factual claims."""


def _get_judge_llm():
    from langchain_groq import ChatGroq

    return ChatGroq(
        model=GROQ_MODEL,
        temperature=0,
        max_tokens=700,
    )


def _extract_json(text: str) -> dict[str, Any]:
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        match = re.search(r"\{.*\}", text, flags=re.DOTALL)
        if not match:
            raise
        return json.loads(match.group(0))


def judge_faithfulness(question: str, context: str, answer: str) -> dict[str, Any]:
    llm = _get_judge_llm()
    prompt = (
        f"Question:\n{question}\n\n"
        f"Retrieved context:\n{context[:12000]}\n\n"
        f"Answer:\n{answer}\n\n"
        "Evaluate the answer now."
    )
    response = llm.invoke(
        [
            ("system", JUDGE_SYSTEM_PROMPT),
            ("human", prompt),
        ]
    )
    parsed = _extract_json(response.content)
    unsupported = parsed.get("unsupported_claims") or []
    return {
        "faithful": bool(parsed.get("faithful")) and not unsupported,
        "score": int(parsed.get("score", 1)),
        "unsupported_claims": unsupported,
        "raw_judge_response": response.content,
    }


def run(dataset_path: str, output_path: str) -> dict:
    cases = load_json(dataset_path)
    rows = []
    faithfulness_flags = []
    hallucination_flags = []
    judge_scores = []
    answer_latencies = []
    judge_latencies = []

    for case in cases:
        scheme_id = case["scheme_id"]
        question = case["question"]
        profile = case.get("profile", {})
        history = case.get("history", [])

        chunks, retrieval_ms = time_call(fetch_scheme_chunks, scheme_id)
        context = build_scheme_context(chunks)
        answer, answer_ms = time_call(chat_response, question, profile, scheme_id, history)
        judge_result, judge_ms = time_call(judge_faithfulness, question, context, answer)

        faithful = 1.0 if judge_result["faithful"] else 0.0
        hallucinated = 1.0 if judge_result["unsupported_claims"] else 0.0
        faithfulness_flags.append(faithful)
        hallucination_flags.append(hallucinated)
        judge_scores.append(judge_result["score"])
        answer_latencies.append(answer_ms + retrieval_ms)
        judge_latencies.append(judge_ms)

        rows.append(
            {
                "case_id": case.get("id"),
                "scheme_id": scheme_id,
                "question": question,
                "answer": answer,
                "faithful": judge_result["faithful"],
                "judge_score": judge_result["score"],
                "unsupported_claims": judge_result["unsupported_claims"],
                "retrieval_ms": round(retrieval_ms, 2),
                "answer_latency_ms": round(answer_ms, 2),
                "judge_latency_ms": round(judge_ms, 2),
            }
        )

    report = {
        "metric": "Faithfulness / Hallucination Rate",
        "cases": len(cases),
        "faithfulness": round(average(faithfulness_flags), 4),
        "hallucination_rate": round(average(hallucination_flags), 4),
        "avg_judge_score": round(average(judge_scores), 2),
        "answer_latency": {
            "p50_ms": round(percentile(answer_latencies, 0.50), 2),
            "p95_ms": round(percentile(answer_latencies, 0.95), 2),
        },
        "judge_latency": {
            "p50_ms": round(percentile(judge_latencies, 0.50), 2),
            "p95_ms": round(percentile(judge_latencies, 0.95), 2),
        },
        "rows": rows,
    }
    write_json(output_path, report)
    return report


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dataset", default="evaluation/datasets/chat_eval.sample.json")
    parser.add_argument("--output", default="evaluation/reports/generation_report.json")
    args = parser.parse_args()

    report = run(args.dataset, args.output)
    print(f"Faithfulness: {report['faithfulness']}")
    print(f"Hallucination rate: {report['hallucination_rate']}")
    print(f"Report written to {args.output}")


if __name__ == "__main__":
    main()
