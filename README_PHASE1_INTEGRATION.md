# Phase 1 Embedding Lock — Integration Guide

Quick drop-in for `brain_intelligence-main`

## What changed?

| File | Change |
|---|---|
| `config.py` | NEW — root-level os.getenv config with dimension validation. Syncs with `app.core.config` if present. |
| `app/core/config.py` | ADDED `@model_validator` — raises `ValueError` if `embedding_model_name` ↔ `qdrant_vector_size` mismatch. Defaults locked to mpnet / 768d. |
| `.env.example` | UPDATED — `EMBEDDING_MODEL_NAME=sentence-transformers/all-mpnet-base-v2`, `QDRANT_VECTOR_SIZE=768`, `EMBEDDING_MAX_SEQ_LENGTH=512`, added AI/ML Vector Engine Configuration block |
| `iob-integration/.env.example` | NEW — Member 1 gateway template, 768d locked |
| `test_vector_init.py` | NEW — Qdrant smoke test |
| `app/vector/embedding_validator.py` | NEW — shared validator for CI |

No breaking changes to:
- `app/vector/embedding_engine.py`
- `app/vector/qdrant_manager.py`
- `app/vector/schema.py`
- GraphRAG / Predictive / XAI pipelines

## Install

1. Copy files over your repo root:
```
cp -r phase1_embedding_lock/* /path/to/brain_intelligence-main/
```

2. Copy env:
```
cp .env.example .env
# fill in secrets
```

3. Smoke test:
```bash
docker run -d -p 6333:6333 qdrant/qdrant
pip install -r requirements.txt
python test_vector_init.py
# ✅ Success! Created collection with vector size: 768
```

4. Validate settings:
```bash
python -c "from app.core.config import get_settings; s=get_settings(); print(s.embedding_model_name, s.qdrant_vector_size)"
# sentence-transformers/all-mpnet-base-v2 768
```

5. Run test suite:
```bash
pytest -q
```

## Environment variables

Minimum required for Phase 1 lock:

```
EMBEDDING_MODEL_NAME=sentence-transformers/all-mpnet-base-v2
VECTOR_DIMENSION=768
QDRANT_VECTOR_SIZE=768
QDRANT_URL=http://localhost:6333
```

Both `VECTOR_DIMENSION` and `QDRANT_VECTOR_SIZE` must be 768 when using mpnet.

## Team coordination

- **Member 1 (Platform Gateway):** pull `iob-integration/.env.example`
- **Member 2 (Telemetry / PLC):** ACK that ingestion pipeline is NOT using 384d vectors — switch to 768d
- Recreate all Qdrant collections after the lock — old 384d collections will raise `ValueError` on startup (intentional)

## Rollback / Alt models

Supported models (validated):

| Model | Dim |
|---|---|
| `sentence-transformers/all-MiniLM-L6-v2` | 384 |
| `sentence-transformers/all-mpnet-base-v2` | 768 |
| `BAAI/bge-base-en-v1.5` | 768 |
| `BAAI/bge-large-en-v1.5` | 1024 |

Change BOTH `EMBEDDING_MODEL_NAME` and `QDRANT_VECTOR_SIZE` / `VECTOR_DIMENSION` together, then recreate Qdrant collections.

The validator will catch mismatches at import time.

---

For the full manifest see `PHASE1_EMBEDDING_LOCK_REPORT.md`
