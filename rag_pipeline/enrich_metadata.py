"""
Create enriched per-scheme JSON files with filter metadata.

This script never mutates raw scraped files. It reads from
data/schemes_data_json and writes enriched copies to
data/schemes_enriched_json while preserving folder structure.
"""
from __future__ import annotations

import argparse
import json
import re
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Tuple

try:
    from .config import (
        CASTE_TAGS,
        CENTRAL_GOVT_LABEL,
        ENRICHED_DATA_DIR,
        GENDER_TAGS,
        LOCATION_TYPE_CENTRAL,
        RAW_DATA_DIR,
    )
except ImportError:
    from config import (
        CASTE_TAGS,
        CENTRAL_GOVT_LABEL,
        ENRICHED_DATA_DIR,
        GENDER_TAGS,
        LOCATION_TYPE_CENTRAL,
        RAW_DATA_DIR,
    )


@dataclass
class AgeExtraction:
    age_min: Optional[int]
    age_max: Optional[int]
    age_present: bool
    age_confidence: float
    age_raw_text: Optional[str]


def iter_scheme_files(root_dir: Path) -> Iterable[Path]:
    """Yield raw scheme JSON files."""
    yield from root_dir.rglob("*.json")


def safe_load_json(path: Path) -> Optional[Dict[str, Any]]:
    """Load JSON with soft-fail behavior."""
    try:
        with open(path, "r", encoding="utf-8") as handle:
            return json.load(handle)
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        print(f"[WARN] Failed to read {path}: {exc}")
        return None


def normalize_location(data: Dict[str, Any]) -> Tuple[str, str]:
    """Normalize central schemes where raw location fields are empty."""
    location_name = (data.get("location_name") or "").strip()
    location_type = (data.get("location_type") or "").strip()
    if not location_name or not location_type:
        return CENTRAL_GOVT_LABEL, LOCATION_TYPE_CENTRAL
    return location_name, location_type


def flatten_text(data: Dict[str, Any]) -> str:
    """Build one normalized text blob from details + eligibility sections."""
    sections = data.get("sections") or {}
    parts: List[str] = []
    for key in ("details", "eligibility"):
        value = sections.get(key)
        if isinstance(value, list):
            parts.extend(str(item) for item in value if item)
        elif isinstance(value, str):
            parts.append(value)
    # Lower-casing makes keyword extraction deterministic.
    return "\n".join(parts).strip().lower()


def extract_gender_tags(text_blob: str) -> List[str]:
    """Extract normalized gender tags from free text."""
    if not text_blob:
        return ["unknown"]

    tags = set()

    female_markers = [
        r"\bwomen\b", r"\bwoman\b", r"\bfemale\b", r"\bgirl\b",
        r"\bpregnant\b", r"\blactating\b", r"\bwidow\b", r"\bmahila\b",
    ]
    male_markers = [r"\bmen\b", r"\bman\b", r"\bmale\b", r"\bboy\b"]
    trans_markers = [r"\btransgender\b", r"\bthird gender\b"]
    any_markers = [
        r"\ball genders\b", r"\bany gender\b", r"\bregardless of gender\b",
        r"\bopen to all\b", r"\ball applicants\b", r"\bany applicant\b",
    ]

    if any(re.search(pat, text_blob) for pat in female_markers):
        tags.add("female")
    if any(re.search(pat, text_blob) for pat in male_markers):
        tags.add("male")
    if any(re.search(pat, text_blob) for pat in trans_markers):
        tags.add("transgender")
    if any(re.search(pat, text_blob) for pat in any_markers):
        tags.add("any")

    if not tags:
        return ["unknown"]

    # If both male and female are present and there is no explicit restriction,
    # "any" helps avoid over-filtering.
    if {"male", "female"}.issubset(tags):
        tags.add("any")

    normalized = [t for t in GENDER_TAGS if t in tags]
    return normalized or ["unknown"]


def extract_caste_tags(text_blob: str) -> List[str]:
    """Extract normalized caste/community tags from free text."""
    if not text_blob:
        return ["unknown"]

    tags = set()
    keyword_map = {
        "sc": [r"\bsc\b", r"scheduled caste", r"schedule caste"],
        "st": [r"\bst\b", r"scheduled tribe", r"schedule tribe", r"tribal"],
        "obc": [r"\bobc\b", r"other backward"],
        "minority": [r"\bminority\b", r"minorities"],
        "ews": [r"\bews\b", r"economically weaker section"],
        "general": [r"\bgeneral category\b", r"\bopen category\b"],
        "any": [r"\ball castes\b", r"\bany caste\b", r"\birrespective of caste\b"],
    }

    for tag, patterns in keyword_map.items():
        if any(re.search(pat, text_blob) for pat in patterns):
            tags.add(tag)

    if not tags:
        return ["unknown"]

    normalized = [t for t in CASTE_TAGS if t in tags]
    return normalized or ["unknown"]


def _age_context_sentences(text_blob: str) -> List[str]:
    """Get candidate age lines for explainability."""
    lines = [ln.strip() for ln in re.split(r"[\n\.]", text_blob) if ln.strip()]
    return [
        ln for ln in lines
        if re.search(r"\bage\b", ln) or re.search(r"\byears?\b", ln)
    ]


