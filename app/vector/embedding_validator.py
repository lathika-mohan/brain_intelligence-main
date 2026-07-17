"""
Phase 1 — Embedding Dimension Validator
Shared by Member 1 (Platform Gateway), Member 2 (Telemetry Ingest), 
and the AI Intelligence Platform.

Prevents silent Qdrant 384d vs 768d mismatches.
"""
from typing import Tuple

MODEL_DIMENSIONS = {
    "all-minilm-l6-v2": 384,
    "all-MiniLM-L6-v2": 384,
    "sentence-transformers/all-MiniLM-L6-v2": 384,
    "all-mpnet-base-v2": 768,
    "sentence-transformers/all-mpnet-base-v2": 768,
    "bge-large-en-v1.5": 1024,
    "BAAI/bge-large-en-v1.5": 1024,
    "bge-base-en-v1.5": 768,
    "bge-small-en-v1.5": 384,
}

def resolve_embedding_dim(model_name: str) -> int | None:
    """Resolve expected vector dimensions from model id."""
    name = model_name.lower()
    if "mpnet" in name:
        return 768
    if "minilm" in name or "mini-lm" in name:
        return 384
    if "bge-large" in name:
        return 1024
    if "bge-base" in name:
        return 768
    if "bge-small" in name:
        return 384
    # Check exact map
    return MODEL_DIMENSIONS.get(model_name)

def validate_embedding_config(model_name: str, vector_dimension: int) -> Tuple[bool, str]:
    """Validate embedding_model ↔ vector_dimension pair. Returns (ok, message)."""
    expected = resolve_embedding_dim(model_name)
    if expected is None:
        return True, f"Unknown model {model_name}, skipping strict check (got {vector_dimension}d)"
    if expected != vector_dimension:
        return False, f"Dimension mismatch! {model_name} requires {expected} dimensions, got {vector_dimension}."
    return True, f"OK — {model_name} / {vector_dimension}d"

def assert_embedding_config(model_name: str, vector_dimension: int):
    ok, msg = validate_embedding_config(model_name, vector_dimension)
    if not ok:
        raise ValueError(msg)
    return True

# Auto-validate on import if env is set
if __name__ != "__main__":
    import os
    model = os.getenv("EMBEDDING_MODEL_NAME", "all-mpnet-base-v2")
    dim_str = os.getenv("VECTOR_DIMENSION", os.getenv("QDRANT_VECTOR_SIZE", "768"))
    try:
        assert_embedding_config(model, int(dim_str))
    except Exception:
        pass  # Let app.core.config raise with full context
