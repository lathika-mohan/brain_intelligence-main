# config.py
# Phase 1 — Embedding Mismatch Lock / Vector Layer Configuration
#
# This is the lightweight, framework-agnostic config used by
# iob-integration scripts and standalone smoke tests.
#
# For the full FastAPI / Pydantic settings, see: app/core/config.py
#
import os

# Embedding Configuration
# Defaulting to 768d for higher retrieval performance over plan baseline.
EMBEDDING_MODEL_NAME = os.getenv("EMBEDDING_MODEL_NAME", "all-mpnet-base-v2")
VECTOR_DIMENSION = int(os.getenv("VECTOR_DIMENSION", "768"))

# Allow override via the main app Settings (pydantic) if available,
# so root config.py stays in sync with app/core/config.py
try:
    from app.core.config import get_settings  # type: ignore
    _settings = get_settings()
    EMBEDDING_MODEL_NAME = _settings.embedding_model_name
    VECTOR_DIMENSION = _settings.qdrant_vector_size
except Exception:
    # Running standalone – env vars / defaults above apply
    pass

# Validation Check to prevent silent Qdrant initialization failures
if "mpnet" in EMBEDDING_MODEL_NAME and VECTOR_DIMENSION != 768:
    raise ValueError(f"Dimension mismatch! {EMBEDDING_MODEL_NAME} requires 768 dimensions, got {VECTOR_DIMENSION}.")
elif "MiniLM" in EMBEDDING_MODEL_NAME or "minilm" in EMBEDDING_MODEL_NAME.lower():
    if VECTOR_DIMENSION != 384:
        raise ValueError(f"Dimension mismatch! {EMBEDDING_MODEL_NAME} requires 384 dimensions, got {VECTOR_DIMENSION}.")
elif "bge-large" in EMBEDDING_MODEL_NAME.lower() and VECTOR_DIMENSION != 1024:
    raise ValueError(f"Dimension mismatch! {EMBEDDING_MODEL_NAME} requires 1024 dimensions, got {VECTOR_DIMENSION}.")
elif "bge-base" in EMBEDDING_MODEL_NAME.lower() and VECTOR_DIMENSION != 768:
    raise ValueError(f"Dimension mismatch! {EMBEDDING_MODEL_NAME} requires 768 dimensions, got {VECTOR_DIMENSION}.")

# Qdrant wiring helpers (for standalone scripts)
QDRANT_URL = os.getenv("QDRANT_URL", "http://localhost:6333")
QDRANT_COLLECTION = os.getenv("QDRANT_COLLECTION", "operational_knowledge_v4")

__all__ = [
    "EMBEDDING_MODEL_NAME",
    "VECTOR_DIMENSION",
    "QDRANT_URL",
    "QDRANT_COLLECTION",
]
