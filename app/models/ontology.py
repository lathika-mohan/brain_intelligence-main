"""
Phase 1 Industrial Knowledge Ontology interfaces.

These Pydantic V2 models are semantic contracts only. They intentionally
contain no Neo4j driver calls, Cypher generation, parser logic, ML logic,
or UI-facing implementation. Their purpose is to make the Phase 1 domain
model machine-readable so later phases can populate Neo4j/Qdrant without
renegotiating entity names, IDs, attributes, or relationship semantics.
"""
from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from app.models.common import AssetStatus, AssetType
from app.models.telemetry import SensorUnit

ONTOLOGY_VERSION = "1.0.0"


class LocationType(str, Enum):
    SITE = "SITE"
    PLANT = "PLANT"
    AREA = "AREA"
    UNIT = "UNIT"
    LINE = "LINE"
    SKID = "SKID"
    ROOM = "ROOM"
    FUNCTIONAL_LOCATION = "FUNCTIONAL_LOCATION"


class EquipmentClass(str, Enum):
    ROTARY_EQUIPMENT = "ROTARY_EQUIPMENT"
    STATIC_EQUIPMENT = "STATIC_EQUIPMENT"
    ELECTRICAL_EQUIPMENT = "ELECTRICAL_EQUIPMENT"
    INSTRUMENTATION_CONTROL = "INSTRUMENTATION_CONTROL"
    MATERIAL_HANDLING = "MATERIAL_HANDLING"
    UTILITY_EQUIPMENT = "UTILITY_EQUIPMENT"
    SAFETY_SYSTEM = "SAFETY_SYSTEM"
    GENERIC = "GENERIC"


class CriticalityTier(str, Enum):
    SAFETY_CRITICAL = "SAFETY_CRITICAL"
    PRODUCTION_CRITICAL = "PRODUCTION_CRITICAL"
    QUALITY_CRITICAL = "QUALITY_CRITICAL"
    ENVIRONMENTAL_CRITICAL = "ENVIRONMENTAL_CRITICAL"
    NON_CRITICAL = "NON_CRITICAL"


class ComponentType(str, Enum):
    BEARING = "BEARING"
    SEAL = "SEAL"
    IMPELLER = "IMPELLER"
    SHAFT = "SHAFT"
    COUPLING = "COUPLING"
    GEARBOX = "GEARBOX"
    MOTOR_WINDING = "MOTOR_WINDING"
    CASING = "CASING"
    VALVE_BODY = "VALVE_BODY"
    ACTUATOR = "ACTUATOR"
    FILTER = "FILTER"
    LUBRICATION_SYSTEM = "LUBRICATION_SYSTEM"
    COOLING_SYSTEM = "COOLING_SYSTEM"
    CONTROL_MODULE = "CONTROL_MODULE"
    OTHER = "OTHER"


class SensorCategory(str, Enum):
    VIBRATION = "VIBRATION"
    THERMAL = "THERMAL"
    PRESSURE = "PRESSURE"
    FLOW = "FLOW"
    SPEED = "SPEED"
    ELECTRICAL = "ELECTRICAL"
    ACOUSTIC = "ACOUSTIC"
    LEVEL = "LEVEL"
    POSITION = "POSITION"
    QUALITY = "QUALITY"
    OTHER = "OTHER"


class SamplingMethod(str, Enum):
    CONTINUOUS = "CONTINUOUS"
    PERIODIC = "PERIODIC"
    EVENT_DRIVEN = "EVENT_DRIVEN"
    MANUAL = "MANUAL"


class FailureSeverityTier(str, Enum):
    CRITICAL = "CRITICAL"
    DEGRADED = "DEGRADED"
    INCIPIENT = "INCIPIENT"


class FailureMechanism(str, Enum):
    FATIGUE = "FATIGUE"
    WEAR = "WEAR"
    CORROSION = "CORROSION"
    EROSION = "EROSION"
    CAVITATION = "CAVITATION"
    FOULING = "FOULING"
    LEAKAGE = "LEAKAGE"
    OVERHEATING = "OVERHEATING"
    MISALIGNMENT = "MISALIGNMENT"
    IMBALANCE = "IMBALANCE"
    ELECTRICAL_FAULT = "ELECTRICAL_FAULT"
    CONTAMINATION = "CONTAMINATION"
    SOFTWARE_CONTROL_FAULT = "SOFTWARE_CONTROL_FAULT"
    HUMAN_ERROR = "HUMAN_ERROR"
    UNKNOWN = "UNKNOWN"


