"""Evaluate profile-based discovery with eligibility precision/recall."""
from __future__ import annotations

import argparse

from evaluation.eval_utils import load_json, time_call, write_json
from evaluation.metrics import average, percentile, precision_recall
from rag_pipeline.inference.generator import prepare_discovery_candidates


def run(dataset_path: str, output_path: str, top_k: int = 10) -> dict:
    cases = load_json(dataset_path)
    rows = []
    precisions = []
    recalls = []
    latencies = []

    for case in cases:
        profile = case["profile"]
        expected_ids = case.get("eligible_scheme_ids", [])
        (results, is_relaxed), elapsed_ms = time_call(prepare_discovery_candidates, profile)
        predicted_ids = [item.scheme_id for item in results[:top_k]]
        precision, recall = precision_recall(predicted_ids, expected_ids)

        precisions.append(precision)
        recalls.append(recall)
        latencies.append(elapsed_ms)
        rows.append(
            {
                "case_id": case.get("id"),
                "profile": profile,
                "expected_scheme_ids": expected_ids,
                "predicted_top_k": predicted_ids,
                "is_relaxed": is_relaxed,
                "precision": round(precision, 4),
                "recall": round(recall, 4),
                "latency_ms": round(elapsed_ms, 2),
            }
        )

    report = {
        "metric": "Eligibility Precision / Recall",
        "cases": len(cases),
        "top_k": top_k,
        "precision": round(average(precisions), 4),
        "recall": round(average(recalls), 4),
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
    parser.add_argument("--dataset", default="evaluation/datasets/eligibility_eval.sample.json")
    parser.add_argument("--output", default="evaluation/reports/eligibility_report.json")
    parser.add_argument("--top-k", type=int, default=10)
    args = parser.parse_args()

    report = run(args.dataset, args.output, args.top_k)
    print(f"Eligibility Precision: {report['precision']}")
    print(f"Eligibility Recall: {report['recall']}")
    print(f"Report written to {args.output}")


if __name__ == "__main__":
    main()
