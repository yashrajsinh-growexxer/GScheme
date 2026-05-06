"""Evaluate RAG answer faithfulness and hallucination rate with an LLM judge."""
from __future__ import annotations

import argparse
import json
import re
import time
from pathlib import Path
from typing import Any

from evaluation.eval_utils import load_json, time_call, write_json
from evaluation.metrics import average, percentile
from rag_pipeline.config import GROQ_MODEL
from rag_pipeline.inference.generator import chat_response
from rag_pipeline.inference.retriever import build_scheme_context, fetch_scheme_chunks


JUDGE_SYSTEM_PROMPT = """You evaluate government-scheme RAG answers.
Use only the provided context as ground truth.
Mark an answer faithful only if every factual claim is supported by the context.
Return strict compact JSON only:
{"faithful":true,"score":5,"unsupported_claims":[]}
score is 1-5. unsupported_claims lists only unsupported factual claims."""


class RateLimitPauseRequired(RuntimeError):
    """Raised when Groq asks us to wait longer than this eval run should block."""

    def __init__(self, label: str, wait_seconds: float, original: Exception):
        super().__init__(f"{label} hit Groq rate limit; retry after {wait_seconds:.1f}s")
        self.label = label
        self.wait_seconds = wait_seconds
        self.original = original


def _get_judge_llm(model: str, max_tokens: int):
    from langchain_groq import ChatGroq

    return ChatGroq(
        model=model,
        temperature=0,
        max_tokens=max_tokens,
    )


def _extract_json(text: str) -> dict[str, Any]:
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        match = re.search(r"\{.*\}", text, flags=re.DOTALL)
        if not match:
            raise
        return json.loads(match.group(0))


def _retry_after_seconds(exc: Exception) -> float | None:
    message = str(exc)
    match = re.search(r"try again in ([0-9.]+)s", message, flags=re.IGNORECASE)
    if match:
        return float(match.group(1))

    match = re.search(
        r"try again in (?:(?P<minutes>[0-9.]+)m)?(?P<seconds>[0-9.]+)s",
        message,
        flags=re.IGNORECASE,
    )
    if match:
        minutes = float(match.group("minutes") or 0)
        seconds = float(match.group("seconds") or 0)
        return minutes * 60 + seconds

    return None


def _call_with_rate_limit_retries(
    label: str,
    fn,
    *args: Any,
    max_retries: int,
    retry_buffer_seconds: float,
    max_wait_seconds: float,
    **kwargs: Any,
) -> Any:
    for attempt in range(max_retries + 1):
        try:
            return fn(*args, **kwargs)
        except Exception as exc:
            retry_after = _retry_after_seconds(exc)
            is_rate_limit = "rate_limit" in str(exc).lower() or "rate limit" in str(exc).lower()
            if not is_rate_limit or attempt >= max_retries:
                raise

            wait_seconds = (retry_after or min(60.0, 2.0 ** attempt * 5.0)) + retry_buffer_seconds
            if wait_seconds > max_wait_seconds:
                raise RateLimitPauseRequired(label, wait_seconds, exc) from exc

            print(
                f"{label} hit Groq rate limit. "
                f"Waiting {wait_seconds:.1f}s before retry {attempt + 1}/{max_retries}..."
            )
            time.sleep(wait_seconds)


def _compact_context(context: str, limit: int) -> str:
    context = context.strip()
    if len(context) <= limit:
        return context

    head_chars = int(limit * 0.75)
    tail_chars = limit - head_chars
    return (
        context[:head_chars].rstrip()
        + "\n\n[Context trimmed for evaluation token budget]\n\n"
        + context[-tail_chars:].lstrip()
    )


def _load_completed_rows(output_path: str, resume: bool) -> list[dict[str, Any]]:
    if not resume:
        return []
    path = Path(output_path)
    if not path.exists():
        return []
    try:
        with path.open("r", encoding="utf-8") as file:
            payload = json.load(file)
    except (OSError, json.JSONDecodeError):
        return []
    rows = payload.get("rows", [])
    return rows if isinstance(rows, list) else []


def _case_key(case: dict[str, Any], index: int) -> str:
    return str(case.get("id") or f"case-{index}")


