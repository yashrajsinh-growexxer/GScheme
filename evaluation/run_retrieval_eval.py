"""Evaluate scheme-name search with Recall@5."""
from __future__ import annotations

import argparse

from evaluation.eval_utils import load_json, time_call, write_json
from evaluation.metrics import average, percentile, recall_at_k
from rag_pipeline.inference.generator import prepare_search_candidates


def run(dataset_path: str, output_path: str, k: int = 5) -> dict:
    cases = load_json(dataset_path)
    rows = []
    recalls = []
    latencies = []

    for case in cases:
        query = case["query"]
        expected_ids = case.get("expected_scheme_ids", [])
        filters = case.get("filters")
        results, elapsed_ms = time_call(prepare_search_candidates, query, filters=filters)
        predicted_ids = [item.scheme_id for item in results[:k]]
        score = recall_at_k(predicted_ids, expected_ids, k=k)

        recalls.append(score)
        latencies.append(elapsed_ms)
        rows.append(
            {
                "query": query,
                "expected_scheme_ids": expected_ids,
                "predicted_top_k": predicted_ids,
                f"recall_at_{k}": score,
                "latency_ms": round(elapsed_ms, 2),
            }
        )

    report = {
        "metric": f"Search Recall@{k}",
        "cases": len(cases),
        f"recall_at_{k}": round(average(recalls), 4),
        "latency": {
            "p50_ms": round(percentile(latencies, 0.50), 2),
            "p95_ms": round(percentile(latencies, 0.95), 2),
        },
        "rows": rows,
    }
    write_json(output_path, report)
    return report


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dataset", default="evaluation/datasets/retrieval_eval.sample.json")
    parser.add_argument("--output", default="evaluation/reports/retrieval_report.json")
    parser.add_argument("--k", type=int, default=5)
    args = parser.parse_args()

    report = run(args.dataset, args.output, args.k)
    print(f"Search Recall@{args.k}: {report[f'recall_at_{args.k}']}")
    print(f"Report written to {args.output}")


if __name__ == "__main__":
    main()
