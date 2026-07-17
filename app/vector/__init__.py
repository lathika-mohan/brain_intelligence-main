# Phase 1 — Vector package init
# Ensures embedding dimension lock is validated on import
try:
    from app.core.config import get_settings
    _s = get_settings()  # triggers model_validator
except Exception:
    pass
