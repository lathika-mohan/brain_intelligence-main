"""Canonical node and relationship constants for the Neo4j graph repository.

Provides Phase 1 canonical constants alongside Phase 0 backward-safe alias compatibility.
"""
from __future__ import annotations

from app.models.ontology import GraphNodeLabel, GraphRelationshipType

# Phase 1 Canonical Node Labels
NODE_LABELS = tuple(label.value for label in GraphNodeLabel)

# Phase 1 Canonical Relationship Types
RELATIONSHIP_TYPES = tuple(rel.value for rel in GraphRelationshipType)

# Individual Node Label Constants (Canonical)
ASSET_NODE = GraphNodeLabel.Asset.value
COMPONENT_NODE = GraphNodeLabel.Component.value
SENSOR_NODE = GraphNodeLabel.Sensor.value
FAILURE_MODE_NODE = GraphNodeLabel.FailureMode.value
ROOT_CAUSE_NODE = GraphNodeLabel.RootCause.value
SOP_NODE = GraphNodeLabel.SOP.value
SOP_STEP_NODE = GraphNodeLabel.SOPStep.value
TOOLING_NODE = GraphNodeLabel.Tooling.value
SAFETY_HAZARD_NODE = GraphNodeLabel.SafetyHazard.value
LOCATION_NODE = GraphNodeLabel.Location.value
MAINTENANCE_TASK_NODE = GraphNodeLabel.MaintenanceTask.value
FAILURE_SYMPTOM_NODE = GraphNodeLabel.FailureSymptom.value
OPERATOR_ROLE_NODE = GraphNodeLabel.OperatorRole.value
TELEMETRY_STREAM_NODE = GraphNodeLabel.TelemetryStream.value
SOURCE_DOCUMENT_NODE = GraphNodeLabel.SourceDocument.value
TEXT_CHUNK_NODE = GraphNodeLabel.TextChunk.value

# Individual Relationship Constants (Canonical)
COMPRISED_OF_REL = GraphRelationshipType.COMPRISED_OF.value
MONITORED_BY_REL = GraphRelationshipType.MONITORED_BY.value
EXHIBITS_ANOMALY_REL = GraphRelationshipType.EXHIBITS_ANOMALY.value
TRIGGERED_BY_REL = GraphRelationshipType.TRIGGERED_BY.value
MITIGATED_BY_REL = GraphRelationshipType.MITIGATED_BY.value
REQUIRES_TOOL_REL = GraphRelationshipType.REQUIRES_TOOL.value
HAS_STEP_REL = GraphRelationshipType.HAS_STEP.value
LOCATED_IN_REL = GraphRelationshipType.LOCATED_IN.value
HAS_SYMPTOM_REL = GraphRelationshipType.HAS_SYMPTOM.value
HAS_HAZARD_REL = GraphRelationshipType.HAS_HAZARD.value
REQUIRES_ROLE_REL = GraphRelationshipType.REQUIRES_ROLE.value
EMITS_STREAM_REL = GraphRelationshipType.EMITS_STREAM.value
MENTIONS_REL = GraphRelationshipType.MENTIONS.value
GROUNDS_ENTITY_REL = GraphRelationshipType.GROUNDS_ENTITY.value

# Phase 0 Backward-Safe Alias Compatibility
HAS_COMPONENT_REL = "HAS_COMPONENT"  # Phase 0 alias for COMPRISED_OF
HAS_SENSOR_REL = "HAS_SENSOR"        # Phase 0 alias for MONITORED_BY
INDICATES_FAILURE_REL = "INDICATES_FAILURE"  # Phase 0 alias for EXHIBITS_ANOMALY
PART_OF_REL = "PART_OF"
DEPENDS_ON_REL = "DEPENDS_ON"

# Aliases dictionary mapping Phase 0 names to Phase 1 canonical names where applicable
PHASE0_TO_PHASE1_LABEL_ALIASES = {
    "Asset": ASSET_NODE,
    "Component": COMPONENT_NODE,
    "Sensor": SENSOR_NODE,
    "FailureMode": FAILURE_MODE_NODE,
    "SOP": SOP_NODE,
}

PHASE0_TO_PHASE1_REL_ALIASES = {
    "HAS_COMPONENT": COMPRISED_OF_REL,
    "HAS_SENSOR": MONITORED_BY_REL,
    "INDICATES_FAILURE": EXHIBITS_ANOMALY_REL,
    "MITIGATED_BY": MITIGATED_BY_REL,
}

__all__ = [
    "NODE_LABELS",
    "RELATIONSHIP_TYPES",
    "ASSET_NODE",
    "COMPONENT_NODE",
    "SENSOR_NODE",
    "FAILURE_MODE_NODE",
    "ROOT_CAUSE_NODE",
    "SOP_NODE",
    "SOP_STEP_NODE",
    "TOOLING_NODE",
    "SAFETY_HAZARD_NODE",
    "LOCATION_NODE",
    "MAINTENANCE_TASK_NODE",
    "FAILURE_SYMPTOM_NODE",
    "OPERATOR_ROLE_NODE",
    "TELEMETRY_STREAM_NODE",
    "SOURCE_DOCUMENT_NODE",
    "TEXT_CHUNK_NODE",
    "COMPRISED_OF_REL",
    "MONITORED_BY_REL",
    "EXHIBITS_ANOMALY_REL",
    "TRIGGERED_BY_REL",
    "MITIGATED_BY_REL",
    "REQUIRES_TOOL_REL",
    "HAS_STEP_REL",
    "LOCATED_IN_REL",
    "HAS_SYMPTOM_REL",
    "HAS_HAZARD_REL",
    "REQUIRES_ROLE_REL",
    "EMITS_STREAM_REL",
    "MENTIONS_REL",
    "GROUNDS_ENTITY_REL",
    "HAS_COMPONENT_REL",
    "HAS_SENSOR_REL",
    "INDICATES_FAILURE_REL",
    "PART_OF_REL",
    "DEPENDS_ON_REL",
    "PHASE0_TO_PHASE1_LABEL_ALIASES",
    "PHASE0_TO_PHASE1_REL_ALIASES",
]
