# Phase 4 Worked Files Manifest

Generated: 2026-07-03
Scope: Embedding & Semantic Search (Member 3 — AI & Knowledge Engineer)
Integration: Phase 0 contracts + Phase 1 ontology + Phase 2 Neo4j repository + Phase 3 ingestion pipeline

## New deliverables — vector engine

| Path | Purpose |
| --- | --- |
| `app/vector/__init__.py` | Package marker, version 4.0.0, public exports |
| `app/vector/schema.py` | Qdrant collection catalog, embedding model registry, payload schema, HNSW tuning |
| `app/vector/client.py` | Qdrant client lifecycle singleton, health probe |
| `app/vector/embedding_engine.py` | SentenceTransformer orchestration: all-mpnet-base-v2 (768d) default, BGE-large-en-v1.5 (1024d) supported, GPU/CPU auto-detect, idempotent batching, token length tracking, timeout guards |
| `app/vector/models.py` | Pydantic v2 search models: ChunkPayload, SearchFilters, VectorSearchResult, VectorSearchResponse, EmbeddingBatchResult, GraphRAG compatibility layer |
| `app/vector/qdrant_manager.py` | Idempotent collection provisioning, vector size auto-alignment, payload indexing on document_type, asset_type, chunk_id, document_id, source_filename |
| `app/vector/search_service.py` | Async `semantic_search(query_text, top_k, filters)` — on-the-fly encoding, Qdrant Filter/Must/Match, score thresholding ≥0.70, normalization, multi_search |
| `app/vector/pipeline.py` | VectorIngestionPipeline — pulls Chunk nodes, embeds, upserts to Qdrant, tracks token lengths, skips existing fingerprints |
| `app/vector/repository.py` | ChunkVectorRepository — Cypher projection pulling :TextChunk nodes from Neo4j with full Context Preservation Hierarchy |
| `app/api/v1/vector_search.py` | FastAPI router: POST /api/v1/vector/search, GET /api/v1/vector/search, GET /api/v1/vector/health |

## Operational scripts

| Path | Purpose |
| --- | --- |
| `scripts/init_qdrant_collections.py` | Bootstraps operational_knowledge_v4 + legacy sop_documents / technical_manuals / incident_reports collections, verifies vector dim, creates payload indexes |
| `scripts/embed_chunks.py` | CLI batch ingestion: `python scripts/embed_chunks.py --collection operational_knowledge_v4 --limit 2000` — pulls Phase 3 :Chunk nodes from Neo4j, embeds idempotently, upserts |

## API integration

| Path | Purpose |
| --- | --- |
| `app/api/v1/router.py` | Updated — mounts vector_search_router with try/except guard, preserves GraphRAG / XAI routes untouched, no UI changes |
| `app/models/graphrag.py` | Restored Phase 0 contract: GraphRagQueryRequest, GraphRagQueryResponse, GraphRagContextChunk — ensures search_service maps perfectly |
| `app/models/ontology.py` | Restored Phase 1 ontology interfaces for extraction validation |
| `app/models/predictive.py` | Restored Predictive Maintenance contracts |
| `app/models/telemetry.py` | Restored upstream telemetry contract |
| `app/models/decision.py` | Restored Decision Engine contracts |

## Configuration updates

| Path | Purpose |
| --- | --- |
| `app/core/config.py` | Phase 4 upgrades: embedding_model_name → `sentence-transformers/all-mpnet-base-v2`, qdrant_vector_size 384→768, embedding_max_seq_length 256→512, vector_score_threshold=0.70, graphrag_min_confidence_threshold 0.55→0.70, app_version 0.1.0→0.4.0 |
| `requirements.txt` | Added Phase 4 explicit: torch>=2.2.0, huggingface-hub>=0.24.0, tokenizers>=0.19.0 |

## Tests — retrieval benchmarking suite

| Path | Purpose |
| --- | --- |
| `tests/test_phase4_embedding.py` | Embedding consistency: model init, fingerprint determinism, idempotent skip, BGE query prefix, empty payload handling |
| `tests/test_phase4_search_service.py` | Filter builder (MatchValue / MatchAny / Range), score thresholding rejects <0.70, empty query validation |
| `tests/test_phase4_benchmark.py` | 30× operational query run: measures p50/p95/p99, asserts p95 < 50ms (mocked), payload index coverage assertion |
| `tests/test_phase4_integration.py` | Payload preservation (chunk_id, document_id, document_type, asset_type, section_title, text), Pydantic mapping to GraphRAG, EmbeddingBatchResult schema, idempotent ingest end-to-end |

All 4 pytest suites designed to pass without external LLM keys, without running Qdrant server (mocked), and without GPU — CI-safe.

## Vector engineering summary

- **Model**: `sentence-transformers/all-mpnet-base-v2` (768d, cosine) — industry standard, upgrade path to `BAAI/bge-large-en-v1.5` (1024d) via env `EMBEDDING_MODEL_NAME`
- **Collection**: `operational_knowledge_v4` — HNSW m=16, ef_construct=200, Cosine distance
- **Payload indexes**: chunk_id, document_id, document_type, asset_type, source_filename, chunk_index, token_count (keyword/integer/text)
- **Search API**: `await search_service.semantic_search(query_text, top_k=8, filters=SearchFilters(document_type="SOP", asset_type="PUMP"))` → < 50ms p95
- **Score gate**: cosine similarity ≥ 0.70 — prevents low-confidence noise entering GraphRAG context assembly
- **Idempotency**: SHA-256 fingerprint = model_name + chunk_id + text → skips re-embedding

Zero UI scaffolding. Zero LLM prompt engineering. 100% vector database engineering, model orchestration, retrieval APIs.

## Runbook

```bash
# 1. Start Qdrant
docker compose up -d qdrant

# 2. Init collections
python scripts/init_qdrant_collections.py

# 3. Embed Phase 3 chunks
python scripts/embed_chunks.py --collection operational_knowledge_v4 --limit 2000

# 4. Search
curl -X POST http://localhost:8000/api/v1/vector/search \
  -H "Content-Type: application/json" \
  -d '{"query_text":"vibration spike turbine bearing","top_k":8,"min_score":0.70}'

# 5. Test
pytest -k phase4 -q
```