class RootCauseCategory(str, Enum):
    DESIGN = "DESIGN"
    MANUFACTURING = "MANUFACTURING"
    INSTALLATION = "INSTALLATION"
    OPERATIONAL = "OPERATIONAL"
    MAINTENANCE = "MAINTENANCE"
    ENVIRONMENTAL = "ENVIRONMENTAL"
    MATERIAL = "MATERIAL"
    CONTROL_SYSTEM = "CONTROL_SYSTEM"
    HUMAN_FACTOR = "HUMAN_FACTOR"
    UNKNOWN = "UNKNOWN"


class MaintenanceAction(str, Enum):
    ISOLATE = "ISOLATE"
    LOCKOUT_TAGOUT = "LOCKOUT_TAGOUT"
    INSPECT = "INSPECT"
    LUBRICATE = "LUBRICATE"
    CALIBRATE = "CALIBRATE"
    ALIGN = "ALIGN"
    BALANCE = "BALANCE"
    REPLACE = "REPLACE"
    TIGHTEN = "TIGHTEN"
    CLEAN = "CLEAN"
    TEST = "TEST"
    RESTORE = "RESTORE"
    VERIFY = "VERIFY"
    DOCUMENT = "DOCUMENT"


class SOPStepType(str, Enum):
    PRE_JOB_BRIEF = "PRE_JOB_BRIEF"
    SAFETY_CHECK = "SAFETY_CHECK"
    ISOLATION = "ISOLATION"
    EXECUTION = "EXECUTION"
    INSPECTION = "INSPECTION"
    CALIBRATION = "CALIBRATION"
    VERIFICATION = "VERIFICATION"
    RETURN_TO_SERVICE = "RETURN_TO_SERVICE"
    DOCUMENTATION = "DOCUMENTATION"


class HazardCategory(str, Enum):
    ELECTRICAL = "ELECTRICAL"
    MECHANICAL = "MECHANICAL"
    THERMAL = "THERMAL"
    PRESSURE = "PRESSURE"
    CHEMICAL = "CHEMICAL"
    CONFINED_SPACE = "CONFINED_SPACE"
    WORK_AT_HEIGHT = "WORK_AT_HEIGHT"
    NOISE = "NOISE"
    ERGONOMIC = "ERGONOMIC"
    ENVIRONMENTAL = "ENVIRONMENTAL"


class RiskLevel(str, Enum):
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"


class PermissionScope(str, Enum):
    READ = "READ"
    ACKNOWLEDGE_ALERT = "ACKNOWLEDGE_ALERT"
    EXECUTE_SOP = "EXECUTE_SOP"
    OVERRIDE_RECOMMENDATION = "OVERRIDE_RECOMMENDATION"
    APPROVE_RETURN_TO_SERVICE = "APPROVE_RETURN_TO_SERVICE"
    ADMINISTER_ONTOLOGY = "ADMINISTER_ONTOLOGY"


class SourceType(str, Enum):
    SOP = "SOP"
    MANUAL = "MANUAL"
    INCIDENT_REPORT = "INCIDENT_REPORT"
    MAINTENANCE_LOG = "MAINTENANCE_LOG"
    ENGINEERING_STANDARD = "ENGINEERING_STANDARD"


class GraphNodeLabel(str, Enum):
    LOCATION = "Location"
    ASSET = "Asset"
    COMPONENT = "Component"
    SENSOR = "Sensor"
    TELEMETRY_STREAM = "TelemetryStream"
    FAILURE_MODE = "FailureMode"
    ROOT_CAUSE = "RootCause"
    FAILURE_SYMPTOM = "FailureSymptom"
    MAINTENANCE_TASK = "MaintenanceTask"
    SOP = "SOP"
    SOP_STEP = "SOPStep"
    SAFETY_HAZARD = "SafetyHazard"
    TOOLING = "Tooling"
    OPERATOR_ROLE = "OperatorRole"
    SOURCE_DOCUMENT = "SourceDocument"
    TEXT_CHUNK = "TextChunk"


