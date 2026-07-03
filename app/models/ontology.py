"""
Phase 1 — Industrial Knowledge Ontology interfaces
Minimal contract restoration for Phase 4 integration
"""

from __future__ import annotations
from enum import Enum
from typing import List, Dict

class GraphNodeLabel(str, Enum):
    Asset = "Asset"
    Component = "Component"
    Sensor = "Sensor"
    FailureMode = "FailureMode"
    RootCause = "RootCause"
    SOP = "SOP"
    SOPStep = "SOPStep"
    Tooling = "Tooling"
    SafetyHazard = "SafetyHazard"
    Location = "Location"
    MaintenanceTask = "MaintenanceTask"
    FailureSymptom = "FailureSymptom"
    OperatorRole = "OperatorRole"
    TelemetryStream = "TelemetryStream"
    SourceDocument = "SourceDocument"
    TextChunk = "TextChunk"

class GraphRelationshipType(str, Enum):
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
    MENTIONS = "MENTIONS"
    GROUNDS_ENTITY = "GROUNDS_ENTITY"

# Re-export AssetType from common to avoid circular import issues
try:
    from .common import AssetType
except Exception:
    class AssetType(str, Enum):
        PUMP = "PUMP"
        MOTOR = "MOTOR"
        TURBINE = "TURBINE"
        COMPRESSOR = "COMPRESSOR"
        FAN = "FAN"
        GENERIC = "GENERIC"

# Simplified enums
class EquipmentClass(str, Enum):
    ROTATING = "ROTATING"
    STATIC = "STATIC"
    ELECTRICAL = "ELECTRICAL"
    INSTRUMENTATION = "INSTRUMENTATION"

class ComponentType(str, Enum):
    BEARING = "BEARING"
    SEAL = "SEAL"
    IMPELLER = "IMPELLER"
    SHAFT = "SHAFT"
    MOTOR_WINDING = "MOTOR_WINDING"
    VALVE_BODY = "VALVE_BODY"

class SensorCategory(str, Enum):
    VIBRATION = "VIBRATION"
    TEMPERATURE = "TEMPERATURE"
    PRESSURE = "PRESSURE"
    FLOW = "FLOW"
    CURRENT = "CURRENT"

class FailureSeverityTier(str, Enum):
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"

class FailureMechanism(str, Enum):
    WEAR = "WEAR"
    FATIGUE = "FATIGUE"
    CORROSION = "CORROSION"
    MISALIGNMENT = "MISALIGNMENT"

class RootCauseCategory(str, Enum):
    MECHANICAL = "MECHANICAL"
    ELECTRICAL = "ELECTRICAL"
    OPERATIONAL = "OPERATIONAL"
    ENVIRONMENTAL = "ENVIRONMENTAL"

class SOPStepType(str, Enum):
    PREPARATION = "PREPARATION"
    EXECUTION = "EXECUTION"
    VERIFICATION = "VERIFICATION"
    SAFETY_CHECK = "SAFETY_CHECK"

class HazardCategory(str, Enum):
    MECHANICAL = "MECHANICAL"
    ELECTRICAL = "ELECTRICAL"
    CHEMICAL = "CHEMICAL"
    THERMAL = "THERMAL"

class RiskLevel(str, Enum):
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    EXTREME = "EXTREME"

class CriticalityTier(str, Enum):
    A = "A"
    B = "B"
    C = "C"

# Relationship catalog for validation
RELATIONSHIP_CATALOG: Dict[tuple, Dict] = {
    ("Asset", "COMPRISED_OF", "Component"): {},
    ("Component", "MONITORED_BY", "Sensor"): {},
    ("Sensor", "EXHIBITS_ANOMALY", "FailureMode"): {"required_props": ["metric", "confidence_weight"]},
    ("FailureMode", "TRIGGERED_BY", "RootCause"): {},
    ("FailureMode", "MITIGATED_BY", "SOP"): {},
    ("SOP", "HAS_STEP", "SOPStep"): {"required_props": ["sequence_number"]},
}
