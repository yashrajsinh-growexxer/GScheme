"""
Comparison module — extract structured data for side-by-side scheme comparison.

Reads chunks from Qdrant and the knowledge base to assemble structured
fields such as eligibility, benefits, income caps, age limits, etc.
"""
from __future__ import annotations

import re
from collections import defaultdict
from typing import Any, Dict, List, Optional

from rag_pipeline.inference.retriever import fetch_scheme_chunks, get_qdrant_client
from rag_pipeline.config import QDRANT_COLLECTION_NAME


def get_scheme_comparison_data(scheme_id: str) -> Dict[str, Any]:
    """
    Fetch all chunks for a scheme and return structured comparison fields.

    Returns a dict with keys:
        scheme_id, name, state, category, url,
        details, eligibility, benefits,
        income_cap, age_limits,
        documents_required, application_mode, application_process,
        gender_tags, caste_tags
    """
    chunks = fetch_scheme_chunks(scheme_id)
    if not chunks:
        return _empty_comparison(scheme_id)

    # Group chunks by type
    sections: Dict[str, List[str]] = defaultdict(list)
    meta = {
        "name": "",
        "url": "",
        "state": "",
        "category": "",
    }

    for c in chunks:
        ctype = c.get("chunk_type", "")
        text = c.get("text", "")
        if ctype and text:
            sections[ctype].append(text)

        # Grab metadata from first chunk
        if not meta["name"]:
            meta["name"] = c.get("scheme_name", "")
        if not meta["url"]:
            meta["url"] = c.get("scheme_url", "")
        if not meta["state"]:
            meta["state"] = c.get("location_name", "")

    # Fetch payload metadata for age, gender, caste from Qdrant
    payload_meta = _fetch_payload_metadata(scheme_id)

    # Assemble section texts
    details_text = "\n".join(sections.get("details", []))
    eligibility_text = "\n".join(sections.get("eligibility", []))
    benefits_text = "\n".join(sections.get("benefits", []))
    app_process_text = "\n".join(sections.get("application_process", []))
    docs_text = "\n".join(sections.get("documents_required", []))

    # Extract structured fields
    income_cap = _extract_income_cap(eligibility_text + "\n" + details_text)
    age_limits = _extract_age_limits(payload_meta, eligibility_text)
    application_mode = _extract_application_mode(app_process_text)
    documents_list = _extract_documents_list(docs_text)

    return {
        "scheme_id": scheme_id,
        "name": meta["name"] or "Unknown Scheme",
        "state": meta["state"] or "N/A",
        "category": payload_meta.get("category_name", "").replace("_", " ").title() or "N/A",
        "url": meta["url"] or "N/A",
        "details": details_text.strip() or "N/A",
        "eligibility": eligibility_text.strip() or "N/A",
        "benefits": benefits_text.strip() or "N/A",
        "income_cap": income_cap,
        "age_limits": age_limits,
        "documents_required": documents_list,
        "application_mode": application_mode,
        "application_process": app_process_text.strip() or "N/A",
        "gender_tags": payload_meta.get("gender_tags", []),
        "caste_tags": payload_meta.get("caste_tags", []),
    }


def get_multiple_scheme_comparison(scheme_ids: List[str]) -> List[Dict[str, Any]]:
    """Fetch comparison data for multiple schemes."""
    return [get_scheme_comparison_data(sid) for sid in scheme_ids]


# ── Private helpers ──────────────────────────────────────────────────


def _empty_comparison(scheme_id: str) -> Dict[str, Any]:
    """Return an empty comparison dict when no data is found."""
    return {
        "scheme_id": scheme_id,
        "name": "Unknown Scheme",
        "state": "N/A",
        "category": "N/A",
        "url": "N/A",
        "details": "N/A",
        "eligibility": "N/A",
        "benefits": "N/A",
        "income_cap": "N/A",
        "age_limits": "N/A",
        "documents_required": [],
        "application_mode": "N/A",
        "application_process": "N/A",
        "gender_tags": [],
        "caste_tags": [],
    }


def _fetch_payload_metadata(scheme_id: str) -> Dict[str, Any]:
    """Fetch metadata fields from Qdrant payload for a scheme."""
    try:
        client = get_qdrant_client()
        from qdrant_client.http import models

        points, _ = client.scroll(
            collection_name=QDRANT_COLLECTION_NAME,
            scroll_filter=models.Filter(
                must=[
                    models.FieldCondition(
                        key="scheme_id",
                        match=models.MatchValue(value=scheme_id),
                    )
                ]
            ),
            limit=1,
            with_payload=True,
        )

        if points:
            return points[0].payload or {}
    except Exception:
        pass
    return {}


