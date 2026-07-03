"""
Phase 3 — LLM Extraction Schemas (Pydantic v2, strict structured output)

Enforces Phase 1 ontology boundary constraints for Industry 5.0 knowledge extraction.
"""

from __future__ import annotations

from enum import Enum
from typing import Literal, Optional
from pydantic import BaseModel, Field, ConfigDict, field_validator

# Import canonical enums to stay aligned with Phase 1
try:
    from app.models.ontology import (
        GraphNodeLabel,
        GraphRelationshipType,
        AssetType,
        EquipmentClass,
        ComponentType,
        SensorCategory,
        FailureSeverityTier,
        FailureMechanism,
        RootCauseCategory,
        SOPStepType,
        HazardCategory,
        RiskLevel,
        CriticalityTier,
    )
except Exception:  # allow schema import in isolated test contexts
    GraphNodeLabel = str  # type: ignore
    GraphRelationshipType = str  # type: ignore


class ExtractionEntityType(str, Enum):
    """Strict entity boundary — Phase 1 GraphNodeLabel subset for extraction."""
    ASSET = "Asset"
    COMPONENT = "Component"
    SENSOR = "Sensor"
    FAILURE_MODE = "FailureMode"
    ROOT_CAUSE = "RootCause"
    SOP = "SOP"
    SOP_STEP = "SOPStep"
    TOOLING = "Tooling"
    SAFETY_HAZARD = "SafetyHazard"
    LOCATION = "Location"
    MAINTENANCE_TASK = "MaintenanceTask"
    FAILURE_SYMPTOM = "FailureSymptom"
    OPERATOR_ROLE = "OperatorRole"
    TELEMETRY_STREAM = "TelemetryStream"


class ExtractionRelationshipType(str, Enum):
    """Phase 1 canonical UPPERCASE_SNAKE_CASE relationships."""
    COMPRISED_OF = "COMPRISED_OF"
    MONITORED_BY = "MONITORED_BY"
    EXHIBITS_ANOMALY = "EXHIBITS_ANOMALY"
    TRIGGERED_BY = "TRIGGERED_BY"
    MITIGATED_BY = "MITIGATED_BY"
    REQUIRES_TOOL = "REQUIRES_TOOL"
    HAS_STEP = "HAS_STEP"
    LOCATED_IN = "LOCATED_IN"
    HAS_SYMPTOM = "HAS_SYMPTOM"
    HAS_HAZARD = "HAS_HAZARD"
    REQUIRES_ROLE = "REQUIRES_ROLE"
    EMITS_STREAM = "EMITS_STREAM"
    SUBASSEMBLY_OF = "SUBASSEMBLY_OF"
    DEPENDS_ON = "DEPENDS_ON"
    APPLIES_TO_ASSET = "APPLIES_TO_ASSET"
    APPLIES_TO_COMPONENT = "APPLIES_TO_COMPONENT"
    EXECUTES_SOP = "EXECUTES_SOP"
    # Phase 3 auditability edge
    MENTIONS = "MENTIONS"
    GROUNDS_ENTITY = "GROUNDS_ENTITY"


# Allowed source -> relationship -> target map (Phase 1 RELATIONSHIP_CATALOG subset)
# Used for runtime validation
ALLOWED_TRIPLES: dict[tuple[str, str, str], bool] = {
    ("Asset", "COMPRISED_OF", "Component"): True,
    ("Component", "MONITORED_BY", "Sensor"): True,
    ("Sensor", "EXHIBITS_ANOMALY", "FailureMode"): True,
    ("FailureMode", "TRIGGERED_BY", "RootCause"): True,
    ("FailureMode", "MITIGATED_BY", "SOP"): True,
    ("SOP", "REQUIRES_TOOL", "Tooling"): True,
    ("SOP", "HAS_STEP", "SOPStep"): True,
    ("Asset", "LOCATED_IN", "Location"): True,
    ("FailureMode", "HAS_SYMPTOM", "FailureSymptom"): True,
    ("SOPStep", "HAS_HAZARD", "SafetyHazard"): True,
    ("SOPStep", "REQUIRES_ROLE", "OperatorRole"): True,
    ("Sensor", "EMITS_STREAM", "TelemetryStream"): True,
    ("Component", "SUBASSEMBLY_OF", "Component"): True,
    ("Asset", "DEPENDS_ON", "Asset"): True,
    ("MaintenanceTask", "EXECUTES_SOP", "SOP"): True,
    ("MaintenanceTask", "APPLIES_TO_ASSET", "Asset"): True,
    ("MaintenanceTask", "APPLIES_TO_COMPONENT", "Component"): True,
    # Phase 3 grounding
    ("TextChunk", "MENTIONS", "Asset"): True,
    ("TextChunk", "MENTIONS", "Component"): True,
    ("TextChunk", "MENTIONS", "Sensor"): True,
    ("TextChunk", "MENTIONS", "FailureMode"): True,
    ("TextChunk", "MENTIONS", "RootCause"): True,
    ("TextChunk", "MENTIONS", "SOP"): True,
    ("TextChunk", "MENTIONS", "SOPStep"): True,
    ("TextChunk", "MENTIONS", "Tooling"): True,
    ("TextChunk", "GROUNDS_ENTITY", "SOP"): True,
    ("TextChunk", "GROUNDS_ENTITY", "SOPStep"): True,
    ("TextChunk", "GROUNDS_ENTITY", "FailureMode"): True,
    ("TextChunk", "GROUNDS_ENTITY", "SafetyHazard"): True,
}


