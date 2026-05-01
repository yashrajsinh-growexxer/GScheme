"""
Retriever module — Qdrant hybrid search with metadata filtering.

Two modes:
  1. discover_schemes()  — metadata filter + semantic search on eligibility/details
  2. fetch_scheme_chunks() — fetch ALL chunks for a single scheme_id (deep-dive)
"""
from __future__ import annotations

import os
import re
from collections import defaultdict
from dataclasses import dataclass, field
from difflib import SequenceMatcher
from functools import lru_cache
from typing import Any, Dict, List, Optional

from dotenv import load_dotenv

from rag_pipeline.config import (
    CENTRAL_GOVT_LABEL,
    DENSE_VECTOR_NAME,
    DISCOVERY_INITIAL_FETCH,
    DISCOVERY_RERANK_CANDIDATES,
    DISCOVERY_TOP_K,
    DISCOVERY_USE_SEMANTIC,
    PROFESSION_BOOST,
    PROFESSION_CATEGORY_MAP,
    QDRANT_COLLECTION_NAME,
    SPARSE_VECTOR_NAME,
)
from rag_pipeline.knowledge_base.data_loader import load_all_schemes
from rag_pipeline.knowledge_base.embeddings import get_embedding_model

load_dotenv()


# ── Data structures ──────────────────────────────────────────────────


@dataclass
class SchemeResult:
    """One scheme with aggregated score and its matching chunks."""

    scheme_id: str
    scheme_name: str
    scheme_url: str
    location_name: str
    category_id: int
    category_name: str
    score: float
    chunks: List[Dict[str, Any]] = field(default_factory=list)

    @property
    def details_text(self) -> str:
        return "\n".join(
            c["text"] for c in self.chunks if c.get("chunk_type") == "details"
        )

    @property
    def eligibility_text(self) -> str:
        return "\n".join(
            c["text"] for c in self.chunks if c.get("chunk_type") == "eligibility"
        )

    @property
    def combined_text(self) -> str:
        return "\n\n".join(c["text"] for c in self.chunks)


# ── Qdrant client ───────────────────────────────────────────────────


_qdrant_client = None


class KnowledgeBaseUnavailableError(RuntimeError):
    """Raised when the remote Qdrant knowledge base cannot be reached."""


def _raise_kb_unavailable(exc: Exception) -> None:
    raise KnowledgeBaseUnavailableError(
        "The scheme knowledge base is temporarily unreachable. "
        "Please check your internet/DNS connection and Qdrant availability."
    ) from exc


def get_qdrant_client():
    global _qdrant_client
    if _qdrant_client is None:
        from qdrant_client import QdrantClient

        url = os.environ.get("QDRANT_URL")
        if not url:
            raise ValueError("QDRANT_URL not set in environment / .env")
        api_key = os.environ.get("QDRANT_API_KEY")
        _qdrant_client = QdrantClient(
            url=url,
            api_key=api_key,
            timeout=120,
            check_compatibility=False,
        )
    return _qdrant_client


# ── Filter construction ─────────────────────────────────────────────


def build_metadata_filter(profile: Dict[str, Any]):
    """Build a Qdrant Filter from the user profile."""
    from qdrant_client.http import models

    gender = profile["gender"].lower()
    caste = profile["caste"].lower()
    state = profile["state"]
    age = int(profile["age"])

    must = [
        # Only eligibility + details for discovery
        models.FieldCondition(
            key="chunk_type",
            match=models.MatchAny(any=["eligibility", "details"]),
        ),
        # Gender: user's tag OR catch-all tags
        models.FieldCondition(
            key="gender_tags",
            match=models.MatchAny(any=[gender, "any", "unknown"]),
        ),
        # Caste: user's tag OR catch-all tags
        models.FieldCondition(
            key="caste_tags",
            match=models.MatchAny(any=[caste, "any", "unknown"]),
        ),
        # State OR Central ("India") — keeps central schemes in results
        models.FieldCondition(
            key="location_name",
            match=models.MatchAny(any=[state, CENTRAL_GOVT_LABEL]),
        ),
    ]

    # Age: include if scheme has no age restriction OR user is in range.
    age_filter = models.Filter(
        should=[
            models.FieldCondition(
                key="age_present",
                match=models.MatchValue(value=False),
            ),
            models.Filter(
                must=[
                    models.FieldCondition(
                        key="age_min_effective",
                        range=models.Range(lte=age),
                    ),
                    models.FieldCondition(
                        key="age_max_effective",
                        range=models.Range(gte=age),
                    ),
                ]
            ),
        ]
    )
    must.append(age_filter)

    return models.Filter(must=must)