def _extract_income_cap(text: str) -> str:
    """
    Extract income cap / financial eligibility from text using regex patterns.
    Looks for patterns like 'annual income', 'family income', 'Rs.', '₹', 'lakh', etc.
    """
    if not text:
        return "N/A"

    # Patterns for income mentions
    patterns = [
        # "annual family income ... Rs. 2,50,000" or "₹ 2.5 lakh"
        r"(?:annual|yearly|family|household)\s*income[^.]*?(?:Rs\.?|₹|INR)\s*[\d,]+(?:\.\d+)?(?:\s*(?:lakh|lakhs|lac|crore|per\s*annum))?",
        # "income below Rs. X" / "income not exceeding"
        r"income\s*(?:below|under|not\s*exceed(?:ing)?|up\s*to|less\s*than)[^.]*?(?:Rs\.?|₹|INR)\s*[\d,]+(?:\.\d+)?(?:\s*(?:lakh|lakhs|lac|crore|per\s*annum))?",
        # "Rs. X per annum" in income context
        r"(?:Rs\.?|₹|INR)\s*[\d,]+(?:\.\d+)?(?:\s*(?:lakh|lakhs|lac|crore))?\s*per\s*annum",
        # "BPL" mention
        r"\b(?:below\s*poverty\s*line|BPL)\b",
        # "EWS" or "economically weaker"
        r"\b(?:economically\s*weaker\s*section|EWS)\b",
    ]

    for pattern in patterns:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            # Clean up and return the matched text
            result = match.group(0).strip()
            # Capitalize first letter
            return result[0].upper() + result[1:] if result else "N/A"

    return "N/A"


def _extract_age_limits(payload_meta: Dict[str, Any], eligibility_text: str) -> str:
    """Extract age limits from payload metadata or eligibility text."""
    age_min = payload_meta.get("age_min")
    age_max = payload_meta.get("age_max")
    age_present = payload_meta.get("age_present", False)

    if age_present and (age_min is not None or age_max is not None):
        if age_min is not None and age_max is not None:
            return f"{age_min} – {age_max} years"
        elif age_min is not None:
            return f"{age_min}+ years"
        elif age_max is not None:
            return f"Up to {age_max} years"

    # Fallback: try to extract from eligibility text
    if eligibility_text:
        age_pattern = r"(?:age|aged)\s*(?:between|from|of)?\s*(\d{1,3})\s*(?:to|-|–|and)\s*(\d{1,3})\s*(?:years|yrs)?"
        match = re.search(age_pattern, eligibility_text, re.IGNORECASE)
        if match:
            return f"{match.group(1)} – {match.group(2)} years"

        # Single age limit
        min_pattern = r"(?:minimum|at\s*least|above|over)\s*(\d{1,3})\s*(?:years|yrs)?"
        match = re.search(min_pattern, eligibility_text, re.IGNORECASE)
        if match:
            return f"{match.group(1)}+ years"

        max_pattern = r"(?:maximum|up\s*to|below|under|not\s*exceed(?:ing)?)\s*(\d{1,3})\s*(?:years|yrs)?"
        match = re.search(max_pattern, eligibility_text, re.IGNORECASE)
        if match:
            return f"Up to {match.group(1)} years"

    return "N/A"


def _extract_application_mode(app_process_text: str) -> str:
    """Determine if the application is online, offline, or both."""
    if not app_process_text:
        return "N/A"

    text_lower = app_process_text.lower()
    has_online = any(
        kw in text_lower
        for kw in ["online", "portal", "website", "digital", "e-portal", "web"]
    )
    has_offline = any(
        kw in text_lower
        for kw in ["offline", "in person", "visit the office", "physically", "counter"]
    )

    if has_online and has_offline:
        return "Online & Offline"
    elif has_online:
        return "Online"
    elif has_offline:
        return "Offline"
    return "N/A"


def _extract_documents_list(docs_text: str) -> List[str]:
    """Parse documents text into a clean list."""
    if not docs_text or docs_text.strip() == "":
        return []

    # Split by newlines and clean up
    lines = docs_text.split("\n")
    documents = []
    for line in lines:
        cleaned = line.strip().lstrip("•-–*·0123456789.)")
        cleaned = cleaned.strip()
        if cleaned and len(cleaned) > 2:
            documents.append(cleaned)

    return documents if documents else []