class ExtractedEntity(BaseModel):
    """Single ontology-grounded entity extracted from a text chunk."""
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    entity_id: str = Field(..., description="Canonical Phase 1 ID, e.g. asset:SRP:P-101A")
    label: ExtractionEntityType = Field(..., description="Phase 1 GraphNodeLabel")
    display_name: str = Field(..., min_length=1, max_length=256)
    confidence: float = Field(..., ge=0.0, le=1.0)
    # optional ontology-typed attributes (partial, flattened for graph loader)
    asset_type: Optional[str] = None
    equipment_class: Optional[str] = None
    component_type: Optional[str] = None
    sensor_category: Optional[str] = None
    metric: Optional[str] = None
    unit: Optional[str] = None
    severity_tier: Optional[str] = None
    # free-form properties captured by LLM, will be JSON-serialized if nested
    properties: dict = Field(default_factory=dict)
    # alias surface forms observed in text
    aliases: list[str] = Field(default_factory=list)
    # provenance
    chunk_id: Optional[str] = None
    source_span: Optional[str] = Field(None, description="Exact text span supporting extraction")

    @field_validator("entity_id")
    @classmethod
    def validate_entity_id(cls, v: str) -> str:
        if ":" not in v:
            raise ValueError("entity_id must follow Phase 1 strategy <label>:<...>")
        if len(v) < 5:
            raise ValueError("entity_id too short")
        return v.strip()


class ExtractedRelationship(BaseModel):
    """Ontology-constrained triple: (Source) -> [RELATIONSHIP] -> (Target)"""
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    source_id: str
    source_label: ExtractionEntityType
    relationship: ExtractionRelationshipType
    target_id: str
    target_label: ExtractionEntityType
    confidence: float = Field(..., ge=0.0, le=1.0)
    properties: dict = Field(default_factory=dict)
    chunk_id: Optional[str] = None
    evidence_text: Optional[str] = None

    @field_validator("relationship")
    @classmethod
    def validate_uppercase_snake(cls, v: ExtractionRelationshipType) -> ExtractionRelationshipType:
        s = v.value if isinstance(v, Enum) else str(v)
        if s != s.upper():
            raise ValueError("relationship must be UPPERCASE_SNAKE_CASE")
        if not s.replace("_", "").isalpha():
            # allow alphanumeric for safety, but prefer alpha
            pass
        return v


class ExtractionResult(BaseModel):
    """Structured LLM output for a single text chunk."""
    model_config = ConfigDict(extra="forbid")

    chunk_id: str
    document_id: str
    entities: list[ExtractedEntity] = Field(default_factory=list)
    relationships: list[ExtractedRelationship] = Field(default_factory=list)
    extraction_model: str = Field(default="phase3-industrial-ie-v1")
    extraction_timestamp: Optional[str] = None
    warnings: list[str] = Field(default_factory=list)

    def validate_ontology_constraints(self) -> list[str]:
        """Return list of validation errors (empty = valid)."""
        errors: list[str] = []
        entity_ids = {e.entity_id: e.label.value for e in self.entities}
        # Check all relationship endpoints exist in entity list
        for r in self.relationships:
            if r.source_id not in entity_ids:
                errors.append(f"Relationship source {r.source_id} not in extracted entities")
            if r.target_id not in entity_ids:
                errors.append(f"Relationship target {r.target_id} not in extracted entities")
            # Check triple is allowed
            key = (r.source_label.value, r.relationship.value, r.target_label.value)
            if key not in ALLOWED_TRIPLES:
                # Allow MENTIONS/GROUNDS_ENTITY broadly if source is TextChunk (handled upstream)
                errors.append(f"Triple not in RELATIONSHIP_CATALOG: {key}")
            # Required edge properties per Phase 1
            if r.relationship.value == "EXHIBITS_ANOMALY":
                if "metric" not in r.properties or "confidence_weight" not in r.properties:
                    errors.append(f"EXHIBITS_ANOMALY missing required props: {r.source_id}->{r.target_id}")
            if r.relationship.value == "HAS_STEP":
                if "sequence_number" not in r.properties:
                    errors.append(f"HAS_STEP missing sequence_number: {r.source_id}->{r.target_id}")
        return errors


class ChunkMetadata(BaseModel):
    """Context Preservation Hierarchy — deterministic chunk envelope."""
    model_config = ConfigDict(extra="forbid")

    chunk_id: str = Field(..., description="Deterministic SHA-256 hash ID")
    document_id: str
    source_filename: str
    document_category: Literal["MANUAL", "SOP", "SPEC_SHEET", "MAINTENANCE_LOG", "INCIDENT_REPORT"]
    section_title: Optional[str] = None
    section_identifier: Optional[str] = None
    page_start: Optional[int] = None
    page_end: Optional[int] = None
    chunk_index: int = Field(..., ge=0)
    token_count: Optional[int] = None
    char_count: int
    hash: str
    parent_metadata: dict = Field(default_factory=dict)


class ParsedDocument(BaseModel):
    """Output of pdf_parser — clean text + structural metadata."""
    model_config = ConfigDict(arbitrary_types_allowed=True)

    document_id: str
    source_filename: str
    document_category: str
    total_pages: int
    text: str
    sections: list[dict] = Field(default_factory=list)
    tables: list[dict] = Field(default_factory=list)  # JSON-serialized tables
    metadata: dict = Field(default_factory=dict)


class GraphLoadBatch(BaseModel):
    """Batch payload handed to graph_loader."""
    model_config = ConfigDict(extra="forbid")
    chunks: list[ChunkMetadata] = Field(default_factory=list)
    entities: list[ExtractedEntity] = Field(default_factory=list)
    relationships: list[ExtractedRelationship] = Field(default_factory=list)