# ── Query text construction ──────────────────────────────────────────


def build_search_query(profile: Dict[str, Any]) -> str:
    """Create a natural-language query from the user profile for semantic search."""
    parts = [
        f"Government scheme for a {profile['age']} year old",
        profile["gender"].lower(),
        f"from {profile['state']}",
        f"in {profile['area'].lower()} area",
        f"belonging to {profile['caste']} category",
        f"who is a {profile['profession'].lower()}",
    ]
    if profile.get("disability", "No") == "Yes":
        parts.append("with disability")
    return " ".join(parts)


# ── Grouping helpers ─────────────────────────────────────────────────


def _group_points_by_scheme(scored_points) -> List[SchemeResult]:
    """Aggregate scored Qdrant points into per-scheme results."""
    scheme_map: Dict[str, dict] = {}

    for point in scored_points:
        payload = point.payload or {}
        sid = payload.get("scheme_id", "")
        if not sid:
            continue

        if sid not in scheme_map:
            scheme_map[sid] = {
                "name": payload.get("scheme_name", ""),
                "url": payload.get("scheme_url", ""),
                "loc": payload.get("location_name", ""),
                "cat_id": payload.get("category_id", 0),
                "cat_name": payload.get("category_name", ""),
                "scores": [],
                "chunks": [],
            }

        info = scheme_map[sid]
        score = getattr(point, "score", None)
        info["scores"].append(float(score) if score is not None else 0.65)
        info["chunks"].append(
            {
                "text": payload.get("text", ""),
                "chunk_type": payload.get("chunk_type", ""),
                "chunk_index": payload.get("chunk_index", 0),
            }
        )

    results = [
        SchemeResult(
            scheme_id=sid,
            scheme_name=info["name"],
            scheme_url=info["url"],
            location_name=info["loc"],
            category_id=info["cat_id"],
            category_name=info["cat_name"],
            score=max(info["scores"]),
            chunks=info["chunks"],
        )
        for sid, info in scheme_map.items()
    ]
    results.sort(key=lambda r: r.score, reverse=True)
    return results


def _apply_profession_boost(
    schemes: List[SchemeResult], profile: Dict[str, Any]
) -> List[SchemeResult]:
    """Multiply score for schemes whose category matches the profession."""
    profession = profile.get("profession", "Other")
    target_cats = PROFESSION_CATEGORY_MAP.get(profession, [])
    if not target_cats:
        return schemes
    for s in schemes:
        if s.category_id in target_cats:
            s.score *= PROFESSION_BOOST
    schemes.sort(key=lambda r: r.score, reverse=True)
    return schemes


def _dedupe_scheme_results(schemes: List[SchemeResult]) -> List[SchemeResult]:
    """Keep one result per canonical scheme while preserving relevance order."""
    deduped: List[SchemeResult] = []
    seen: set[str] = set()

    for scheme in schemes:
        key = scheme.scheme_id or f"{scheme.scheme_name}|{scheme.scheme_url}"
        if key in seen:
            continue
        seen.add(key)
        deduped.append(scheme)

    return deduped


# ── Main discovery pipeline ──────────────────────────────────────────