class GraphRelationshipType(str, Enum):
    LOCATED_IN = "LOCATED_IN"
    CONTAINS = "CONTAINS"
    COMPRISED_OF = "COMPRISED_OF"
    PART_OF = "PART_OF"
    SUBASSEMBLY_OF = "SUBASSEMBLY_OF"
    MONITORED_BY = "MONITORED_BY"
    EMITS_STREAM = "EMITS_STREAM"
    EXHIBITS_ANOMALY = "EXHIBITS_ANOMALY"
    HAS_SYMPTOM = "HAS_SYMPTOM"
    TRIGGERED_BY = "TRIGGERED_BY"
    MITIGATED_BY = "MITIGATED_BY"
    REQUIRES_TOOL = "REQUIRES_TOOL"
    HAS_STEP = "HAS_STEP"
    HAS_HAZARD = "HAS_HAZARD"
    REQUIRES_ROLE = "REQUIRES_ROLE"
    APPLIES_TO_ASSET = "APPLIES_TO_ASSET"
    APPLIES_TO_COMPONENT = "APPLIES_TO_COMPONENT"
    EXECUTES_SOP = "EXECUTES_SOP"
    DOCUMENTED_BY = "DOCUMENTED_BY"
    CONTAINS_CHUNK = "CONTAINS_CHUNK"
    GROUNDS_ENTITY = "GROUNDS_ENTITY"
    DEPENDS_ON = "DEPENDS_ON"


class RelationshipCardinality(str, Enum):
    ONE_TO_ONE = "ONE_TO_ONE"
    ONE_TO_MANY = "ONE_TO_MANY"
    MANY_TO_ONE = "MANY_TO_ONE"
    MANY_TO_MANY = "MANY_TO_MANY"


class BaselineConstraint(BaseModel):
    """Normal operating range for one sensor metric in a given operating context."""

    model_config = ConfigDict(extra="forbid")

    metric: str = Field(..., description="Telemetry metric name; must match Sensor.metric.")
    unit: SensorUnit
    normal_min: float | None = None
    normal_max: float | None = None
    warning_min: float | None = None
    warning_max: float | None = None
    critical_min: float | None = None
    critical_max: float | None = None
    operating_mode: str | None = Field(default=None, description="RUNNING, STARTUP, IDLE, etc.")
    baseline_window_hours: float | None = Field(default=None, gt=0)
    source: str | None = Field(default=None, description="Manual/SOP/OEM reference for this constraint.")


class OperatingEnvelope(BaseModel):
    model_config = ConfigDict(extra="forbid")

    rated_capacity: float | None = None
    rated_capacity_unit: str | None = None
    min_operating_load_pct: float | None = Field(default=None, ge=0.0, le=100.0)
    max_operating_load_pct: float | None = Field(default=None, ge=0.0, le=100.0)
    design_pressure_bar: float | None = None
    design_temperature_c: float | None = None
    speed_rpm: float | None = None
    baseline_constraints: list[BaselineConstraint] = Field(default_factory=list)


class CitationAnchor(BaseModel):
    """Deep semantic hook from a node/field to source text used by GraphRAG citations."""

    model_config = ConfigDict(extra="forbid")

    source_document_id: str
    chunk_id: str
    page_number: int | None = None
    section_heading: str | None = None
    claim_field: str = Field(..., description="Entity attribute grounded by this source span.")
    confidence_score: float = Field(..., ge=0.0, le=1.0)


class SemanticEntity(BaseModel):
    """Common payload inherited by every ontology node class."""

    model_config = ConfigDict(extra="forbid", protected_namespaces=())

    id: str = Field(..., description="Canonical graph ID following the Phase 1 ID strategy.")
    display_name: str
    description: str | None = None
    aliases: list[str] = Field(default_factory=list)
    ontology_version: str = Field(default=ONTOLOGY_VERSION)
    citation_anchors: list[CitationAnchor] = Field(default_factory=list)
    metadata: dict[str, str] = Field(default_factory=dict)


class Location(SemanticEntity):
    location_type: LocationType
    site_code: str
    parent_location_id: str | None = None
    timezone: str | None = Field(default=None, description="IANA timezone, e.g. Asia/Kolkata.")


