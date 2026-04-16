# Government Schemes Knowledge Base Pipeline

## What This Pipeline Does
1. Reads raw per-scheme JSON files from `data/schemes_data_json`.
2. Creates enriched per-scheme JSON files in `data/schemes_enriched_json` with structured metadata for filtering:
   - `location_name`, `location_type`
   - `gender_tags`
   - `caste_tags`
   - `age_min`, `age_max`, `age_present`
3. Chunks scheme sections with section-aware recursive chunking + overlap.
4. Generates hybrid embeddings using `BAAI/bge-m3` (dense + sparse via FlagEmbedding).
5. Supports split ingestion:
   - prepare embeddings locally
   - upsert prepared vectors later when internet is available
6. Uploads filter-ready payload metadata and vectors to Qdrant.

## Why Per-Scheme Files Stay Separate
- Raw source files remain unchanged for auditability and scraper compatibility.
- Enriched files are written separately, preserving one-file-per-scheme structure.
- This enables incremental updates and easy debugging.

## Metadata Filtering
These filters are prepared in payload metadata and stored with each vector:
- `state` (maps to `location_name`)
- `gender`
- `caste`
- `age`

## Chunking Strategy
- Section-aware first:
  - `details`, `benefits`, `eligibility`, `documents_required`, `sources_and_references`
  - `application_process` split by mode (`online`, `offline`, `unspecified`) before recursive splitting
- Recursive splitting + overlap for long sections
- FAQ remains one chunk per Q/A

## Files
- `config.py`: shared constants (paths, chunk config, embedding and Qdrant settings)
- `enrich_metadata.py`: builds enriched per-scheme JSON files
- `data_loader.py`: loads normalized scheme objects (enriched preferred, raw fallback)
- `chunker.py`: creates chunks with metadata
- `embeddings.py`: BGE-M3 dense+sparse embedding wrapper
- `vector_store.py`: prepare embeddings, Qdrant upsert/stats/reset operations
- `setup.sh`: dependency and bootstrap script

## Setup
```bash
cd rag_pipeline
bash setup.sh
```

Add environment variables in `.env`:
```bash
QDRANT_URL=https://<cluster>.cloud.qdrant.io
QDRANT_API_KEY=<your-key>
```

## Run Pipeline
```bash
cd rag_pipeline
python enrich_metadata.py
python chunker.py

# Stage 1: local (offline after first model cache)
python vector_store.py --action prepare-embeddings --batch-size 64

# Stage 2: network only (Qdrant upload)
python vector_store.py --action upsert-prepared --batch-size 64
```

Prepared vectors are stored at:
`data/prepared_embeddings/prepared_vectors.jsonl`
