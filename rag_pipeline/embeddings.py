"""
Embedding setup using BGE-M3 via FlagEmbedding.
"""
from __future__ import annotations

from typing import Dict, List, Sequence, Tuple

try:
    from .config import EMBEDDING_DIMENSION, EMBEDDING_MODEL
except ImportError:
    from config import EMBEDDING_DIMENSION, EMBEDDING_MODEL


SparseVector = Dict[str, List[float]]


class EmbeddingModel:
    """Wrapper for BGE-M3 dense+sparse embeddings."""

    def __init__(
        self,
        model_name: str = EMBEDDING_MODEL,
    ):
        self.model_name = model_name
        self.dimension = EMBEDDING_DIMENSION
        self._embedder = None

    def _load_embedder(self):
        """Lazy-load BGE-M3 embedder."""
        if self._embedder is None:
            try:
                from FlagEmbedding import BGEM3FlagModel
            except ImportError as exc:
                raise ImportError(
                    "FlagEmbedding not installed. Install with: pip install FlagEmbedding"
                ) from exc

            print(f"Loading hybrid embedding model: {self.model_name}")
            self._embedder = BGEM3FlagModel(self.model_name, use_fp16=True)
            print(f"Model loaded. Dense dimension (expected): {self.dimension}")
        return self._embedder

    @staticmethod
    def _normalize_sparse_vector(weights: Dict) -> SparseVector:
        """
        Convert BGE-M3 lexical weights map to Qdrant sparse format.
        """
        indices: List[int] = []
        values: List[float] = []

        if not isinstance(weights, dict):
            return {"indices": indices, "values": values}

        for key, value in weights.items():
            if value is None:
                continue
            try:
                idx = int(key)
            except (ValueError, TypeError):
                # Fallback if key is non-integer token form.
                idx = abs(hash(str(key))) % (2**31 - 1)
            indices.append(idx)
            values.append(float(value))

        return {"indices": indices, "values": values}

    def _encode_hybrid(
        self,
        texts: Sequence[str],
        batch_size: int = 32,
    ) -> Tuple[List[List[float]], List[SparseVector]]:
        """Encode texts into dense+sparse vectors."""
        model = self._load_embedder()
        encoded = model.encode(
            list(texts),
            batch_size=batch_size,
            max_length=2048,
            return_dense=True,
            return_sparse=True,
            return_colbert_vecs=False,
        )
        dense = encoded.get("dense_vecs", [])
        sparse = encoded.get("lexical_weights", [])

        # Normalize numpy / list / dict outputs without ambiguous truth checks.
        if dense is None:
            dense = []
        elif hasattr(dense, "tolist"):
            dense = dense.tolist()
        elif not isinstance(dense, list):
            dense = list(dense)

        if sparse is None:
            sparse = []
        elif isinstance(sparse, dict):
            sparse = [sparse]
        elif hasattr(sparse, "tolist") and not isinstance(sparse, list):
            sparse = sparse.tolist()
        elif not isinstance(sparse, list):
            sparse = list(sparse)

        # Ensure list output for single-text calls.
        if len(dense) > 0 and isinstance(dense[0], (int, float)):
            dense = [dense]
        if len(sparse) > 0 and isinstance(sparse, dict):
            sparse = [sparse]

        dense_vectors = [list(map(float, vec)) for vec in dense]
        sparse_vectors = [self._normalize_sparse_vector(weights) for weights in sparse]
        return dense_vectors, sparse_vectors

    def embed_documents(self, texts: List[str], batch_size: int = 32) -> List[List[float]]:
        """Dense-only document embeddings (compatibility helper)."""
        dense, _ = self._encode_hybrid(texts, batch_size=batch_size)
        return dense

    def embed_documents_hybrid(
        self, texts: List[str], batch_size: int = 32
    ) -> Tuple[List[List[float]], List[SparseVector]]:
        """Hybrid embeddings for multiple documents."""
        return self._encode_hybrid(texts, batch_size=batch_size)

# Singleton instance
_embedding_model = None


def get_embedding_model() -> EmbeddingModel:
    """Get or create the singleton embedding model instance."""
    global _embedding_model
    if _embedding_model is None:
        _embedding_model = EmbeddingModel()
    return _embedding_model


if __name__ == "__main__":
    model = get_embedding_model()
    texts = ["Sample scheme details text for embedding."]
    dense, sparse = model.embed_documents_hybrid(texts)
    print(f"Dense dimension: {len(dense[0])}")
    print(f"Sparse terms: {len(sparse[0]['indices'])}")