class Asset(SemanticEntity):
    asset_type: AssetType = Field(..., description="Must align with app.models.common.AssetType.")
    equipment_class: EquipmentClass
    tag: str = Field(..., description="Plant/OEM tag, e.g. P-101A.")
    status: AssetStatus
    criticality: CriticalityTier
    location_id: str
    process_function: str
    asset_subclass: str | None = Field(default=None, description="e.g. CENTRIFUGAL_PUMP.")
    manufacturer: str | None = None
    model_number: str | None = None
    serial_number: str | None = None
    installed_at: datetime | None = None
    parent_asset_id: str | None = None
    operating_envelope: OperatingEnvelope | None = None


class Component(SemanticEntity):
    asset_id: str = Field(..., description="Matches Asset.id and TelemetryReading.component parent.")
    component_type: ComponentType
    criticality: CriticalityTier
    maintainable: bool = True
    component_position: str | None = Field(default=None, description="DE, NDE, suction, discharge, etc.")
    parent_component_id: str | None = None
    material: str | None = None
    manufacturer: str | None = None
    model_number: str | None = None
    serial_number: str | None = None
    installed_at: datetime | None = None
    design_life_hours: float | None = Field(default=None, ge=0.0)
    operating_envelope: OperatingEnvelope | None = None


class Sensor(SemanticEntity):
    sensor_category: SensorCategory
    metric: str = Field(..., description="Must match SensorReading.metric in telemetry.py.")
    unit: SensorUnit
    asset_id: str = Field(..., description="Matches TelemetryReading.asset_id.")
    component_id: str | None = Field(default=None, description="Matches TelemetryReading.component_id when scoped.")
    tag: str
    sampling_method: SamplingMethod
    sampling_frequency_hz: float = Field(..., gt=0.0)
    signal_quality_expected_min: float = Field(default=0.95, ge=0.0, le=1.0)
    baseline_constraints: list[BaselineConstraint] = Field(default_factory=list)
    installation_date: datetime | None = None
    calibration_interval_days: int | None = Field(default=None, gt=0)
    last_calibrated_at: datetime | None = None
    calibration_offset: float | None = None


class TelemetryStream(SemanticEntity):
    sensor_id: str
    asset_id: str
    component_id: str | None = None
    metric: str
    unit: SensorUnit
    sampling_frequency_hz: float = Field(..., gt=0.0)
    retention_policy: str | None = None
    historian_topic: str | None = None


class FailureSymptom(SemanticEntity):
    observed_signal: str
    metric: str | None = None
    unit: SensorUnit | None = None
    symptom_threshold: str | None = Field(default=None, description="Human-readable threshold rule.")
    detection_method: str | None = None


class RootCause(SemanticEntity):
    category: RootCauseCategory
    causal_statement: str
    evidence_required: list[str] = Field(default_factory=list)
    prevention_controls: list[str] = Field(default_factory=list)


class FailureMode(SemanticEntity):
    iso_14224_code: str | None = Field(default=None, description="ISO 14224-aligned local code if known.")
    equipment_class: EquipmentClass
    component_type: ComponentType | None = None
    severity_tier: FailureSeverityTier
    mechanisms: list[FailureMechanism] = Field(..., min_length=1)
    failure_effect: str
    symptoms: list[str] = Field(default_factory=list)
    detection_metrics: list[str] = Field(default_factory=list)
    recommended_sop_ids: list[str] = Field(default_factory=list)
    mtbf_hours: float | None = Field(default=None, ge=0.0)
    risk_priority_number: int | None = Field(default=None, ge=1, le=1000)


class SafetyHazard(SemanticEntity):
    category: HazardCategory
    risk_level: RiskLevel
    hazard_statement: str
    control_measures: list[str] = Field(..., min_length=1)
    required_ppe: list[str] = Field(default_factory=list)
    permit_required: bool = False


class Tooling(SemanticEntity):
    tool_type: str
    calibrated: bool = False
    calibration_due_at: datetime | None = None
    minimum_quantity: int = Field(default=1, ge=1)
    certification_required: str | None = None


class OperatorRole(SemanticEntity):
    role_code: str
    permissions: list[PermissionScope] = Field(..., min_length=1)
    minimum_certifications: list[str] = Field(default_factory=list)
    can_authorize_return_to_service: bool = False


class SOP(SemanticEntity):
    sop_number: str
    title: str
    revision: str
    status: str = Field(default="ACTIVE", description="ACTIVE, DRAFT, SUPERSEDED, RETIRED.")
    source_document_id: str | None = None
    effective_at: datetime | None = None
    owner_role_id: str | None = None
    safety_critical: bool = False


