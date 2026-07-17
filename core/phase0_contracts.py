"""
Phase 0 Frozen Contracts — Pydantic Models
This file is the single source of truth shared with Member 2 Gateway for validation.
No business logic — only frozen schemas matching CONTRACT_FREEZE_PAYLOADS.json

Usage:
 - Gateway can import these to validate relay payloads
 - AI service uses these in routers (already exists in app/models/*, this file freezes them)

Embedding Lock: 768d all-mpnet-base-v2 enforced here as constant.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Literal, Optional
from pydantic import BaseModel, Field

# ------------------------------------------------------------------
# Constants — Phase 0 Locked
# ------------------------------------------------------------------
EMBEDDING_MODEL_NAME = "sentence-transformers/all-mpnet-base-v2"
VECTOR_DIMENSION = 768
QDRANT_COLLECTION = "operational_knowledge_v4"
QDRANT_DISTANCE = "Cosine"
API_V1_PREFIX = "/api/v1"
PHASE = "0-frozen"

# ------------------------------------------------------------------
# Predictive
# ------------------------------------------------------------------
class PredictiveFeatures(BaseModel):
    vibration: Optional[float] = Field(default=None, example=4.2)
    temperature: Optional[float] = Field(default=None, example=92.5)
    bearing_temperature: Optional[float] = Field(default=None)
    bearing_temp: Optional[float] = Field(default=None)
    pressure: Optional[float] = Field(default=None, example=3.1)
    rpm: Optional[float] = Field(default=None, example=1750)
    vibration_rms: Optional[float] = Field(default=None)

    class Config:
        extra = "allow"  # allow flexible sensor features

class PredictiveInferRequest(BaseModel):
    asset_id: str = Field(..., example="machine07")
    component_id: Optional[str] = Field(default="bearing", example="bearing")
    features: Dict[str, float] = Field(default_factory=dict, example={"vibration": 4.2, "temperature": 92.5})
    horizon_hours: int = Field(default=24, example=24)

class RULResponse(BaseModel):
    value_days: float = Field(example=2.3)
    lower_bound_days: float
    upper_bound_days: float
    confidence_level: float = 0.9
    model_name: str = "xgboost_rul_v1"
    model_version: str = "1.0.0"

class PredictiveInferResponseData(BaseModel):
    asset_id: str
    component_id: str
    risk_score: float = Field(example=0.87, ge=0, le=1)
    failure_probability: float
    rul: RULResponse
    anomaly_detected: Optional[bool] = None
    model_used: str = "xgboost_failure_classifier_v1"
    fallback_used: bool = False

# ------------------------------------------------------------------
# GraphRAG
# ------------------------------------------------------------------
class GraphRagQueryRequest(BaseModel):
    query_text: str = Field(..., example="Why is pump07 bearing temperature rising above 85C?")
    asset_id: Optional[str] = Field(default=None, example="pump07")
    top_k: int = Field(default=8, ge=1, le=50)
    min_score: float = Field(default=0.55, ge=0, le=1)
    max_graph_hops: int = Field(default=2, ge=1, le=5)
    include_telemetry: bool = True
    filters: Optional[Dict[str, Any]] = None

class Citation(BaseModel):
    citation_id: str = Field(example="[Source #1]")
    claim_span: str
    source_document: str = Field(example="SOP-101-Bearing-Maintenance.pdf")
    source_type: str = Field(example="SOP")
    source_node_id: str
    confidence_score: float = Field(ge=0, le=1)
    page_number: Optional[int] = None

class GraphRagContextChunk(BaseModel):
    chunk_id: str
    text: str
    score: float
    document_type: str
    source: str

class GraphRagQueryResponseData(BaseModel):
    answer: str
    citations: List[Citation]
    context_chunks: List[GraphRagContextChunk] = []
    graph_nodes: List[Any] = []
    graph_edges: List[Any] = []
    overall_confidence: float = 0.85
    out_of_domain: bool = False
    generated_at: str

# ------------------------------------------------------------------
# XAI
# ------------------------------------------------------------------
class XAIRequest(BaseModel):
    asset_id: str = Field(example="machine07")
    explanation_type: Literal["local", "global"] = "local"
    methods: List[Literal["shap", "lime"]] = Field(default_factory=lambda: ["shap", "lime"])
    top_features: int = Field(default=5, ge=1, le=20)

class ShapValue(BaseModel):
    feature_name: str
    impact_weight: float = Field(ge=0, le=1)
    feature_value: float
    rank: int

class XAIResponseData(BaseModel):
    asset_id: str
    explanation_type: str
    shap_values: List[ShapValue]
    lime_explanation: Optional[List[Dict[str, Any]]] = None
    root_cause_summary: str
    confidence: float = Field(ge=0, le=1)
    generated_at: Optional[str] = None

# ------------------------------------------------------------------
# Decision
# ------------------------------------------------------------------
class DecisionRecommendRequest(BaseModel):
    asset_id: str = Field(example="machine07")
    risk_score: float = Field(example=0.87, ge=0, le=1)
    rul_days: float = Field(example=2.3)
    failure_probability: float = Field(example=0.85, ge=0, le=1)
    shap_features: Optional[List[Dict[str, Any]]] = None
    context: Optional[Dict[str, Any]] = Field(default_factory=dict)

class RecommendationAction(BaseModel):
    action_id: str
    priority: int
    action_type: str = Field(example="INSPECTION")
    title: str
    description: str
    risk_reduction: Optional[float] = None
    estimated_downtime_hours: Optional[float] = None
    sop_reference: Optional[str] = None
    sop_steps: Optional[List[str]] = None
    fmea_link: Optional[str] = None

class DecisionRecommendResponseData(BaseModel):
    asset_id: str
    severity: Literal["IMMINENT", "SCHEDULED", "MONITOR"] = Field(example="IMMINENT")
    recommendations: List[RecommendationAction]
    decision_log: List[str] = []
    risk_assessment: Optional[Dict[str, Any]] = None

# ------------------------------------------------------------------
# Wrapper Envelope — frozen APIResponse shape used by all endpoints
# ------------------------------------------------------------------
class APIEnvelope(BaseModel):
    success: bool
    data: Any
    error: Optional[str] = None
    request_id: str
    generated_at: str