def _report_from_rows(
    rows: list[dict[str, Any]],
    total_cases: int,
    settings: dict[str, Any],
    status: str = "completed",
    stop_reason: str | None = None,
) -> dict[str, Any]:
    faithfulness_flags = [1.0 if row.get("faithful") else 0.0 for row in rows]
    hallucination_flags = [
        1.0 if row.get("unsupported_claims") else 0.0
        for row in rows
    ]
    judge_scores = [float(row.get("judge_score", 0)) for row in rows]
    answer_latencies = [
        float(row.get("answer_latency_ms", 0)) + float(row.get("retrieval_ms", 0))
        for row in rows
    ]
    judge_latencies = [float(row.get("judge_latency_ms", 0)) for row in rows]

    report = {
        "metric": "Faithfulness / Hallucination Rate",
        "status": status,
        "stop_reason": stop_reason,
        "cases": total_cases,
        "completed_cases": len(rows),
        "settings": settings,
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
    return report


def judge_faithfulness(
    question: str,
    context: str,
    answer: str,
    judge_model: str,
    judge_max_tokens: int,
    context_chars: int,
    answer_chars: int,
) -> dict[str, Any]:
    llm = _get_judge_llm(judge_model, judge_max_tokens)
    compact_context = _compact_context(context, context_chars)
    compact_answer = answer.strip()[:answer_chars]
    prompt = (
        f"Question:\n{question}\n\n"
        f"Retrieved context:\n{compact_context}\n\n"
        f"Answer:\n{compact_answer}\n\n"
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


def run(
    dataset_path: str,
    output_path: str,
    judge_model: str = GROQ_MODEL,
    judge_max_tokens: int = 180,
    context_chars: int = 2500,
    answer_chars: int = 1200,
    delay_seconds: float = 30.0,
    max_retries: int = 5,
    retry_buffer_seconds: float = 2.0,
    max_wait_seconds: float = 300.0,
    resume: bool = True,
) -> dict:
    cases = load_json(dataset_path)
    settings = {
        "judge_model": judge_model,
        "judge_max_tokens": judge_max_tokens,
        "context_chars": context_chars,
        "answer_chars": answer_chars,
        "delay_seconds": delay_seconds,
        "max_retries": max_retries,
        "retry_buffer_seconds": retry_buffer_seconds,
        "max_wait_seconds": max_wait_seconds,
        "resume": resume,
    }
    rows = _load_completed_rows(output_path, resume)
    completed_keys = {
        str(row.get("case_id"))
        for row in rows
        if row.get("case_id") is not None
    }

    for index, case in enumerate(cases):
        case_id = _case_key(case, index)
        if case_id in completed_keys:
            print(f"Skipping completed case {case_id}")
            continue

        scheme_id = case["scheme_id"]
        question = case["question"]
        profile = case.get("profile", {})
        history = case.get("history", [])

        try:
            chunks, retrieval_ms = time_call(fetch_scheme_chunks, scheme_id)
            context = build_scheme_context(chunks)
            answer, answer_ms = time_call(
                _call_with_rate_limit_retries,
                "Answer generation",
                chat_response,
                question,
                profile,
                scheme_id,
                history,
                max_retries=max_retries,
                retry_buffer_seconds=retry_buffer_seconds,
                max_wait_seconds=max_wait_seconds,
            )
            judge_result, judge_ms = time_call(
                _call_with_rate_limit_retries,
                "Faithfulness judge",
                judge_faithfulness,
                question,
                context,
                answer,
                judge_model,
                judge_max_tokens,
                context_chars,
                answer_chars,
                max_retries=max_retries,
                retry_buffer_seconds=retry_buffer_seconds,
                max_wait_seconds=max_wait_seconds,
            )
        except RateLimitPauseRequired as exc:
            report = _report_from_rows(
                rows,
                len(cases),
                settings,
                status="stopped_rate_limited",
                stop_reason=(
                    f"{exc.label} requested a wait of {exc.wait_seconds:.1f}s. "
                    "The partial report was saved; rerun the same command later to resume."
                ),
            )
            write_json(output_path, report)
            print(report["stop_reason"])
            return report

        faithful = 1.0 if judge_result["faithful"] else 0.0
        hallucinated = 1.0 if judge_result["unsupported_claims"] else 0.0
        rows.append(
            {
                "case_id": case_id,
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
        completed_keys.add(case_id)

        write_json(
            output_path,
            _report_from_rows(rows, len(cases), settings, status="partial"),
        )

        if delay_seconds > 0 and index != len(cases) - 1:
            time.sleep(delay_seconds)

    report = _report_from_rows(rows, len(cases), settings, status="completed")
    write_json(output_path, report)
    return report


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dataset", default="evaluation/datasets/chat_eval.sample.json")
    parser.add_argument("--output", default="evaluation/reports/generation_report.json")
    parser.add_argument("--judge-model", default=GROQ_MODEL)
    parser.add_argument("--judge-max-tokens", type=int, default=180)
    parser.add_argument("--context-chars", type=int, default=2500)
    parser.add_argument("--answer-chars", type=int, default=1200)
    parser.add_argument("--delay-seconds", type=float, default=30.0)
    parser.add_argument("--max-retries", type=int, default=5)
    parser.add_argument("--retry-buffer-seconds", type=float, default=2.0)
    parser.add_argument("--max-wait-seconds", type=float, default=300.0)
    parser.add_argument("--no-resume", action="store_true")
    args = parser.parse_args()

    report = run(
        args.dataset,
        args.output,
        judge_model=args.judge_model,
        judge_max_tokens=args.judge_max_tokens,
        context_chars=args.context_chars,
        answer_chars=args.answer_chars,
        delay_seconds=args.delay_seconds,
        max_retries=args.max_retries,
        retry_buffer_seconds=args.retry_buffer_seconds,
        max_wait_seconds=args.max_wait_seconds,
        resume=not args.no_resume,
    )
    print(f"Faithfulness: {report['faithfulness']}")
    print(f"Hallucination rate: {report['hallucination_rate']}")
    print(f"Report written to {args.output}")


if __name__ == "__main__":
    main()