def extract_age_metadata(text_blob: str) -> AgeExtraction:
    """Extract age bounds using rule-based patterns."""
    if not text_blob:
        return AgeExtraction(None, None, False, 0.0, None)

    age_min: Optional[int] = None
    age_max: Optional[int] = None
    confidence = 0.0

    # Strongest: explicit range.
    range_patterns = [
        r"between\s+(\d{1,2})\s*(?:-|to|and)\s*(\d{1,2})\s*years?",
        r"age\s*(?:of)?\s*(\d{1,2})\s*(?:-|to)\s*(\d{1,2})\s*years?",
        r"(\d{1,2})\s*(?:-|to)\s*(\d{1,2})\s*years?\s*(?:of age|old)?",
    ]
    for pat in range_patterns:
        match = re.search(pat, text_blob)
        if match:
            low, high = int(match.group(1)), int(match.group(2))
            age_min, age_max = min(low, high), max(low, high)
            confidence = 0.95
            break

    # If no explicit range, infer each side.
    if age_min is None and age_max is None:
        min_patterns = [
            r"(?:minimum|at least|not less than|above|over)\s*(\d{1,2})\s*years?",
            r"age\s*(?:should be|must be)?\s*(?:above|over)\s*(\d{1,2})",
        ]
        max_patterns = [
            r"(?:maximum|up to|upto|not more than|not exceeding|below|under|less than)\s*(\d{1,2})\s*years?",
            r"age\s*(?:should be|must be)?\s*(?:below|under)\s*(\d{1,2})",
        ]

        min_hits: List[int] = []
        max_hits: List[int] = []
        for pat in min_patterns:
            min_hits.extend(int(m) for m in re.findall(pat, text_blob))
        for pat in max_patterns:
            max_hits.extend(int(m) for m in re.findall(pat, text_blob))

        if min_hits:
            age_min = min(min_hits)
            confidence = max(confidence, 0.7)
        if max_hits:
            age_max = max(max_hits)
            confidence = max(confidence, 0.7)
        if age_min is not None and age_max is not None:
            confidence = max(confidence, 0.85)

    # Guard against accidental reversed bounds.
    if age_min is not None and age_max is not None and age_min > age_max:
        age_min, age_max = age_max, age_min

    age_present = age_min is not None or age_max is not None
    if not age_present:
        confidence = 0.0

    context_lines = _age_context_sentences(text_blob)
    raw_text = context_lines[0] if context_lines else None

    return AgeExtraction(
        age_min=age_min,
        age_max=age_max,
        age_present=age_present,
        age_confidence=round(confidence, 3),
        age_raw_text=raw_text,
    )


def build_filter_metadata(data: Dict[str, Any]) -> Dict[str, Any]:
    """Build filter metadata block for one scheme."""
    text_blob = flatten_text(data)
    age = extract_age_metadata(text_blob)
    gender_tags = extract_gender_tags(text_blob)
    caste_tags = extract_caste_tags(text_blob)
    location_name, location_type = normalize_location(data)

    return {
        "location_name": location_name,
        "location_type": location_type,
        "gender_tags": gender_tags,
        "caste_tags": caste_tags,
        "age_min": age.age_min,
        "age_max": age.age_max,
        "age_present": age.age_present,
        "age_min_effective": (
            None if not age.age_present else (0 if age.age_min is None else age.age_min)
        ),
        "age_max_effective": (
            None if not age.age_present else (120 if age.age_max is None else age.age_max)
        ),
        "age_confidence": age.age_confidence,
        "age_raw_text": age.age_raw_text,
    }


def enrich_scheme(data: Dict[str, Any]) -> Dict[str, Any]:
    """Add filter metadata and extraction metadata to one scheme JSON."""
    enriched = dict(data)
    enriched["filter_metadata"] = build_filter_metadata(data)
    enriched["metadata_extraction"] = {
        "version": "v1_rule_based",
        "extracted_at_utc": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC"),
    }
    return enriched


def write_json(path: Path, data: Dict[str, Any]) -> None:
    """Write JSON with stable formatting."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as handle:
        json.dump(data, handle, ensure_ascii=False, indent=2)


def run_enrichment(
    input_dir: Path = RAW_DATA_DIR,
    output_dir: Path = ENRICHED_DATA_DIR,
    overwrite: bool = False,
    limit: Optional[int] = None,
) -> Dict[str, int]:
    """Enrich all raw files and write mirrored output tree."""
    files = list(iter_scheme_files(input_dir))
    if limit is not None:
        files = files[:limit]

    stats = {"total": len(files), "processed": 0, "skipped": 0, "failed": 0}
    print(f"Enriching {stats['total']} files from {input_dir} -> {output_dir}")

    for idx, src in enumerate(files, start=1):
        rel = src.relative_to(input_dir)
        dst = output_dir / rel

        if dst.exists() and not overwrite:
            stats["skipped"] += 1
            continue

        raw = safe_load_json(src)
        if raw is None:
            stats["failed"] += 1
            continue

        try:
            enriched = enrich_scheme(raw)
            write_json(dst, enriched)
            stats["processed"] += 1
        except Exception as exc:  # noqa: BLE001 - keep pipeline resilient
            print(f"[WARN] Failed to enrich {src}: {exc}")
            stats["failed"] += 1

        if idx % 500 == 0:
            print(f"  {idx}/{stats['total']} scanned...")

    return stats


def main() -> None:
    parser = argparse.ArgumentParser(description="Create enriched scheme JSON files.")
    parser.add_argument("--input-dir", type=Path, default=RAW_DATA_DIR)
    parser.add_argument("--output-dir", type=Path, default=ENRICHED_DATA_DIR)
    parser.add_argument("--overwrite", action="store_true")
    parser.add_argument("--limit", type=int, default=None)
    args = parser.parse_args()

    stats = run_enrichment(
        input_dir=args.input_dir,
        output_dir=args.output_dir,
        overwrite=args.overwrite,
        limit=args.limit,
    )

    print("\n=== Enrichment Summary ===")
    for key, value in stats.items():
        print(f"{key}: {value}")


if __name__ == "__main__":
    main()