class SOPStep(SemanticEntity):
    sop_id: str
    sequence_number: int = Field(..., ge=1)
    step_type: SOPStepType
    instruction: str
    expected_outcome: str | None = None
    hold_point: bool = False
    estimated_duration_minutes: float | None = Field(default=None, ge=0.0)
    required_role_ids: list[str] = Field(default_factory=list)
    hazard_ids: list[str] = Field(default_factory=list)


class MaintenanceTask(SemanticEntity):
    task_type: MaintenanceAction
    asset_id: str
    component_id: str | None = None
    sop_id: str | None = None
    priority: RiskLevel
    planned_start_at: datetime | None = None
    due_at: datetime | None = None
    estimated_duration_minutes: float | None = Field(default=None, ge=0.0)
    required_role_ids: list[str] = Field(default_factory=list)
    required_tool_ids: list[str] = Field(default_factory=list)


class SourceDocument(SemanticEntity):
    source_type: SourceType
    source_document: str = Field(..., description="Filename or enterprise document ID.")
    revision: str | None = None
    document_url: str | None = None
    effective_at: datetime | None = None
    checksum_sha256: str | None = None


class TextChunk(SemanticEntity):
    chunk_id: str = Field(..., description="Matches Qdrant point ID and VectorContextChunk.chunk_id.")
    source_document_id: str
    source_document: str
    source_type: SourceType
    text: str
    page_number: int | None = None
    section_heading: str | None = None
    asset_ids: list[str] = Field(default_factory=list)
    asset_types: list[AssetType] = Field(default_factory=list)


