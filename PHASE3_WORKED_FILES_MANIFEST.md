# Phase 3 Worked Files Manifest

Generated: 2026-07-03  
Scope: Knowledge Extraction Pipeline (Member 3 — AI & Knowledge Engineer)  
Integration: Phase 0 contracts + Phase 1 ontology + Phase 2 Neo4j repository

## New deliverables — ingestion engine

| Path | Purpose |
|---|---|
| `app/ingestion/__init__.py` | Package marker, version 3.0.0 |
| `app/ingestion/schemas.py` | Strict Pydantic v2 extraction schemas (ExtractedEntity, ExtractedRelationship, ExtractionResult, ChunkMetadata, ParsedDocument, GraphLoadBatch). Enforces Phase 1 ontology boundaries and UPPERCASE_SNAKE_CASE relationship validation. |
| `app/ingestion/prompts.py` | Production-grade Industry 5.0 prompts. Injects Phase 1 Entity Dictionary + Relationship Catalogue. Includes few-shot anchors and entity resolution instructions. |
| `app/ingestion/pdf_parser.py` | Multi-format extraction engine: pdfplumber → PyMuPDF → pypdf fallback. Layout-aware cleansing strips headers, footers, page numbers, index listings. Tables converted to JSON strings. Preserves document metadata (source_filename, document_category, total_pages, section_identifiers). |
| `app/ingestion/chunker.py` | Semantic sliding-window chunker: 512–1024 tokens, 10–20% overlap (default 768 / 120). Uses langchain-text-splitters TokenTextSplitter with sentence-aware fallback. Deterministic SHA-256 chunk_id, full Context Preservation Hierarchy (document_id, section_title, chunk_index, parent_metadata). |
| `app/ingestion/entity_resolver.py` | Entity Resolution & Standardization. Canonical alias map normalizes "Centrifugal Pump A", "Pump-A", "CP-A" → `asset:SRP:P-101A`. Deduplicates by entity_id, merges aliases, preserves max confidence. |
| `app/ingestion/extractor.py` | LLM-driven triple generation. Structured output via instructor / OpenAI function calling. Deterministic mock extractor fallback for CI (no API key). Outputs (Source) -> [RELATIONSHIP] -> (Target) with required edge props (metric, confidence_weight, sequence_number). |
| `app/ingestion/graph_loader.py` | Idempotent graph loading. Wraps `Neo4jGraphRepository` MERGE patterns. Upserts :TextChunk nodes, links [:MENTIONS] and [:GROUNDS_ENTITY] for auditability. Batch transactional execution with counters. |
| `app/ingestion/validator.py` | Data Quality Assertions: zero isolated nodes without provenance, relationship UPPERCASE_SNAKE_CASE conformity, chunk traceability, required edge properties (EXHIBITS_ANOMALY.metric, HAS_STEP.sequence_number). Includes live Neo4j Cypher integrity checks. |
| `app/ingestion/pipeline.py` | End-to-end orchestrator: parse → chunk → extract → resolve → validate → load. CLI entrypoint `python -m app.ingestion.pipeline <file.pdf>`. Auto-detects Neo4j, falls back to dry-run. |

## API integration (optional, backend-ready)

| Path | Purpose |
|---|---|
| `app/api/v1/document_ingestion.py` | FastAPI router exposing POST `/api/v1/ingestion/document` (multipart upload → pipeline) and GET `/api/v1/ingestion/pipeline/health`. Gracefully degrades if Neo4j unavailable. |
| `app/api/v1/router.py` | Updated to include document_ingestion_router with try/except guard — existing GraphRAG / XAI routes untouched. |

## Tests

| Path | Purpose |
|---|---|
| `tests/test_phase3_ingestion_pipeline.py` | End-to-end integration test: 1) PDF parser layout cleansing + table extraction, 2) Semantic chunking (512-1024 tokens, 10-20% overlap, deterministic hash IDs), 3) LLM structured extraction + entity resolution, 4) Idempotent graph loading + validation, 5) Full pipeline run against sample SOP PDF (`tests/data/sample_sop_p101a.pdf`). All 5 tests pass (mock extractor, no external LLM required). |

## Restored Phase 1 / Phase 0 contracts (required for integration)

The Phase 2 commit in the upstream repo accidentally deleted core contract files. They are restored here to make Phase 3 executable, with zero logic changes:

- `app/models/ontology.py` — Phase 1 Pydantic interfaces, enums, ID strategies, RELATIONSHIP_CATALOG
- `app/models/graphrag.py` — GraphRAG Engine contracts
- `app/models/predictive.py` — Predictive Maintenance contracts
- `app/models/telemetry.py` — Upstream telemetry contract
- `app/graph/schema.py` — Canonical node/relationship constants + Phase 0 alias compatibility
- `app/api/v1/graphrag.py` — GraphRAG stub router
- `app/api/v1/xai.py` — XAI stub router

## Dependencies updated

`requirements.txt` appended Phase 3 pipeline stack:
- pypdf==5.0.1, pdfplumber==0.11.4, pymupdf==1.24.9
- langchain-text-splitters==0.3.0, tiktoken==0.7.0
- instructor==1.6.2, openai==1.54.0, anthropic==0.40.0
- reportlab==4.2.2 (test PDF generation)
- python-magic==0.4.27

## Validation performed

```bash
pytest tests/test_phase1_ontology.py -q
# 3 passed

pytest tests/test_phase3_ingestion_pipeline.py -q
# 5 passed

pytest tests/test_phase2_graph_integration.py -q
# 7 skipped (no live Neo4j in CI — expected, fixtures skip cleanly)

ruff check app tests
# All checks passed
```

Pipeline dry-run output (mock extractor):
```
{
  "success": true,
  "document_id": "document:SOP:SAMPLE_SOP_P101A:…",
  "chunks": 2,
  "entities_extracted": 6,
  "relationships_extracted": 5,
  "validation": {"passed": true, "error_count": 0, ...},
  "load_report": {"chunks_stored": 2, "nodes_upserted": 6, "relationships_created": 11, ...}
}
```

## Output expectations — compliance matrix

1. **Modular pipeline scripts** ✓
   - `pdf_parser.py`, `chunker.py`, `extractor.py`, `graph_loader.py` (+ `pipeline.py`, `schemas.py`, `prompts.py`, `entity_resolver.py`, `validator.py`)
2. **Production prompts + Pydantic schemas** ✓
   - `app/ingestion/prompts.py` (system prompt injects Phase 1 Entity Dictionary + Relationship Catalogue)
   - `app/ingestion/schemas.py` (strict structured JSON, triple validation)
3. **End-to-end integration test** ✓
   - `tests/test_phase3_ingestion_pipeline.py` executes full pipeline against sample technical manual PDF, verifies Neo4j population (dry-run mode if no DB)
4. **Zero UI assets** ✓ — 100% backend data pipeline focus

## Handoff notes

- Credentials: uses Phase 0 `app.core.config.Settings` (`NEO4J_URI`, `OPENAI_API_KEY`)
- Graph writes: all MERGE-based via `app.graph.graph_repository.Neo4jGraphRepository`
- Chunk nodes: `:TextChunk` label per Phase 1, linked via `[:MENTIONS]` and `[:GROUNDS_ENTITY]` with `claim_field`, `confidence_score`
- IDs follow `app.models.ontology.ID_STRATEGY_BY_LABEL`
- Set `OPENAI_API_KEY` to use real LLM; otherwise mock extractor provides deterministic CI-safe output
- Run: `python -m app.ingestion.pipeline ./manual.pdf --category SOP --mock`
