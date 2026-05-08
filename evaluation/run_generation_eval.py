"""Evaluate chat answers with embedding metrics or an optional LLM judge."""
from __future__ import annotations

import argparse
import json
import math
import re
import time
from pathlib import Path
from typing import Any

from evaluation.eval_utils import load_json, time_call, write_json
from evaluation.metrics import average, percentile
from rag_pipeline.config import GROQ_MODEL
from rag_pipeline.inference.generator import chat_response
from rag_pipeline.inference.retriever import build_scheme_context, fetch_scheme_chunks
from rag_pipeline.knowledge_base.embeddings import get_embedding_model


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


def _split_sentences(text: str) -> list[str]:
    normalized = re.sub(r"\s+", " ", text or "").strip()
    if not normalized:
        return []
    parts = re.split(r"(?<=[.!?।])\s+|\n+", normalized)
    return [part.strip() for part in parts if len(part.strip()) > 12]


def _clean_markdown_text(text: str) -> str:
    cleaned = text or ""
    cleaned = re.sub(r"\[([^\]]+)\]\([^)]+\)", r"\1", cleaned)
    cleaned = re.sub(r"[*_`#>]+", " ", cleaned)
    cleaned = re.sub(r"\s+", " ", cleaned)
    return cleaned.strip()


def _split_answer_units(text: str, min_chars: int = 45, max_chars: int = 700) -> list[str]:
    """
    Split an answer into semantic units instead of raw sentences.

    Markdown lists and numbered steps often produce fragments like "Here are
    the steps: 1.". This parser keeps nearby fragments together so grounding is
    judged at a useful claim/block level.
    """
    normalized = (text or "").replace("\r\n", "\n").strip()
    if not normalized:
        return []

    normalized = re.sub(r"(?m)^\s*(#{1,6})\s*", "", normalized)
    normalized = re.sub(r"(?m)^\s*[-*•]\s+", "\n", normalized)
    normalized = re.sub(r"(?m)^\s*(\d+)[.)]\s+", r"\n\1. ", normalized)
    raw_parts = re.split(r"\n{2,}|\n|(?<=[.!?।])\s+", normalized)

    units: list[str] = []
    current = ""
    for raw_part in raw_parts:
        part = _clean_markdown_text(raw_part)
        if not part:
            continue

        is_fragment = (
            len(part) < min_chars
            or bool(re.search(r"[:;]\s*$", part))
            or bool(re.search(r"\b\d+[.)]\s*$", part))
        )
        candidate = f"{current} {part}".strip() if current else part

        if current and (is_fragment or len(candidate) <= max_chars):
            current = candidate
            continue

        if current:
            units.append(current)
        current = part

    if current:
        units.append(current)

    merged: list[str] = []
    for unit in units:
        if merged and len(unit) < min_chars:
            merged[-1] = f"{merged[-1]} {unit}".strip()
        else:
            merged.append(unit)

    return merged


def _cosine(a: list[float], b: list[float]) -> float:
    numerator = sum(x * y for x, y in zip(a, b))
    norm_a = math.sqrt(sum(x * x for x in a))
    norm_b = math.sqrt(sum(y * y for y in b))
    if not norm_a or not norm_b:
        return 0.0
    return numerator / (norm_a * norm_b)


def _clamp(value: float, low: float = 0.0, high: float = 1.0) -> float:
    return max(low, min(high, value))


def _soft_similarity_score(score: float, weak_threshold: float, strong_threshold: float) -> float:
    if score <= weak_threshold:
        return 0.0
    if score >= strong_threshold:
        return 1.0
    return (score - weak_threshold) / (strong_threshold - weak_threshold)


def _embed_texts(texts: list[str]) -> list[list[float]]:
    if not texts:
        return []
    return get_embedding_model().embed_documents(texts)


def _chunk_texts(chunks: list[dict[str, Any]], max_chunks: int, max_chars_per_chunk: int) -> list[str]:
    texts: list[str] = []
    for chunk in chunks:
        text = str(chunk.get("text") or "").strip()
        if text:
            texts.append(text[:max_chars_per_chunk])
        if len(texts) >= max_chunks:
            break
    return texts


