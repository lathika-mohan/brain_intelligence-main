"""
Centralized application configuration (Pydantic v2 / pydantic-settings).

Every subsystem (GraphRAG, Predictive Maintenance, XAI, Decision Engine)
reads its tunables from a single `Settings` instance obtained via
`get_settings()`. Values are sourced from environment variables / a local
`.env` file, following the contract frozen in `.env.example`.

Phase 1 Embedding Lock: all-mpnet-base-v2 / 768d enforced
No business logic lives here — configuration only.
"""
from functools import lru_cache
from typing import List, Literal

from pydantic import field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # --- Runtime ---
    app_env: Literal["development", "staging", "production"] = "development"
    app_name: str = "IOB AI Intelligence Platform"
    app_version: str = "0.4.0"  # Phase 4 — Embedding & Semantic Search
    api_v1_prefix: str = "/api/v1"
    log_level: str = "INFO"
    debug: bool = True

    # --- CORS ---
    cors_allow_origins: str = "http://localhost:3000"

    # --- Server ---
    host: str = "0.0.0.0"
    port: int = 8000

    # --- Neo4j ---
    neo4j_uri: str = "bolt://localhost:7687"
    neo4j_user: str = "neo4j"
    neo4j_password: str = "changeme_neo4j_password"
    neo4j_database: str = "neo4j"
    neo4j_max_connection_lifetime: int = 3600
    neo4j_max_connection_pool_size: int = 50
    neo4j_connection_timeout: int = 30

    # --- Qdrant ---
    qdrant_url: str = "http://localhost:6333"
    qdrant_api_key: str | None = None
    qdrant_grpc_port: int = 6334
    qdrant_prefer_grpc: bool = False
    qdrant_collection_sop_docs: str = "sop_documents"
    qdrant_collection_manuals: str = "technical_manuals"
    qdrant_collection_incidents: str = "incident_reports"
    qdrant_collection_operational: str = "operational_knowledge_v4"  # Phase 4 primary
    qdrant_vector_size: int = 768  # Phase 1 Lock: all-mpnet-base-v2
    qdrant_distance_metric: Literal["Cosine", "Euclid", "Dot"] = "Cosine"

    # --- Embeddings -- Phase 1 / Phase 4 ---
    # Production default: sentence-transformers/all-mpnet-base-v2 (768d)
    # Alternative high-performance: BAAI/bge-large-en-v1.5 (1024d)
    # Legacy fallback: sentence-transformers/all-MiniLM-L6-v2 (384d)
    embedding_model_name: str = "sentence-transformers/all-mpnet-base-v2"
    embedding_device: Literal["cpu", "cuda", "mps"] = "cpu"
    embedding_batch_size: int = 32
    embedding_max_seq_length: int = 512  # Phase 4: increased for technical docs
    embedding_normalize: bool = True
    embedding_trust_remote_code: bool = False

    # --- Vector Search -- Phase 4 ---
    vector_score_threshold: float = 0.70
    vector_default_top_k: int = 8
    vector_max_top_k: int = 50
    vector_search_ef: int = 128
    vector_search_exact: bool = False

    # --- GraphRAG -- Phase 5 hybrid engine ---
    graphrag_top_k_vector: int = 8
    graphrag_max_graph_hops: int = 3
    graphrag_min_confidence_threshold: float = 0.70
    graphrag_max_context_chunks: int = 12
    graphrag_score_threshold: float = 0.55  # Phase 5: lowered for broader retrieval
    graphrag_rerank_enabled: bool = True
    graphrag_rrf_k: int = 60  # RRF smoothing constant

    # --- LLM (Phase 5 synthesis) ---
    llm_provider: str = "mock"  # "openai" | "anthropic" | "mock"
    llm_model_name: str = "mock-llm-v1"
    llm_max_tokens: int = 1024
    llm_temperature: float = 0.1
    llm_api_key: str = ""  # set via OPENAI_API_KEY or ANTHROPIC_API_KEY env vars
    llm_base_url: str = ""  # optional custom endpoint

    # --- Predictive Maintenance ---
    pdm_model_registry_path: str = "./artifacts/models"
    pdm_rul_model_name: str = "xgboost_rul_v1"
    pdm_failure_model_name: str = "xgboost_failure_classifier_v1"
    pdm_anomaly_model_name: str = "isolation_forest_v1"
    pdm_anomaly_contamination: float = 0.02
    pdm_inference_fallback_mode: Literal["heuristic", "last_known_good", "reject"] = "heuristic"

    # --- XAI ---
    xai_shap_background_samples: int = 100
    xai_lime_num_features: int = 10
    xai_lime_num_samples: int = 500
    xai_min_confidence_threshold: float = 0.5

    # --- Decision Engine -- Phase 8 ---
    decision_engine_max_recommendations: int = 5
    decision_engine_risk_horizon_days: int = 30
    # Severity classification thresholds (RUL days) -> IMMINENT / SCHEDULED / MONITOR
    decision_engine_imminent_rul_days: float = 3.0
    decision_engine_scheduled_rul_days: float = 14.0
    # Failure-probability floor that force-escalates a tier regardless of RUL
    decision_engine_imminent_probability: float = 0.75
    decision_engine_scheduled_probability: float = 0.40
    # Default asset criticality weight applied when the graph lookup misses
    # (e.g. Neo4j unreachable, or asset not yet catalogued).
    decision_engine_default_criticality_weight: float = 1.0
    # Cost-of-inaction model defaults (USD), used when asset-level overrides
    # are not present on the graph node.
    decision_engine_default_downtime_cost_per_hour_usd: float = 2500.0
    decision_engine_default_repair_hours: float = 6.0
    decision_engine_planned_maintenance_discount: float = 0.35
    # Risk Priority Number ceiling used to normalise RPN -> [0, 1]
    decision_engine_rpn_ceiling: float = 1000.0

    # --- Telemetry ingestion (upstream contract with Member 2) ---
    telemetry_ingest_queue_url: str = "kafka://localhost:9092/telemetry.raw"
    telemetry_schema_version: str = "1.0.0"
    telemetry_max_batch_size: int = 500

    # --- Downstream gateway (Member 1) ---
    platform_gateway_base_url: str = "http://localhost:8080"
    platform_gateway_service_token: str = "changeme_service_token"

    # --- Auth ---
    jwt_secret_key: str = "changeme_super_secret_key"
    jwt_algorithm: str = "HS256"
    jwt_access_token_expire_minutes: int = 60
    service_api_key: str = "changeme_internal_service_key"

    @field_validator("cors_allow_origins")
    @classmethod
    def _validate_origins(cls, v: str) -> str:
        return v

    @property
    def cors_origins_list(self) -> List[str]:
        return [origin.strip() for origin in self.cors_allow_origins.split(",") if origin.strip()]

    # ------------------------------------------------------------------
    # Phase 1 Embedding Mismatch Lock
    # ------------------------------------------------------------------
    @model_validator(mode="after")
    def _validate_embedding_dimensions(self) -> "Settings":
        """
        Phase 1 Hard Gate: Prevent silent Qdrant initialization failures.
        Ensures embedding_model_name ↔ qdrant_vector_size alignment.
        """
        model = self.embedding_model_name.lower()
        dim = self.qdrant_vector_size

        # Canonical dimension map
        expected_dim = None
        if "mpnet" in model:
            expected_dim = 768
        elif "minilm" in model or "mini-lm" in model:
            expected_dim = 384
        elif "bge-large" in model:
            expected_dim = 1024
        elif "bge-base" in model:
            expected_dim = 768
        elif "bge-small" in model:
            expected_dim = 384

        if expected_dim is not None and dim != expected_dim:
            raise ValueError(
                f"Dimension mismatch! {self.embedding_model_name} requires "
                f"{expected_dim} dimensions, got {dim}. "
                f"Update QDRANT_VECTOR_SIZE / qdrant_vector_size to match."
            )

        # Extra safety: vector size must be one of the known good sizes
        if dim not in (384, 768, 1024):
            raise ValueError(
                f"QDRANT_VECTOR_SIZE={dim} is not a supported embedding dimension. "
                f"Supported: 384 (MiniLM), 768 (mpnet/bge-base), 1024 (bge-large)"
            )

        return self