def discover_schemes(
    profile: Dict[str, Any],
    top_k: int = DISCOVERY_TOP_K,
) -> tuple[List[SchemeResult], bool]:
    """
    Full discovery pipeline.

    Returns:
        (schemes, is_relaxed) — is_relaxed=True means strict filters had
        no results so filters were loosened.
    """
    qdrant_filter = build_metadata_filter(profile)
    client = get_qdrant_client()

    if not DISCOVERY_USE_SEMANTIC:
        try:
            points = _filtered_scroll(client, qdrant_filter, limit=DISCOVERY_INITIAL_FETCH)
        except Exception as exc:
            _raise_kb_unavailable(exc)

        if not points:
            try:
                points = _relaxed_filtered_scroll(client, profile, limit=DISCOVERY_INITIAL_FETCH)
            except Exception as exc:
                _raise_kb_unavailable(exc)
            if not points:
                return [], True
            schemes = _group_points_by_scheme(points)
            schemes = _apply_profession_boost(schemes, profile)
            return _dedupe_scheme_results(schemes), True

        schemes = _group_points_by_scheme(points)
        schemes = _apply_profession_boost(schemes, profile)
        return _dedupe_scheme_results(schemes), False

    emb = get_embedding_model()
    query_text = build_search_query(profile)
    dense_vecs, sparse_vecs = emb.embed_documents_hybrid([query_text])
    dense = dense_vecs[0]
    sparse = sparse_vecs[0]

    try:
        points = _hybrid_search(client, dense, sparse, qdrant_filter)
    except Exception as exc:
        _raise_kb_unavailable(exc)

    if not points:
        # Relax: drop caste + age filters
        try:
            points = _relaxed_search(client, dense, sparse, profile)
        except Exception as exc:
            _raise_kb_unavailable(exc)
        if not points:
            return [], True
        schemes = _group_points_by_scheme(points)
        schemes = _apply_profession_boost(schemes, profile)
        return _dedupe_scheme_results(schemes), True

    schemes = _group_points_by_scheme(points)
    schemes = _apply_profession_boost(schemes, profile)
    return _dedupe_scheme_results(schemes), False


def search_schemes_by_name(
    query_text: str,
    top_k: int = DISCOVERY_TOP_K,
) -> List[SchemeResult]:
    """
    Search schemes by KB scheme_name only.

    This path intentionally avoids semantic content retrieval so that results
    are returned only when the scheme title itself matches the user's query.
    """
    query_text = (query_text or "").strip()
    if not query_text:
        return []

    normalized_query = _normalize_scheme_name(query_text)
    query_tokens = _tokenize_scheme_name(query_text)
    if not normalized_query or not query_tokens:
        return []

    ranked_matches = []
    for scheme in _load_scheme_name_index():
        name = scheme["scheme_name"]
        normalized_name = scheme["normalized_name"]
        name_tokens = scheme["tokens"]
        score = _score_scheme_name_match(
            normalized_query,
            query_tokens,
            normalized_name,
            name_tokens,
        )
        if score < 0.45:
            continue

        ranked_matches.append(
            SchemeResult(
                scheme_id=scheme["scheme_id"],
                scheme_name=name,
                scheme_url=scheme["scheme_url"],
                location_name=scheme["location_name"],
                category_id=scheme["category_id"],
                category_name=scheme["category_name"],
                score=score,
                chunks=[],
            )
        )

    ranked_matches.sort(key=lambda s: (-s.score, len(s.scheme_name), s.scheme_name))
    return _dedupe_scheme_results(ranked_matches)


def _normalize_scheme_name(text: str) -> str:
    """Normalize scheme names/queries for strict title matching."""
    normalized = (text or "").lower()

    replacements = {
        "&": " and ",
        "/": " ",
        "-": " ",
        "_": " ",
        "yojna": " yojana ",
        "yojan": " yojana ",
    }
    for src, target in replacements.items():
        normalized = normalized.replace(src, target)

    # Expand a few common title-search abbreviations without changing KB data.
    normalized = re.sub(r"\bpm\b", "pradhan mantri", normalized)
    normalized = re.sub(r"\bcm\b", "chief minister", normalized)

    normalized = re.sub(r"[^a-z0-9\s]", " ", normalized)
    normalized = re.sub(r"\s+", " ", normalized).strip()
    return normalized


def _tokenize_scheme_name(text: str) -> List[str]:
    """Split a normalized scheme title into meaningful tokens."""
    return [tok for tok in _normalize_scheme_name(text).split() if tok]