def _combined_text(texts: list[str], max_chars: int) -> str:
    return "\n\n".join(texts).strip()[:max_chars]


def _stringify_reference_value(value: Any, label: str | None = None) -> list[str]:
    """Flatten official reference answers while preserving useful section labels."""
    if value is None:
        return []

    if isinstance(value, str):
        cleaned = value.strip()
        if not cleaned:
            return []
        return [f"{label}: {cleaned}" if label else cleaned]

    if isinstance(value, dict):
        parts: list[str] = []
        for key, nested_value in value.items():
            key_label = str(key).replace("_", " ").strip()
            parts.extend(_stringify_reference_value(nested_value, key_label or label))
        return parts

    if isinstance(value, list):
        parts: list[str] = []
        for item in value:
            parts.extend(_stringify_reference_value(item, label))
        return parts

    cleaned = str(value).strip()
    if not cleaned:
        return []
    return [f"{label}: {cleaned}" if label else cleaned]


def _normalize_reference_answer(reference_answer: Any) -> str | None:
    """Accept string, list, or dictionary reference answers from official sources."""
    parts = _stringify_reference_value(reference_answer)
    return "\n".join(parts) if parts else None


def evaluate_embedding_metrics(
    answer: str,
    chunks: list[dict[str, Any]],
    reference_answer: Any,
    grounding_threshold: float,
    max_chunks: int,
    max_chars_per_chunk: int,
    soft_threshold: float,
    strong_threshold: float,
    global_weight: float,
) -> dict[str, Any]:
    """Compute RAG grounding and reference-answer correctness without an LLM judge."""
    answer_units = _split_answer_units(answer)
    context_texts = _chunk_texts(chunks, max_chunks, max_chars_per_chunk)

    unit_grounding: list[dict[str, Any]] = []
    supported_count = 0
    unit_scores: list[float] = []
    if answer_units and context_texts:
        unit_embeddings = _embed_texts(answer_units)
        context_embeddings = _embed_texts(context_texts)
        for unit, unit_embedding in zip(answer_units, unit_embeddings):
            similarities = [
                _cosine(unit_embedding, context_embedding)
                for context_embedding in context_embeddings
            ]
            best_score = max(similarities) if similarities else 0.0
            best_index = similarities.index(best_score) if similarities else -1
            supported = best_score >= grounding_threshold
            supported_count += 1 if supported else 0
            soft_score = _soft_similarity_score(best_score, soft_threshold, strong_threshold)
            unit_scores.append(soft_score)
            unit_grounding.append(
                {
                    "answer_unit": unit,
                    "max_context_similarity": round(best_score, 4),
                    "soft_support_score": round(soft_score, 4),
                    "supported": supported,
                    "best_context_preview": context_texts[best_index][:500] if best_index >= 0 else "",
                }
            )

    total_units = len(answer_units)
    local_grounding_score = average(unit_scores)
    global_context_similarity = None
    if answer.strip() and context_texts:
        answer_vec, context_vec = _embed_texts(
            [
                _clean_markdown_text(answer),
                _combined_text(context_texts, max_chunks * max_chars_per_chunk),
            ]
        )
        global_context_similarity = _cosine(answer_vec, context_vec)

    global_grounding_score = (
        _soft_similarity_score(global_context_similarity, soft_threshold, strong_threshold)
        if global_context_similarity is not None
        else 0.0
    )
    blended_grounding = (
        (1 - global_weight) * local_grounding_score
        + global_weight * global_grounding_score
    )
    rag_grounding_score = _clamp(blended_grounding)
    hallucination_risk = 1.0 - rag_grounding_score if total_units else 0.0

    correctness_score = None
    global_reference_similarity = None
    normalized_reference = _normalize_reference_answer(reference_answer)
    if normalized_reference and answer.strip():
        answer_text = _clean_markdown_text(answer)
        answer_vec, reference_vec = _embed_texts([answer_text, normalized_reference])
        global_reference_similarity = _cosine(answer_vec, reference_vec)
        correctness_score = global_reference_similarity

    return {
        "rag_grounding_score": round(rag_grounding_score, 4),
        "hallucination_risk": round(hallucination_risk, 4),
        "answer_correctness_score": round(correctness_score, 4) if correctness_score is not None else None,
        "local_grounding_score": round(local_grounding_score, 4),
        "global_context_similarity": round(global_context_similarity, 4) if global_context_similarity is not None else None,
        "global_grounding_score": round(global_grounding_score, 4),
        "global_reference_similarity": round(global_reference_similarity, 4) if global_reference_similarity is not None else None,
        "grounded_sentence_count": supported_count,
        "answer_sentence_count": total_units,
        "answer_unit_count": total_units,
        "reference_answer_text": normalized_reference,
        "grounding_threshold": grounding_threshold,
        "soft_threshold": soft_threshold,
        "strong_threshold": strong_threshold,
        "global_weight": global_weight,
        "sentence_grounding": unit_grounding,
        "answer_unit_grounding": unit_grounding,
    }


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
    grounding_scores = [
        float(row["rag_grounding_score"])
        for row in rows
        if row.get("rag_grounding_score") is not None
    ]
    hallucination_risks = [
        float(row["hallucination_risk"])
        for row in rows
        if row.get("hallucination_risk") is not None
    ]
    correctness_scores = [
        float(row["answer_correctness_score"])
        for row in rows
        if row.get("answer_correctness_score") is not None
    ]
    faithfulness_flags = [1.0 if row.get("faithful") else 0.0 for row in rows if "faithful" in row]
    hallucination_flags = [
        1.0 if row.get("unsupported_claims") else 0.0
        for row in rows
        if "unsupported_claims" in row
    ]
    judge_scores = [float(row.get("judge_score", 0)) for row in rows if row.get("judge_score") is not None]
    answer_latencies = [
        float(row.get("answer_latency_ms", 0)) + float(row.get("retrieval_ms", 0))
        for row in rows
    ]
    judge_latencies = [float(row.get("judge_latency_ms", 0)) for row in rows if row.get("judge_latency_ms") is not None]

    report = {
        "metric": "Chat Answer Evaluation",
        "status": status,
        "stop_reason": stop_reason,
        "cases": total_cases,
        "completed_cases": len(rows),
        "settings": settings,
        "rag_grounding_score": round(average(grounding_scores), 4),
        "hallucination_risk": round(average(hallucination_risks), 4),
        "answer_correctness_score": round(average(correctness_scores), 4),
        "reference_answer_cases": len(correctness_scores),
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
    mode: str = "embedding",
    judge_model: str = GROQ_MODEL,
    judge_max_tokens: int = 180,
    context_chars: int = 2500,
    answer_chars: int = 1200,
    delay_seconds: float = 0.0,
    max_retries: int = 5,
    retry_buffer_seconds: float = 2.0,
    max_wait_seconds: float = 300.0,
    resume: bool = True,
    grounding_threshold: float = 0.62,
    max_chunks: int = 30,
    max_chars_per_chunk: int = 1200,
    soft_threshold: float = 0.50,
    strong_threshold: float = 0.78,
    global_weight: float = 0.35,
) -> dict:
    if mode not in {"embedding", "llm"}:
        raise ValueError("mode must be 'embedding' or 'llm'")

    cases = load_json(dataset_path)
    settings = {
        "mode": mode,
        "judge_model": judge_model if mode == "llm" else None,
        "judge_max_tokens": judge_max_tokens if mode == "llm" else None,
        "context_chars": context_chars,
        "answer_chars": answer_chars,
        "delay_seconds": delay_seconds,
        "max_retries": max_retries,
        "retry_buffer_seconds": retry_buffer_seconds,
        "max_wait_seconds": max_wait_seconds,
        "resume": resume,
        "grounding_threshold": grounding_threshold,
        "max_chunks": max_chunks,
        "max_chars_per_chunk": max_chars_per_chunk,
        "soft_threshold": soft_threshold,
        "strong_threshold": strong_threshold,
        "global_weight": global_weight,
    }
    rows = [
        row for row in _load_completed_rows(output_path, resume)
        if row.get("evaluation_mode") == mode
    ]
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
        reference_answer = case.get("reference_answer")

        try:
            chunks, retrieval_ms = time_call(fetch_scheme_chunks, scheme_id)
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

            row: dict[str, Any] = {
                "case_id": case_id,
                "evaluation_mode": mode,
                "scheme_id": scheme_id,
                "question": question,
                "reference_answer": reference_answer,
                "answer": answer,
                "retrieval_ms": round(retrieval_ms, 2),
                "answer_latency_ms": round(answer_ms, 2),
            }

            if mode == "embedding":
                embedding_metrics, metric_ms = time_call(
                    evaluate_embedding_metrics,
                    answer,
                    chunks,
                    reference_answer,
                    grounding_threshold,
                    max_chunks,
                    max_chars_per_chunk,
                    soft_threshold,
                    strong_threshold,
                    global_weight,
                )
                row.update(embedding_metrics)
                row["metric_latency_ms"] = round(metric_ms, 2)
            else:
                context = build_scheme_context(chunks)
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
                row.update(
                    {
                        "faithful": judge_result["faithful"],
                        "judge_score": judge_result["score"],
                        "unsupported_claims": judge_result["unsupported_claims"],
                        "judge_latency_ms": round(judge_ms, 2),
                    }
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

        rows.append(row)
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
    parser.add_argument("--mode", choices=["embedding", "llm"], default="embedding")
    parser.add_argument("--grounding-threshold", type=float, default=0.62)
    parser.add_argument("--max-chunks", type=int, default=30)
    parser.add_argument("--max-chars-per-chunk", type=int, default=1200)
    parser.add_argument("--soft-threshold", type=float, default=0.50)
    parser.add_argument("--strong-threshold", type=float, default=0.78)
    parser.add_argument("--global-weight", type=float, default=0.35)
    parser.add_argument("--judge-model", default=GROQ_MODEL)
    parser.add_argument("--judge-max-tokens", type=int, default=180)
    parser.add_argument("--context-chars", type=int, default=2500)
    parser.add_argument("--answer-chars", type=int, default=1200)
    parser.add_argument("--delay-seconds", type=float, default=0.0)
    parser.add_argument("--max-retries", type=int, default=5)
    parser.add_argument("--retry-buffer-seconds", type=float, default=2.0)
    parser.add_argument("--max-wait-seconds", type=float, default=300.0)
    parser.add_argument("--no-resume", action="store_true")
    args = parser.parse_args()

    report = run(
        args.dataset,
        args.output,
        mode=args.mode,
        judge_model=args.judge_model,
        judge_max_tokens=args.judge_max_tokens,
        context_chars=args.context_chars,
        answer_chars=args.answer_chars,
        delay_seconds=args.delay_seconds,
        max_retries=args.max_retries,
        retry_buffer_seconds=args.retry_buffer_seconds,
        max_wait_seconds=args.max_wait_seconds,
        resume=not args.no_resume,
        grounding_threshold=args.grounding_threshold,
        max_chunks=args.max_chunks,
        max_chars_per_chunk=args.max_chars_per_chunk,
        soft_threshold=args.soft_threshold,
        strong_threshold=args.strong_threshold,
        global_weight=args.global_weight,
    )
    print(f"RAG grounding score: {report['rag_grounding_score']}")
    print(f"Hallucination risk: {report['hallucination_risk']}")
    print(f"Answer correctness score: {report['answer_correctness_score']}")
    if args.mode == "llm":
        print(f"LLM faithfulness: {report['faithfulness']}")
        print(f"LLM hallucination rate: {report['hallucination_rate']}")
    print(f"Report written to {args.output}")


if __name__ == "__main__":
    main()
