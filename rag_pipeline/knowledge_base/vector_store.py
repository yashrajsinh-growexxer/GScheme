"""
Qdrant vector store operations for ingestion with split stages:
- prepare-embeddings: local embedding generation + local file storage
- upsert-prepared: network-only upload to Qdrant
- upsert: one-shot (prepare + upsert-prepared)
- stats/reset helpers
"""
from __future__ import annotations

import json
import os
import time
import uuid
from pathlib import Path
from typing import Any, Dict, Generator, List

from dotenv import load_dotenv

from rag_pipeline.config import (
    CHUNKS_OUTPUT_DIR,
    DENSE_VECTOR_NAME,
    EMBEDDING_DIMENSION,
    EMBEDDINGS_OUTPUT_DIR,
    QDRANT_COLLECTION_NAME,
    SPARSE_VECTOR_NAME,
)
from rag_pipeline.knowledge_base.embeddings import get_embedding_model

load_dotenv()


def get_qdrant_client():
    """Initialize and return Qdrant client."""
    try:
        from qdrant_client import QdrantClient
    except ImportError as exc:
        raise ImportError(
            "qdrant-client not installed. Install with: pip install qdrant-client"
        ) from exc

    url = os.environ.get("QDRANT_URL")
    if not url:
        raise ValueError(
            "QDRANT_URL environment variable not set. "
            "Set it with: export QDRANT_URL='https://<cluster>.cloud.qdrant.io'"
        )
    api_key = os.environ.get("QDRANT_API_KEY")
    return QdrantClient(url=url, api_key=api_key, timeout=120)


def load_chunks(chunks_file: Path = CHUNKS_OUTPUT_DIR / "chunks.json") -> List[Dict]:
    """Load chunks from JSON file."""
    print(f"Loading chunks from {chunks_file}...")
    with open(chunks_file, "r", encoding="utf-8") as handle:
        chunks = json.load(handle)
    print(f"Loaded {len(chunks)} chunks")
    return chunks


def ensure_collection(collection_name: str = QDRANT_COLLECTION_NAME) -> None:
    """Create Qdrant collection if missing and ensure required payload indexes exist."""
    client = get_qdrant_client()
    from qdrant_client.http import models

    try:
        exists = client.collection_exists(collection_name=collection_name)
    except Exception:
        exists = False
        try:
            client.get_collection(collection_name=collection_name)
            exists = True
        except Exception:
            exists = False

    if not exists:
        print(f"Creating collection '{collection_name}'...")
        client.create_collection(
            collection_name=collection_name,
            vectors_config={
                DENSE_VECTOR_NAME: models.VectorParams(
                    size=EMBEDDING_DIMENSION,
                    distance=models.Distance.COSINE,
                )
            },
            sparse_vectors_config={SPARSE_VECTOR_NAME: models.SparseVectorParams()},
        )

    payload_indexes = [
        ("chunk_id", models.PayloadSchemaType.KEYWORD),
        ("scheme_id", models.PayloadSchemaType.KEYWORD),
        ("scheme_name", models.PayloadSchemaType.KEYWORD),
        ("location_name", models.PayloadSchemaType.KEYWORD),
        ("location_type", models.PayloadSchemaType.KEYWORD),
        ("category_id", models.PayloadSchemaType.INTEGER),
        ("gender_tags", models.PayloadSchemaType.KEYWORD),
        ("caste_tags", models.PayloadSchemaType.KEYWORD),
        ("age_present", models.PayloadSchemaType.BOOL),
        ("age_min_effective", models.PayloadSchemaType.INTEGER),
        ("age_max_effective", models.PayloadSchemaType.INTEGER),
        ("chunk_type", models.PayloadSchemaType.KEYWORD),
    ]
    for field_name, schema in payload_indexes:
        try:
            client.create_payload_index(
                collection_name=collection_name,
                field_name=field_name,
                field_schema=schema,
            )
        except Exception:
            pass


def _build_payload(chunk: Dict[str, Any]) -> Dict[str, Any]:
    """Build Qdrant payload from chunk metadata."""
    metadata = dict(chunk["metadata"])
    payload: Dict[str, Any] = {
        "chunk_id": chunk.get("id"),
        "scheme_id": metadata.get("scheme_id"),
        "scheme_name": (metadata.get("scheme_name") or "")[:200],
        "scheme_url": metadata.get("scheme_url"),
        "location_type": metadata.get("location_type"),
        "location_name": metadata.get("location_name"),
        "category_id": metadata.get("category_id"),
        "category_name": metadata.get("category_name"),
        "chunk_type": metadata.get("chunk_type"),
        "chunk_index": metadata.get("chunk_index"),
        "language": metadata.get("language"),
        "scraped_at": metadata.get("scraped_at"),
        "gender_tags": metadata.get("gender_tags", ["unknown"]),
        "caste_tags": metadata.get("caste_tags", ["unknown"]),
        "age_min": metadata.get("age_min"),
        "age_max": metadata.get("age_max"),
        "age_present": bool(metadata.get("age_present", False)),
        "age_confidence": float(metadata.get("age_confidence", 0.0)),
        "text": chunk["text"][:12000],
    }
    if "application_mode" in metadata:
        payload["application_mode"] = metadata["application_mode"]

    if payload["age_present"]:
        payload["age_min_effective"] = (
            0 if payload["age_min"] is None else int(payload["age_min"])
        )
        payload["age_max_effective"] = (
            120 if payload["age_max"] is None else int(payload["age_max"])
        )
    else:
        payload["age_min_effective"] = None
        payload["age_max_effective"] = None

    return payload


