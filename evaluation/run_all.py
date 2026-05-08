"""Run all available GScheme evaluation suites."""
from __future__ import annotations

import argparse

from evaluation import run_eligibility_eval, run_generation_eval, run_latency_eval, run_retrieval_eval
from evaluation.eval_utils import write_json


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--api-base", default="http://127.0.0.1:8501/api")
    parser.add_argument("--skip-generation", action="store_true")
    args = parser.parse_args()

    reports = {
        "retrieval": run_retrieval_eval.run(
            "evaluation/datasets/retrieval_eval.json",
            "evaluation/reports/retrieval_report.json",
        ),
        "eligibility": run_eligibility_eval.run(
            "evaluation/datasets/eligibility_eval.json",
            "evaluation/reports/eligibility_report.json",
            5
        ),
        "latency": run_latency_eval.run(
            "evaluation/datasets/latency_eval.json",
            "evaluation/reports/latency_report.json",
            args.api_base,
        ),
    }

    if not args.skip_generation:
        reports["generation"] = run_generation_eval.run(
            "evaluation/datasets/chat_eval.json",
            "evaluation/reports/generation_report.json",
        )

    summary = {
        "search_recall_at_5": reports["retrieval"]["recall_at_5"],
        "eligibility_precision": reports["eligibility"]["precision"],
        "eligibility_recall": reports["eligibility"]["recall"],
        "latency_p50_ms": reports["latency"]["total_latency"]["p50_ms"],
    }
    if "generation" in reports:
        summary.update(
            {
                "rag_grounding_score": reports["generation"]["rag_grounding_score"],
                "hallucination_risk": reports["generation"]["hallucination_risk"],
                "answer_correctness_score": reports["generation"]["answer_correctness_score"],
            }
        )

    write_json(
        "evaluation/reports/summary_report.json",
        {
            "summary": summary,
            "reports": {
                name: f"evaluation/reports/{name if name != 'generation' else 'generation'}_report.json"
                for name in reports
            },
        },
    )

    print("Evaluation summary")
    for key, value in summary.items():
        print(f"- {key}: {value}")
    print("Report written to evaluation/reports/summary_report.json")


if __name__ == "__main__":
    main()
