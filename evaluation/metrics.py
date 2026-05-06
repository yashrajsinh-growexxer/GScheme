"""Reusable metric helpers for GScheme evaluation."""
from __future__ import annotations

from statistics import mean
from typing import Iterable, Sequence


def recall_at_k(predicted_ids: Sequence[str], expected_ids: Iterable[str], k: int = 5) -> float:
    """Return 1.0 if any expected item appears in the top-k predictions."""
    expected = set(expected_ids)
    if not expected:
        return 0.0
    return 1.0 if expected.intersection(predicted_ids[:k]) else 0.0


def precision_recall(predicted_ids: Sequence[str], expected_ids: Iterable[str]) -> tuple[float, float]:
    """Compute set-based precision and recall for one eligibility case."""
    predicted = set(predicted_ids)
    expected = set(expected_ids)

    if not predicted and not expected:
        return 1.0, 1.0
    if not predicted:
        return 0.0, 0.0

    true_positive = len(predicted.intersection(expected))
    precision = true_positive / len(predicted)
    recall = true_positive / len(expected) if expected else 0.0
    return precision, recall


def average(values: Sequence[float]) -> float:
    """Return a stable average for possibly empty metric lists."""
    return mean(values) if values else 0.0


def percentile(values: Sequence[float], pct: float) -> float:
    """Nearest-rank percentile for latency lists."""
    if not values:
        return 0.0
    ordered = sorted(values)
    index = round((len(ordered) - 1) * pct)
    return ordered[index]