class EdgePropertySpec(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str
    data_type: str
    required: bool = False
    description: str


class RelationshipRule(BaseModel):
    """Directed graph rule with cardinality and edge-property semantics."""

    model_config = ConfigDict(extra="forbid")

    source_label: GraphNodeLabel
    relationship: GraphRelationshipType
    target_label: GraphNodeLabel
    cardinality: RelationshipCardinality
    required_edge_properties: list[EdgePropertySpec] = Field(default_factory=list)
    optional_edge_properties: list[EdgePropertySpec] = Field(default_factory=list)
    rule: str


RELATIONSHIP_CATALOG: list[RelationshipRule] = [
    RelationshipRule(
        source_label=GraphNodeLabel.ASSET,
        relationship=GraphRelationshipType.COMPRISED_OF,
        target_label=GraphNodeLabel.COMPONENT,
        cardinality=RelationshipCardinality.ONE_TO_MANY,
        optional_edge_properties=[
            EdgePropertySpec(
                name="installed_at",
                data_type="ISO-8601 Datetime",
                description="Date/time the component was installed into the asset.",
            ),
            EdgePropertySpec(
                name="position",
                data_type="String",
                description="Component position such as DE, NDE, suction, discharge.",
            ),
        ],
        rule="Every maintainable Component must be reachable from exactly one owning Asset.",
    ),
    RelationshipRule(
        source_label=GraphNodeLabel.COMPONENT,
        relationship=GraphRelationshipType.MONITORED_BY,
        target_label=GraphNodeLabel.SENSOR,
        cardinality=RelationshipCardinality.ONE_TO_MANY,
        optional_edge_properties=[
            EdgePropertySpec(
                name="installation_date",
                data_type="ISO-8601 Datetime",
                description="Physical installation timestamp for this sensor attachment.",
            ),
            EdgePropertySpec(
                name="calibration_offset",
                data_type="Float",
                description="Offset applied to normalize the sensor reading.",
            ),
        ],
        rule="Component-scoped telemetry must resolve through this edge before PdM inference.",
    ),
    RelationshipRule(
        source_label=GraphNodeLabel.SENSOR,
        relationship=GraphRelationshipType.EXHIBITS_ANOMALY,
        target_label=GraphNodeLabel.FAILURE_MODE,
        cardinality=RelationshipCardinality.MANY_TO_MANY,
        required_edge_properties=[
            EdgePropertySpec(
                name="metric",
                data_type="String",
                required=True,
                description="Telemetry metric that links the anomaly to the failure mode.",
            ),
            EdgePropertySpec(
                name="confidence_weight",
                data_type="Float[0.0,1.0]",
                required=True,
                description="Evidence strength used by GraphRAG traversal ranking.",
            ),
        ],
        optional_edge_properties=[
            EdgePropertySpec(
                name="threshold_rule",
                data_type="String",
                description="Human-readable anomaly threshold, e.g. rms_mm_s > warning_max.",
            ),
            EdgePropertySpec(
                name="detection_window_seconds",
                data_type="Float",
                description="Minimum duration for anomaly persistence.",
            ),
        ],
        rule="A sensor may indicate multiple FailureMode candidates; ranking must use confidence_weight.",
    ),
    RelationshipRule(
        source_label=GraphNodeLabel.FAILURE_MODE,
        relationship=GraphRelationshipType.TRIGGERED_BY,
        target_label=GraphNodeLabel.ROOT_CAUSE,
        cardinality=RelationshipCardinality.MANY_TO_MANY,
        optional_edge_properties=[
            EdgePropertySpec(
                name="causal_confidence",
                data_type="Float[0.0,1.0]",
                description="Historical/evidential confidence in this causal linkage.",
            )
        ],
        rule="Root causes must be classified by RootCauseCategory and remain distinct from symptoms.",
    ),
    RelationshipRule(
        source_label=GraphNodeLabel.FAILURE_MODE,
        relationship=GraphRelationshipType.MITIGATED_BY,
        target_label=GraphNodeLabel.SOP,
        cardinality=RelationshipCardinality.MANY_TO_MANY,
        optional_edge_properties=[
            EdgePropertySpec(
                name="effectiveness",
                data_type="Float[0.0,1.0]",
                description="Historical mitigation effectiveness for this failure mode.",
            ),
            EdgePropertySpec(
                name="required_severity_tier",
                data_type="Enum[CRITICAL,DEGRADED,INCIPIENT]",
                description="Minimum severity tier at which this SOP is applicable.",
            ),
        ],
        rule="GraphRAG recommendations must cite this edge when proposing a procedure for a failure.",
    ),
    RelationshipRule(
        source_label=GraphNodeLabel.SOP,
        relationship=GraphRelationshipType.REQUIRES_TOOL,
        target_label=GraphNodeLabel.TOOLING,
        cardinality=RelationshipCardinality.MANY_TO_MANY,
        optional_edge_properties=[
            EdgePropertySpec(
                name="quantity",
                data_type="Integer",
                description="Minimum number of tools required for the SOP.",
            ),
            EdgePropertySpec(
                name="calibration_required",
                data_type="Boolean",
                description="Whether the tool must be within calibration before use.",
            ),
        ],
        rule="Safety-critical SOPs must list all calibrated tools needed for execution.",
    ),

    RelationshipRule(
        source_label=GraphNodeLabel.LOCATION,
        relationship=GraphRelationshipType.CONTAINS,
        target_label=GraphNodeLabel.ASSET,
        cardinality=RelationshipCardinality.ONE_TO_MANY,
        optional_edge_properties=[
            EdgePropertySpec(
                name="effective_from",
                data_type="ISO-8601 Datetime",
                description="Timestamp from which the asset belongs to this location hierarchy.",
            )
        ],
        rule="Every Asset must be reachable from exactly one operational Location path.",
    ),
    RelationshipRule(
        source_label=GraphNodeLabel.ASSET,
        relationship=GraphRelationshipType.LOCATED_IN,
        target_label=GraphNodeLabel.LOCATION,
        cardinality=RelationshipCardinality.MANY_TO_ONE,
        optional_edge_properties=[
            EdgePropertySpec(
                name="location_confidence",
                data_type="Float[0.0,1.0]",
                description="Confidence when location was inferred from a manual or tag naming rule.",
            )
        ],
        rule="Asset.location_id must agree with the target Location.id for this edge.",
    ),
    RelationshipRule(
        source_label=GraphNodeLabel.COMPONENT,
        relationship=GraphRelationshipType.EMITS_STREAM,
        target_label=GraphNodeLabel.TELEMETRY_STREAM,
        cardinality=RelationshipCardinality.ONE_TO_MANY,
        required_edge_properties=[
            EdgePropertySpec(
                name="metric",
                data_type="String",
                required=True,
                description="Telemetry metric carried by the emitted stream.",
            )
        ],
        rule="A component may expose derived telemetry streams only through a physical Sensor.",
    ),
    RelationshipRule(
        source_label=GraphNodeLabel.SENSOR,
        relationship=GraphRelationshipType.EMITS_STREAM,
        target_label=GraphNodeLabel.TELEMETRY_STREAM,
        cardinality=RelationshipCardinality.ONE_TO_MANY,
        required_edge_properties=[
            EdgePropertySpec(
                name="sampling_frequency_hz",
                data_type="Float",
                required=True,
                description="Sampling frequency expected for the stream.",
            )
        ],
        rule="TelemetryStream.sensor_id must equal the source Sensor.id.",
    ),
    RelationshipRule(
        source_label=GraphNodeLabel.FAILURE_MODE,
        relationship=GraphRelationshipType.HAS_SYMPTOM,
        target_label=GraphNodeLabel.FAILURE_SYMPTOM,
        cardinality=RelationshipCardinality.MANY_TO_MANY,
        optional_edge_properties=[
            EdgePropertySpec(
                name="symptom_confidence",
                data_type="Float[0.0,1.0]",
                description="Observed probability/strength of this symptom for the failure mode.",
            )
        ],
        rule="Symptoms are observable evidence and must not be modelled as root causes.",
    ),
    RelationshipRule(
        source_label=GraphNodeLabel.SOP,
        relationship=GraphRelationshipType.HAS_STEP,
        target_label=GraphNodeLabel.SOP_STEP,
        cardinality=RelationshipCardinality.ONE_TO_MANY,
        required_edge_properties=[
            EdgePropertySpec(
                name="sequence_number",
                data_type="Integer",
                required=True,
                description="Execution order of the SOP step.",
            )
        ],
        rule="SOPStep.sequence_number must be unique within one SOP.",
    ),
    RelationshipRule(
        source_label=GraphNodeLabel.SOP_STEP,
        relationship=GraphRelationshipType.HAS_HAZARD,
        target_label=GraphNodeLabel.SAFETY_HAZARD,
        cardinality=RelationshipCardinality.MANY_TO_MANY,
        optional_edge_properties=[
            EdgePropertySpec(
                name="control_verified_by_role",
                data_type="String",
                description="OperatorRole.id required to verify the hazard control.",
            )
        ],
        rule="Safety-critical steps must have at least one linked SafetyHazard.",
    ),
    RelationshipRule(
        source_label=GraphNodeLabel.SOP_STEP,
        relationship=GraphRelationshipType.REQUIRES_ROLE,
        target_label=GraphNodeLabel.OPERATOR_ROLE,
        cardinality=RelationshipCardinality.MANY_TO_MANY,
        optional_edge_properties=[
            EdgePropertySpec(
                name="permission_scope",
                data_type="Enum[PermissionScope]",
                description="Permission needed to perform or approve the step.",
            )
        ],
        rule="Execution and approval roles must be explicit for safety-critical steps.",
    ),
    RelationshipRule(
        source_label=GraphNodeLabel.MAINTENANCE_TASK,
        relationship=GraphRelationshipType.EXECUTES_SOP,
        target_label=GraphNodeLabel.SOP,
        cardinality=RelationshipCardinality.MANY_TO_ONE,
        optional_edge_properties=[
            EdgePropertySpec(
                name="work_order_id",
                data_type="String",
                description="External CMMS work order ID if available.",
            )
        ],
        rule="A MaintenanceTask may exist without a SOP during triage, but recommendations should prefer SOP-backed tasks.",
    ),
    RelationshipRule(
        source_label=GraphNodeLabel.MAINTENANCE_TASK,
        relationship=GraphRelationshipType.APPLIES_TO_COMPONENT,
        target_label=GraphNodeLabel.COMPONENT,
        cardinality=RelationshipCardinality.MANY_TO_ONE,
        optional_edge_properties=[
            EdgePropertySpec(
                name="planned_outage_required",
                data_type="Boolean",
                description="Whether task execution requires an outage window.",
            )
        ],
        rule="Component-scoped work must also resolve to the owning Asset via COMPRISED_OF/PART_OF.",
    ),
    RelationshipRule(
        source_label=GraphNodeLabel.SOURCE_DOCUMENT,
        relationship=GraphRelationshipType.CONTAINS_CHUNK,
        target_label=GraphNodeLabel.TEXT_CHUNK,
        cardinality=RelationshipCardinality.ONE_TO_MANY,
        required_edge_properties=[
            EdgePropertySpec(
                name="chunk_id",
                data_type="String",
                required=True,
                description="Qdrant point ID for the source chunk.",
            )
        ],
        rule="Every TextChunk surfaced in GraphRAG must be attributable to exactly one SourceDocument.",
    ),
    RelationshipRule(
        source_label=GraphNodeLabel.TEXT_CHUNK,
        relationship=GraphRelationshipType.GROUNDS_ENTITY,
        target_label=GraphNodeLabel.SOP,
        cardinality=RelationshipCardinality.MANY_TO_MANY,
        required_edge_properties=[
            EdgePropertySpec(
                name="claim_field",
                data_type="String",
                required=True,
                description="Entity attribute supported by the chunk text.",
            )
        ],
        rule="GraphRAG citations should resolve through GROUNDS_ENTITY when source_node_id is available.",
    ),
]


UNIQUE_KEY_BY_LABEL: dict[GraphNodeLabel, str] = {
    label: "id" for label in GraphNodeLabel
}


ID_STRATEGY_BY_LABEL: dict[GraphNodeLabel, str] = {
    GraphNodeLabel.LOCATION: "location:<site_code>:<functional_path>",
    GraphNodeLabel.ASSET: "asset:<site_code>:<asset_tag>",
    GraphNodeLabel.COMPONENT: "component:<asset_tag>:<component_type>:<position>",
    GraphNodeLabel.SENSOR: "sensor:<site_code>:<instrument_tag>",
    GraphNodeLabel.TELEMETRY_STREAM: "stream:<sensor_id>:<metric>",
    GraphNodeLabel.FAILURE_MODE: "failuremode:<equipment_class>:<component_type>:<slug>",
    GraphNodeLabel.ROOT_CAUSE: "rootcause:<category>:<slug>",
    GraphNodeLabel.FAILURE_SYMPTOM: "symptom:<metric_or_observation>:<slug>",
    GraphNodeLabel.MAINTENANCE_TASK: "task:<work_order_or_uuid>",
    GraphNodeLabel.SOP: "sop:<sop_number>:<revision>",
    GraphNodeLabel.SOP_STEP: "sopstep:<sop_id>:<sequence_number>",
    GraphNodeLabel.SAFETY_HAZARD: "hazard:<category>:<slug>",
    GraphNodeLabel.TOOLING: "tooling:<tool_code>",
    GraphNodeLabel.OPERATOR_ROLE: "operatorrole:<role_code>",
    GraphNodeLabel.SOURCE_DOCUMENT: "document:<source_type>:<doc_id_or_checksum>",
    GraphNodeLabel.TEXT_CHUNK: "chunk:<qdrant_point_id>",
}


ONTOLOGY_ENTITY_MODELS: dict[GraphNodeLabel, type[BaseModel]] = {
    GraphNodeLabel.LOCATION: Location,
    GraphNodeLabel.ASSET: Asset,
    GraphNodeLabel.COMPONENT: Component,
    GraphNodeLabel.SENSOR: Sensor,
    GraphNodeLabel.TELEMETRY_STREAM: TelemetryStream,
    GraphNodeLabel.FAILURE_MODE: FailureMode,
    GraphNodeLabel.ROOT_CAUSE: RootCause,
    GraphNodeLabel.FAILURE_SYMPTOM: FailureSymptom,
    GraphNodeLabel.MAINTENANCE_TASK: MaintenanceTask,
    GraphNodeLabel.SOP: SOP,
    GraphNodeLabel.SOP_STEP: SOPStep,
    GraphNodeLabel.SAFETY_HAZARD: SafetyHazard,
    GraphNodeLabel.TOOLING: Tooling,
    GraphNodeLabel.OPERATOR_ROLE: OperatorRole,
    GraphNodeLabel.SOURCE_DOCUMENT: SourceDocument,
    GraphNodeLabel.TEXT_CHUNK: TextChunk,
}


def relationship_catalog_as_dict() -> list[dict[str, Any]]:
    """Serialization helper for docs/tests; it performs no database writes."""
    return [rule.model_dump(mode="json") for rule in RELATIONSHIP_CATALOG]