def _to_qdrant_point_id(raw_id: Any) -> str:
    """
    Convert arbitrary chunk IDs to a valid Qdrant point ID.
    Qdrant accepts unsigned integer or UUID.
    """
    if isinstance(raw_id, int) and raw_id >= 0:
        return str(raw_id)
    return str(uuid.uuid5(uuid.NAMESPACE_URL, str(raw_id)))


def _to_sparse_vector(models, sparse: Dict[str, List[float]]):
    """Convert dict sparse vector to Qdrant SparseVector model."""
    return models.SparseVector(
        indices=[int(i) for i in sparse.get("indices", [])],
        values=[float(v) for v in sparse.get("values", [])],
    )


def _prepared_file(path: Path | None = None) -> Path:
    """Default prepared embeddings file path."""
    if path is not None:
        return path
    EMBEDDINGS_OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    return EMBEDDINGS_OUTPUT_DIR / "prepared_vectors.jsonl"


def _iter_jsonl(path: Path) -> Generator[Dict[str, Any], None, None]:
    """Yield JSON objects from a JSONL file."""
    with open(path, "r", encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if not line:
                continue
            yield json.loads(line)


def prepare_embeddings(
    chunks_file: Path = CHUNKS_OUTPUT_DIR / "chunks.json",
    output_file: Path | None = None,
    batch_size: int = 64,
) -> Path:
    """
    Prepare vectors locally and save to disk as JSONL.
    This stage does not require Qdrant/network after model is cached.
    """
    output_path = _prepared_file(output_file)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    progress_file = output_path.parent / "prepare_embeddings_progress.json"

    chunks = load_chunks(chunks_file)
    total = len(chunks)
    embedding_model = get_embedding_model()

    start_idx = 0
    mode = "w"
    if progress_file.exists() and output_path.exists():
        with open(progress_file, "r", encoding="utf-8") as handle:
            start_idx = int(json.load(handle).get("last_completed_idx", 0))
        if start_idx > 0:
            mode = "a"
            print(f"Resuming local embedding prep from {start_idx}/{total}")

    prepared = start_idx
    failed = 0
    print(f"Preparing embeddings locally: {total} chunks, batch_size={batch_size}")
    print(f"Output: {output_path}")

    with open(output_path, mode, encoding="utf-8") as out:
        for i in range(start_idx, total, batch_size):
            batch = chunks[i:i + batch_size]
            texts = [item["text"] for item in batch]
            try:
                dense_vectors, sparse_vectors = embedding_model.embed_documents_hybrid(
                    texts,
                    batch_size=min(batch_size, 32),
                )

                for chunk, dense_vec, sparse_vec in zip(batch, dense_vectors, sparse_vectors):
                    record = {
                        "chunk_id": chunk["id"],
                        "point_id": _to_qdrant_point_id(chunk["id"]),
                        "dense": dense_vec,
                        "sparse": sparse_vec,
                        "payload": _build_payload(chunk),
                    }
                    out.write(json.dumps(record, ensure_ascii=False) + "\n")

                prepared += len(batch)
                with open(progress_file, "w", encoding="utf-8") as pf:
                    json.dump({"last_completed_idx": i + batch_size}, pf)
                print(f"  [{prepared}/{total}] Prepared batch {i // batch_size + 1}")
            except Exception as exc:  # noqa: BLE001
                failed += len(batch)
                print(f"  Error at batch {i // batch_size + 1}: {exc}")

    if progress_file.exists() and prepared >= total:
        progress_file.unlink()

    print("\n==================================================")
    print("Prepare embeddings complete!")
    print(f"  Prepared: {prepared}")
    print(f"  Failed:   {failed}")
    print("==================================================")
    return output_path


def upsert_prepared(
    prepared_file: Path | None = None,
    batch_size: int = 64,
    collection_name: str = QDRANT_COLLECTION_NAME,
) -> None:
    """
    Upload precomputed vectors to Qdrant.
    This stage requires internet/Qdrant, but no model inference.
    """
    prepared_path = _prepared_file(prepared_file)
    if not prepared_path.exists():
        raise FileNotFoundError(
            f"Prepared file not found: {prepared_path}. "
            "Run --action prepare-embeddings first."
        )

    ensure_collection(collection_name=collection_name)
    client = get_qdrant_client()
    from qdrant_client.http import models

    all_records = list(_iter_jsonl(prepared_path))
    total = len(all_records)
    if total == 0:
        print(f"No prepared vectors found in {prepared_path}")
        return

    progress_file = prepared_path.parent / "upsert_prepared_progress.json"
    start_idx = 0
    if progress_file.exists():
        with open(progress_file, "r", encoding="utf-8") as handle:
            start_idx = int(json.load(handle).get("last_completed_idx", 0))
            if start_idx > 0:
                print(f"Resuming upsert-prepared from {start_idx}/{total}")

    upserted = start_idx
    failed = 0
    print(f"Uploading prepared vectors: {total} records, batch_size={batch_size}")

    for i in range(start_idx, total, batch_size):
        batch = all_records[i:i + batch_size]
        try:
            points = [
                models.PointStruct(
                    id=item["point_id"],
                    vector={
                        DENSE_VECTOR_NAME: item["dense"],
                        SPARSE_VECTOR_NAME: _to_sparse_vector(models, item["sparse"]),
                    },
                    payload=item["payload"],
                )
                for item in batch
            ]
            client.upsert(
                collection_name=collection_name,
                points=points,
                wait=False,
            )
            upserted += len(points)

            with open(progress_file, "w", encoding="utf-8") as pf:
                json.dump({"last_completed_idx": i + batch_size}, pf)
            print(f"  [{upserted}/{total}] Upserted batch {i // batch_size + 1}")
        except Exception as exc:  # noqa: BLE001
            failed += len(batch)
            print(f"  Error at batch {i // batch_size + 1}: {exc}")

        time.sleep(0.05)

    if progress_file.exists() and upserted >= total:
        progress_file.unlink()

    print("\n==================================================")
    print("Upsert prepared complete!")
    print(f"  Successful: {upserted}")
    print(f"  Failed:     {failed}")
    print("==================================================")
    stats = get_collection_stats(collection_name=collection_name)
    print(f"Collection points: {stats.get('points_count', 'N/A')}")


def run_upsert_pipeline(
    chunks_file: Path = CHUNKS_OUTPUT_DIR / "chunks.json",
    batch_size: int = 64,
    collection_name: str = QDRANT_COLLECTION_NAME,
    prepared_file: Path | None = None,
) -> None:
    """
    One-shot mode: prepare embeddings locally then upload.
    """
    prepared_path = prepare_embeddings(
        chunks_file=chunks_file,
        output_file=prepared_file,
        batch_size=batch_size,
    )
    upsert_prepared(
        prepared_file=prepared_path,
        batch_size=batch_size,
        collection_name=collection_name,
    )


def get_collection_stats(collection_name: str = QDRANT_COLLECTION_NAME) -> Dict[str, Any]:
    """Get Qdrant collection stats."""
    client = get_qdrant_client()
    info = client.get_collection(collection_name=collection_name)
    if hasattr(info, "model_dump"):
        return info.model_dump()
    if hasattr(info, "dict"):
        return info.dict()
    return {"info": str(info)}


def delete_all_vectors(collection_name: str = QDRANT_COLLECTION_NAME) -> None:
    """Delete and recreate collection (use with caution)."""
    client = get_qdrant_client()
    try:
        client.delete_collection(collection_name=collection_name)
    except Exception:
        pass
    ensure_collection(collection_name=collection_name)
    print(f"Reset collection '{collection_name}'")


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Qdrant ingestion operations")
    parser.add_argument(
        "--action",
        choices=["prepare-embeddings", "upsert-prepared", "upsert", "stats", "reset"],
        default="stats",
        help="Action to perform",
    )
    parser.add_argument("--batch-size", type=int, default=64, help="Batch size")
    parser.add_argument(
        "--prepared-file",
        type=str,
        default=None,
        help="Path to prepared embeddings JSONL file",
    )
    args = parser.parse_args()

    prepared_file = Path(args.prepared_file) if args.prepared_file else None

    if args.action == "prepare-embeddings":
        prepare_embeddings(batch_size=args.batch_size, output_file=prepared_file)
    elif args.action == "upsert-prepared":
        upsert_prepared(batch_size=args.batch_size, prepared_file=prepared_file)
    elif args.action == "upsert":
        run_upsert_pipeline(batch_size=args.batch_size, prepared_file=prepared_file)
    elif args.action == "stats":
        stats = get_collection_stats()
        print(json.dumps(stats, indent=2, default=str))
    elif args.action == "reset":
        confirm = input("Reset collection and delete all vectors? (yes/no): ")
        if confirm.strip().lower() == "yes":
            delete_all_vectors()
        else:
            print("Cancelled.")
