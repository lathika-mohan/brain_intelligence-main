"""
Centralized application configuration (Pydantic v2 / pydantic-settings).

Every subsystem (GraphRAG, Predictive Maintenance, XAI, Decision Engine)
reads its tunables from a single `Settings` instance obtained via
`get_settings()`. Values are sourced from environment variables / a local
`.env` file, following the contract frozen in `.env.example`.

No business logic lives here — configuration only.
"""
from functools import lru_cache
from typing import List, Literal

from pydantic import field_validator
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
    app_version: str = "0.1.0"
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
    qdrant_vector_size: int = 384
    qdrant_distance_metric: Literal["Cosine", "Euclid", "Dot"] = "Cosine"

    # --- Embeddings ---
    embedding_model_name: str = "sentence-transformers/all-MiniLM-L6-v2"
    embedding_device: Literal["cpu", "cuda"] = "cpu"
    embedding_batch_size: int = 32
    embedding_max_seq_length: int = 256

    # --- GraphRAG ---
    graphrag_top_k_vector: int = 8
    graphrag_max_graph_hops: int = 3
    graphrag_min_confidence_threshold: float = 0.55
    graphrag_max_context_chunks: int = 12

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

    # --- Decision Engine ---
    decision_engine_max_recommendations: int = 5
    decision_engine_risk_horizon_days: int = 30

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


@lru_cache
def get_settings() -> Settings:
    """Return a cached singleton Settings instance."""
    return Settings()
