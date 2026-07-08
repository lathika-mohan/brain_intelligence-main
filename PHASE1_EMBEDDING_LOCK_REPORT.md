# Phase 1 — Embedding Mismatch Lock | Worked Files Manifest

**Target:** Resolve Embedding Mismatch & Lock Vector Layer Configuration  
**Date:** 2026-07-08  
**Model Lock:** `sentence-transformers/all-mpnet-base-v2` — **768d**  
**Time Box:** 2 Hours

---

## 1. Code-Level Configuration Adjustment

### `config.py` (repo root)
- Framework-agnostic, `os.getenv` driven
- Defaults: 
  ```
  EMBEDDING_MODEL_NAME = "all-mpnet-base-v2"
  VECTOR_DIMENSION = 768
  ```
- Validation guard:
  ```python
  if "mpnet" in EMBEDDING_MODEL_NAME and VECTOR_DIMENSION != 768:
      raise ValueError(...)
  elif "MiniLM" in EMBEDDING_MODEL_NAME and VECTOR_DIMENSION != 384:
      raise ValueError(...)
  ```
- Auto-syncs with `app.core.config.get_settings()` if available — zero drift between legacy scripts and FastAPI.

### `app/core/config.py`
Full Pydantic v2 Settings with Phase 1 hard gate:

- `embedding_model_name: str = "sentence-transformers/all-mpnet-base-v2"`
- `qdrant_vector_size: int = 768`
- Added `@model_validator(mode="after") def _validate_embedding_dimensions()`
  - mpnet → 768d
  - MiniLM → 384d
  - bge-large → 1024d
  - bge-base → 768d
  - bge-small → 384d
  - Raises `ValueError` on mismatch, preventing silent Qdrant init failures
- Exports legacy constants at module bottom for `from config import EMBEDDING_MODEL_NAME, VECTOR_DIMENSION` compatibility

Integration points unchanged:
- `app/vector/embedding_engine.py` — auto-upgrades MiniLM → mpnet, reads `settings.embedding_model_name`
- `app/vector/qdrant_manager.py` — auto-aligns `vector_size` to `engine.vector_dim`, validates existing collection size
- `app/vector/schema.py` — `DEFAULT_EMBEDDING_MODEL = "sentence-transformers/all-mpnet-base-v2"`, `DEFAULT_VECTOR_DIM = 768`

### `app/vector/embedding_validator.py` (NEW)
Standalone validator shared across teams:
- `resolve_embedding_dim(model_name)`
- `validate_embedding_config(model_name, vector_dimension)`
- `assert_embedding_config(...)`
- Used by Member 1 / Member 2 CI gates

---

## 2. Environment Documentation Update

### `.env.example` (repo root)
AI/ML & Vector Engine Configuration block added:
```
# ==============================================================================
# AI/ML & VECTOR ENGINE CONFIGURATION
# ==============================================================================
# Model selection alters the required vector collection dimensions in Qdrant.
# Defaulting to 768d for higher retrieval performance over plan baseline.
EMBEDDING_MODEL_NAME=sentence-transformers/all-mpnet-base-v2
VECTOR_DIMENSION=768

EMBEDDING_DEVICE=cpu
EMBEDDING_BATCH_SIZE=32
EMBEDDING_MAX_SEQ_LENGTH=512
```

Updated legacy keys:
- `QDRANT_VECTOR_SIZE=768` (was 384)
- `EMBEDDING_MODEL_NAME=sentence-transformers/all-mpnet-base-v2` (was all-MiniLM-L6-v2)
- `EMBEDDING_MAX_SEQ_LENGTH=512` (was 256)
- `APP_VERSION=0.4.0`
- Added `EMBEDDING_NORMALIZE`, `VECTOR_SCORE_THRESHOLD`, etc., matching `app/core/config.py`

### `iob-integration/.env.example` (NEW)
Trimmed gateway template for Member 1:
- `EMBEDDING_MODEL_NAME=all-mpnet-base-v2`
- `VECTOR_DIMENSION=768`
- Qdrant, Telemetry, Auth stubs aligned with main `.env.example`

---

## 3. Local Smoke Test

### `test_vector_init.py`
Standalone Qdrant collection smoke test:
```bash
docker run -d -p 6333:6333 -p 6334:6334 qdrant/qdrant
python test_vector_init.py
```
Expected:
```
Phase 1 Config — Model: sentence-transformers/all-mpnet-base-v2 | Dim: 768
✅ Success! Created collection 'telemetry_knowledge_test' with vector size: 768
✅ Phase 1 Embedding Lock VERIFIED — 768d mpnet
```

The script:
1. Imports `config.py` → triggers dimension validation
2. Tries `app.core.config.get_settings()` → triggers Pydantic validator
3. Creates `telemetry_knowledge_test` collection with `VectorParams(size=dim, distance=Distance.COSINE)`
4. Asserts `info.config.params.vectors.size == 768`
5. Cleans up

---

## 4. Integration Wiring

| Component | Status | Notes |
|---|---|---|
| `app/vector/embedding_engine.py` | ✅ No change needed | Already auto-upgrades MiniLM → mpnet, reads Settings |
| `app/vector/qdrant_manager.py` | ✅ No change needed | Auto-aligns vector_size to engine.vector_dim, raises on collection mismatch |
| `app/vector/schema.py` | ✅ No change needed | DEFAULT_VECTOR_DIM = 768 |
| `app/graphrag/*` | ✅ Compatible | Uses vector search with Settings-driven top_k |
| `app/ingestion/*` | ✅ Compatible | EmbeddingEngine singleton respects new model |
| Telemetry pipeline (Member 2) | ⚠️ ACK required | Confirm ingestion metrics are NOT using 384d |
| Platform Gateway (Member 1) | ⚠️ Pull required | Copy `iob-integration/.env.example` |

---

## 5. Team Handoff Checklist

- [ ] **Publish Proposal:** Post Phase 1 lock message to team channel
- [ ] **Verify Member 1 Pull:** `@Member 1` confirms `iob-integration/.env.example` copied, gateway service token rotated
- [ ] **Verify Member 2 Ack:** `@Member 2` confirms telemetry PLC/SCADA pipeline will emit 768d vectors only, no 384d ingestion metrics
- [ ] Qdrant collections recreated: `sop_documents`, `technical_manuals`, `incident_reports`, `operational_knowledge_v4` — all at 768d COSINE
- [ ] CI gate: `python -c "from app.vector.embedding_validator import assert_embedding_config; assert_embedding_config('sentence-transformers/all-mpnet-base-v2', 768)"`

**Do not proceed to feature code until this hard gate is cleared.**

---

## Files Delivered

```
phase1_embedding_lock/
├── config.py                           # Protocol-compliant root config, os.getenv + Settings sync
├── test_vector_init.py                 # Qdrant 768d smoke test
├── .env.example                        # Full AI platform env, mpnet/768d
├── iob-integration/
│   └── .env.example                    # Member 1 gateway template
├── app/
│   ├── __init__.py
│   └── core/
│       ├── __init__.py
│       └── config.py                   # Pydantic Settings w/ model_validator dimension lock
│   └── vector/
│       ├── __init__.py
│       └── embedding_validator.py      # Shared validator for CI / Member 1/2
├── PHASE1_EMBEDDING_LOCK_REPORT.md
└── README_PHASE1_INTEGRATION.md
```

All files are drop-in compatible with `https://github.com/lathika-mohan/brain_intelligence-main` @ `f6d04a0` (Phase-12).

---
**Signed:** AI Intelligence Platform — Embedding Layer Lead  
**Lock:** all-mpnet-base-v2 / 768d / Cosine