@lru_cache
def get_settings() -> Settings:
    """Return a cached singleton Settings instance."""
    return Settings()


# ------------------------------------------------------------------------------
# Phase 1 Simple os.getenv compatibility shim
# Allows legacy scripts / iob-integration to import:
#   from config import EMBEDDING_MODEL_NAME, VECTOR_DIMENSION
# without pulling in full Pydantic stack.
# ------------------------------------------------------------------------------
try:
    _s = get_settings()
    EMBEDDING_MODEL_NAME = _s.embedding_model_name
    VECTOR_DIMENSION = _s.qdrant_vector_size
except Exception:
    # Fallback to pure env if Pydantic fails (e.g. during bootstrap)
    import os
    EMBEDDING_MODEL_NAME = os.getenv("EMBEDDING_MODEL_NAME", "all-mpnet-base-v2")
    VECTOR_DIMENSION = int(os.getenv("VECTOR_DIMENSION", "768"))

# Validation Check to prevent silent Qdrant initialization failures
if "mpnet" in EMBEDDING_MODEL_NAME and VECTOR_DIMENSION != 768:
    raise ValueError(f"Dimension mismatch! {EMBEDDING_MODEL_NAME} requires 768 dimensions, got {VECTOR_DIMENSION}.")
elif "MiniLM" in EMBEDDING_MODEL_NAME or "minilm" in EMBEDDING_MODEL_NAME.lower():
    if VECTOR_DIMENSION != 384:
        raise ValueError(f"Dimension mismatch! {EMBEDDING_MODEL_NAME} requires 384 dimensions, got {VECTOR_DIMENSION}.")
