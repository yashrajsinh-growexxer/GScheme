"""Measure end-to-end API latency for selected GScheme endpoints."""
from __future__ import annotations

import argparse
from time import perf_counter
from typing import Any

import httpx

from evaluation.eval_utils import load_json, write_json
from evaluation.metrics import average, percentile

ENDPOINT_ALIASES = {
    "eligibility": "discover",
    "/eligibility": "discover",
}


def _post_text_stream(client: httpx.Client, url: str, payload: dict[str, Any]) -> tuple[str, float, float, int]:
    start = perf_counter()
    first_chunk_ms = 0.0
    chunks: list[str] = []
    status_code = 0

    with client.stream("POST", url, json=payload) as response:
        status_code = response.status_code
        for chunk in response.iter_text():
            if chunk and not first_chunk_ms:
                first_chunk_ms = (perf_counter() - start) * 1000
            chunks.append(chunk)

    total_ms = (perf_counter() - start) * 1000
    return "".join(chunks), first_chunk_ms, total_ms, status_code


def _resolve_endpoint(endpoint: str) -> tuple[str, str]:
    """Resolve product-facing endpoint names to backend API routes."""
    original = endpoint if endpoint.startswith("/") else f"/{endpoint}"
    normalized = endpoint.strip().lstrip("/")
    resolved = ENDPOINT_ALIASES.get(normalized, ENDPOINT_ALIASES.get(original, normalized))
    return original, resolved.lstrip("/")


def run(dataset_path: str, output_path: str, api_base: str) -> dict:
    cases = load_json(dataset_path)
    rows = []
    total_latencies = []
    first_chunk_latencies = []

    with httpx.Client(timeout=120.0) as client:
        for case in cases:
            requested_endpoint, endpoint = _resolve_endpoint(case["endpoint"])
            url = f"{api_base.rstrip('/')}/{endpoint}"
            payload = case.get("payload", {})
            streaming = case.get("streaming", False)

            if streaming:
                body, first_chunk_ms, total_ms, status_code = _post_text_stream(client, url, payload)
            else:
                start = perf_counter()
                response = client.post(url, json=payload)
                total_ms = (perf_counter() - start) * 1000
                first_chunk_ms = total_ms
                status_code = response.status_code
                body = response.text

            total_latencies.append(total_ms)
            first_chunk_latencies.append(first_chunk_ms)
            rows.append(
                {
                    "case_id": case.get("id"),
                    "endpoint": requested_endpoint,
                    "api_endpoint": f"/{endpoint}",
                    "status_code": status_code,
                    "time_to_first_chunk_ms": round(first_chunk_ms, 2),
                    "total_latency_ms": round(total_ms, 2),
                    "response_preview": body[:300],
                }
            )

    report = {
        "metric": "End-to-end latency",
        "cases": len(cases),
        "api_base": api_base,
        "total_latency": {
            "avg_ms": round(average(total_latencies), 2),
            "p50_ms": round(percentile(total_latencies, 0.50), 2),
            "p95_ms": round(percentile(total_latencies, 0.95), 2),
        },
        "time_to_first_chunk": {
            "avg_ms": round(average(first_chunk_latencies), 2),
            "p50_ms": round(percentile(first_chunk_latencies, 0.50), 2),
            "p95_ms": round(percentile(first_chunk_latencies, 0.95), 2),
        },
        "rows": rows,
    }
    write_json(output_path, report)
    return report


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dataset", default="evaluation/datasets/latency_eval.sample.json")
    parser.add_argument("--output", default="evaluation/reports/latency_report.json")
    parser.add_argument("--api-base", default="http://127.0.0.1:8501/api")
    args = parser.parse_args()

    report = run(args.dataset, args.output, args.api_base)
    print(f"Total latency p50: {report['total_latency']['p50_ms']} ms")
    print(f"Total latency p95: {report['total_latency']['p95_ms']} ms")
    print(f"Report written to {args.output}")


if __name__ == "__main__":
    main()
