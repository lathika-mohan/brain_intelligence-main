# Qdrant Vector Collection Specification (Phase 0)

Status: **FROZEN** for Phase 0. Code constants: `app/vector/schema.py`.
Bootstrap script: `scripts/init_qdrant_collections.py`.

---

## 1. Embedding Model

| Setting              | Value                                            |
|----------------------|---------------------------------------------------|
| Model                | `sentence-transformers/all-MiniLM-L6-v2`          |
| Vector dimensions    | **384**                                            |
| Distance metric      | **Cosine**                                         |
| Max sequence length  | 256 tokens                                         |
| Device               | CPU by default (`EMBEDDING_DEVICE` env override)   |

`all-MiniLM-L6-v2` was selected for Phase 0 as the balanced default:
384-dim vectors keep Qdrant memory/index size modest while retaining
strong semantic retrieval quality for SOP/manual-length passages. This is
overridable per environment via `EMBEDDING_MODEL_NAME` — if changed,
`QDRANT_VECTOR_SIZE` **must** be updated to match the new model's output
dimensionality, and collections must be recreated (dimension is immutable
per-collection in Qdrant).

---

## 2. Collections

| Collection name        | Purpose                                             | Source docs                          |
|--------------------------|------------------------------------------------------|----------------------------------------|
| `sop_documents`         | Standard Operating Procedures                        | SOP PDFs / markdown                   |
| `technical_manuals`     | OEM technical/service manuals                        | Manual PDFs                           |
| `incident_reports`      | Historical incident / maintenance-log narratives     | Incident report exports, work orders  |

All three collections share the identical vector config:

```json
{ "size": 384, "distance": "Cosine" }
```

## 3. Point Payload Schema

Every point (across all 3 collections) carries this payload
(`VectorPayloadSchema` in `app/vector/schema.py`):

```json
{
  "chunk_id": "string (uuid, matches point ID)",
  "text": "string — the retrievable passage",
  "source_document": "string — filename or doc identifier",
  "source_type": "SOP | MANUAL | INCIDENT_REPORT | MAINTENANCE_LOG",
  "asset_types": ["PUMP", "MOTOR", "..."],
  "asset_ids": ["asset-101", "..."],
  "page_number": 3,
  "revision": "Rev. C",
  "ingested_at": "2026-07-02T00:00:00Z"
}
```

`asset_types` / `asset_ids` are indexed as Qdrant payload filters so the
GraphRAG request's `asset_ids` / `asset_types` filters (see
`GraphRagQueryRequest` in `app/models/graphrag.py`) map directly to a
Qdrant `Filter` clause without any translation layer.

## 4. Recommended Payload Indexes

```python
client.create_payload_index(collection_name, field_name="asset_ids", field_schema="keyword")
client.create_payload_index(collection_name, field_name="asset_types", field_schema="keyword")
client.create_payload_index(collection_name, field_name="source_type", field_schema="keyword")
```

## 5. Frontend Fusion Mapping

Each Qdrant point retrieved during a GraphRAG query is surfaced to
`GraphRagPanel.tsx` as a `VectorContextChunk`:

```json
{
  "chunk_id": "...",
  "text": "...",
  "source_document": "...",
  "source_type": "SOP",
  "confidence_score": 0.82,
  "page_number": 3
}
```

`confidence_score` = the Qdrant cosine similarity score (optionally
re-ranked) at retrieval time — not stored in the payload itself.