def _score_scheme_name_match(
    normalized_query: str,
    query_tokens: List[str],
    normalized_name: str,
    name_tokens: List[str],
) -> float:
    """Rank candidate schemes using title-only similarity signals."""
    if not normalized_name:
        return 0.0

    if normalized_query == normalized_name:
        return 1.0

    if normalized_name.startswith(normalized_query):
        return 0.96

    if normalized_query in normalized_name:
        coverage = len(query_tokens) / max(len(name_tokens), 1)
        return 0.9 + min(coverage, 1.0) * 0.05

    query_token_set = set(query_tokens)
    name_token_set = set(name_tokens)
    overlap = len(query_token_set & name_token_set)
    token_recall = overlap / max(len(query_token_set), 1)
    token_precision = overlap / max(len(name_token_set), 1)
    fuzzy = SequenceMatcher(None, normalized_query, normalized_name).ratio()

    # Require at least a reasonably meaningful signal from the title itself.
    if overlap == 0 and fuzzy < 0.75:
        return 0.0

    return max(
        fuzzy * 0.78 + token_recall * 0.17 + token_precision * 0.05,
        token_recall * 0.82 + fuzzy * 0.18,
    )


@lru_cache(maxsize=1)
def _load_scheme_name_index() -> tuple[Dict[str, Any], ...]:
    """Load canonical scheme names from the knowledge base for title search."""
    schemes = load_all_schemes(verbose=False)
    index = []
    for scheme in schemes:
        normalized_name = _normalize_scheme_name(scheme.scheme_name)
        index.append(
            {
                "scheme_id": scheme.scheme_id,
                "scheme_name": scheme.scheme_name,
                "scheme_url": scheme.scheme_url,
                "location_name": scheme.location_name,
                "category_id": scheme.category_id,
                "category_name": scheme.category_name,
                "normalized_name": normalized_name,
                "tokens": tuple(tok for tok in normalized_name.split() if tok),
            }
        )
    return tuple(index)


def _hybrid_search(client, dense, sparse, qdrant_filter, limit=DISCOVERY_INITIAL_FETCH):
    """Try hybrid RRF search, fall back to dense-only."""
    from qdrant_client.http import models

    try:
        results = client.query_points(
            collection_name=QDRANT_COLLECTION_NAME,
            prefetch=[
                models.Prefetch(
                    query=dense,
                    using=DENSE_VECTOR_NAME,
                    limit=limit,
                    filter=qdrant_filter,
                ),
                models.Prefetch(
                    query=models.SparseVector(
                        indices=[int(i) for i in sparse["indices"]],
                        values=[float(v) for v in sparse["values"]],
                    ),
                    using=SPARSE_VECTOR_NAME,
                    limit=limit,
                    filter=qdrant_filter,
                ),
            ],
            query=models.FusionQuery(fusion=models.Fusion.RRF),
            limit=limit,
            with_payload=True,
        )
        return results.points
    except Exception as exc:
        print(f"[WARN] Hybrid search failed ({exc}), falling back to dense-only")
        return _dense_only_search(client, dense, qdrant_filter, limit)


def _dense_only_search(client, dense, qdrant_filter, limit=DISCOVERY_INITIAL_FETCH):
    from qdrant_client.http import models

    return client.search(
        collection_name=QDRANT_COLLECTION_NAME,
        query_vector=models.NamedVector(name=DENSE_VECTOR_NAME, vector=dense),
        query_filter=qdrant_filter,
        limit=limit,
        with_payload=True,
    )


def _relaxed_search(client, dense, sparse, profile, limit=50):
    """Drop caste & age filters; keep gender + state + chunk_type."""
    from qdrant_client.http import models

    relaxed = models.Filter(
        must=[
            models.FieldCondition(
                key="chunk_type",
                match=models.MatchAny(any=["eligibility", "details"]),
            ),
            models.FieldCondition(
                key="location_name",
                match=models.MatchAny(
                    any=[profile["state"], CENTRAL_GOVT_LABEL]
                ),
            ),
        ]
    )
    return _hybrid_search(client, dense, sparse, relaxed, limit=limit)


