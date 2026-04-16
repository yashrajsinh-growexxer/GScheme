"""
Cross-encoder reranker using BGE-reranker via FlagEmbedding.

Reranks scheme candidates by computing (query, passage) relevance scores
with a cross-encoder, improving precision over bi-encoder retrieval alone.
"""
from __future__ import annotations

from typing import List, Tuple

try:
    from .config import RERANKER_MODEL
except ImportError:
    from config import RERANKER_MODEL


class Reranker:
    """Lazy-loaded BGE cross-encoder reranker."""

    def __init__(self, model_name: str = RERANKER_MODEL):
        self.model_name = model_name
        self._model = None

    def _load(self):
        if self._model is None:
            try:
                from FlagEmbedding import FlagReranker
            except ImportError as exc:
                raise ImportError(
                    "FlagEmbedding not installed. "
                    "Install with: pip install FlagEmbedding"
                ) from exc
            print(f"Loading reranker model: {self.model_name}")
            self._model = FlagReranker(self.model_name, use_fp16=True)
            print("Reranker loaded.")
        return self._model

    def rerank(
        self,
        query: str,
        passages: List[str],
        top_k: int | None = None,
    ) -> List[Tuple[int, float]]:
        """
        Score each passage against the query and return sorted indices.

        Returns:
            List of (original_index, score) sorted descending.
        """
        if not passages:
            return []

        model = self._load()

        pairs = [[query, p] for p in passages]
        scores = model.compute_score(pairs)

        # compute_score returns a float for single pair, list for multiple
        if isinstance(scores, (int, float)):
            scores = [scores]

        indexed = list(enumerate(scores))
        indexed.sort(key=lambda x: x[1], reverse=True)

        if top_k is not None:
            indexed = indexed[:top_k]

        return indexed


# Singleton
_reranker: Reranker | None = None


def get_reranker() -> Reranker:
    global _reranker
    if _reranker is None:
        _reranker = Reranker()
    return _reranker


if __name__ == "__main__":
    r = get_reranker()
    q = "Scholarship for SC student in Gujarat aged 20"
    passages = [
        "This scheme provides scholarship to SC students in Gujarat aged 18-25.",
        "Housing loan subsidy for urban families in Maharashtra.",
        "Financial assistance for tribal farmers in Rajasthan.",
    ]
    results = r.rerank(q, passages)
    for idx, score in results:
        print(f"  [{score:.4f}] {passages[idx][:80]}")
