"""Shared helpers for evaluation scripts."""
from __future__ import annotations

import json
import sys
from pathlib import Path
from time import perf_counter
from typing import Any, Callable

from dotenv import load_dotenv

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

load_dotenv(PROJECT_ROOT / ".env")


def load_json(path: str | Path) -> list[dict[str, Any]]:
    dataset_path = Path(path)
    if not dataset_path.is_absolute():
        dataset_path = PROJECT_ROOT / dataset_path
    with dataset_path.open("r", encoding="utf-8") as file:
        data = json.load(file)
    if not isinstance(data, list):
        raise ValueError(f"{dataset_path} must contain a JSON list")
    return data


def write_json(path: str | Path, payload: dict[str, Any]) -> None:
    output_path = Path(path)
    if not output_path.is_absolute():
        output_path = PROJECT_ROOT / output_path
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", encoding="utf-8") as file:
        json.dump(payload, file, indent=2, ensure_ascii=False)
        file.write("\n")


def time_call(fn: Callable[..., Any], *args: Any, **kwargs: Any) -> tuple[Any, float]:
    start = perf_counter()
    result = fn(*args, **kwargs)
    elapsed_ms = (perf_counter() - start) * 1000
    return result, elapsed_ms