def _filtered_scroll(client, qdrant_filter, limit=DISCOVERY_INITIAL_FETCH):
    """Fetch profile-matching chunks without local embedding inference."""
    points, _ = client.scroll(
        collection_name=QDRANT_COLLECTION_NAME,
        scroll_filter=qdrant_filter,
        limit=limit,
        with_payload=True,
    )
    return points


def _relaxed_filtered_scroll(client, profile, limit=DISCOVERY_INITIAL_FETCH):
    """Relax profile matching without requiring a semantic query vector."""
    from qdrant_client.http import models

    relaxed = models.Filter(
        must=[
            models.FieldCondition(
                key="chunk_type",
                match=models.MatchAny(any=["eligibility", "details"]),
            ),
            models.FieldCondition(
                key="location_name",
                match=models.MatchAny(
                    any=[profile["state"], CENTRAL_GOVT_LABEL]
                ),
            ),
        ]
    )
    return _filtered_scroll(client, relaxed, limit=limit)


# ── Deep-dive: fetch all chunks for one scheme ──────────────────────


def fetch_scheme_chunks(scheme_id: str) -> List[Dict[str, Any]]:
    """Retrieve every chunk for a given scheme (all section types)."""
    from qdrant_client.http import models

    try:
        client = get_qdrant_client()
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
            limit=200,
            with_payload=True,
        )
    except Exception as exc:
        _raise_kb_unavailable(exc)

    TYPE_ORDER = [
        "details", "benefits", "eligibility", "application_process",
        "documents_required", "sources_and_references", "faq",
    ]

    chunks = []
    for pt in points:
        p = pt.payload or {}
        chunks.append(
            {
                "text": p.get("text", ""),
                "chunk_type": p.get("chunk_type", ""),
                "chunk_index": p.get("chunk_index", 0),
                "scheme_name": p.get("scheme_name", ""),
                "scheme_url": p.get("scheme_url", ""),
                "location_name": p.get("location_name", ""),
                "application_mode": p.get("application_mode", ""),
            }
        )

    chunks.sort(
        key=lambda c: (
            TYPE_ORDER.index(c["chunk_type"])
            if c["chunk_type"] in TYPE_ORDER
            else 99,
            c["chunk_index"],
        )
    )
    return chunks


def build_scheme_context(chunks: List[Dict[str, Any]], is_discovery: bool = False) -> str:
    """Assemble a structured text blob from scheme chunks for the LLM."""
    if not chunks:
        return ""

    name = chunks[0].get("scheme_name", "Unknown Scheme")
    url = chunks[0].get("scheme_url", "")
    loc = chunks[0].get("location_name", "")

    sections: Dict[str, List[str]] = defaultdict(list)
    for c in chunks:
        sections[c["chunk_type"]].append(c["text"])

    if is_discovery:
        labels = {
            "details": "DETAILS",
            "benefits": "BENEFITS",
        }
    else:
        labels = {
            "details": "DETAILS",
            "benefits": "BENEFITS",
            "eligibility": "ELIGIBILITY",
            "application_process": "APPLICATION PROCESS",
            "documents_required": "DOCUMENTS REQUIRED",
        }

    parts = [f"SCHEME: {name}", f"URL: {url}", f"Location: {loc}", ""]
    for ctype, label in labels.items():
        if ctype in sections:
            parts.append(f"[{label}]")
            parts.extend(sections[ctype])
            parts.append("")

    full_text = "\n".join(parts)
    
    if is_discovery and len(full_text) > 1200:
        full_text = full_text[:1200] + "\n...[TRUNCATED]"
        
    return full_text


# ── Quick CLI test ───────────────────────────────────────────────────

if __name__ == "__main__":
    test_profile = {
        "gender": "Male",
        "age": 22,
        "state": "Gujarat",
        "area": "Urban",
        "caste": "General",
        "disability": "No",
        "profession": "Student",
    }
    print("Query:", build_search_query(test_profile))
    print("Searching …")
    schemes, relaxed = discover_schemes(test_profile)
    tag = " (relaxed)" if relaxed else ""
    print(f"\nFound {len(schemes)} schemes{tag}:")
    for s in schemes[:5]:
        print(f"  [{s.score:.4f}] {s.scheme_name} — {s.location_name}")
