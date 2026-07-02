"""
Neo4j graph schema constants (Phase 1 semantic blueprint).

This module is a lightweight compatibility facade over the Phase 1
industrial ontology in `app.models.ontology`. It intentionally performs
ZERO Cypher execution and contains no database-driver logic. Phase 2 may
use these constants to generate constraints/population scripts, but this
phase only freezes canonical labels, relationship names, unique-key
intent, and ID strategies.

Authoritative human-readable spec: `docs/industrial_knowledge_ontology.md`.
Historical Phase 0 contract mirror: `docs/neo4j_schema.md`.
"""
from enum import Enum

from app.models.ontology import (
    GraphNodeLabel,
    GraphRelationshipType,
    ID_STRATEGY_BY_LABEL,
    UNIQUE_KEY_BY_LABEL,
)


class NodeLabel(str, Enum):
    LOCATION = GraphNodeLabel.LOCATION.value
    ASSET = GraphNodeLabel.ASSET.value
    COMPONENT = GraphNodeLabel.COMPONENT.value
    SENSOR = GraphNodeLabel.SENSOR.value
    TELEMETRY_STREAM = GraphNodeLabel.TELEMETRY_STREAM.value
    FAILURE_MODE = GraphNodeLabel.FAILURE_MODE.value
    ROOT_CAUSE = GraphNodeLabel.ROOT_CAUSE.value
    FAILURE_SYMPTOM = GraphNodeLabel.FAILURE_SYMPTOM.value
    MAINTENANCE_TASK = GraphNodeLabel.MAINTENANCE_TASK.value
    SOP = GraphNodeLabel.SOP.value
    SOP_STEP = GraphNodeLabel.SOP_STEP.value
    SAFETY_HAZARD = GraphNodeLabel.SAFETY_HAZARD.value
    TOOLING = GraphNodeLabel.TOOLING.value
    OPERATOR_ROLE = GraphNodeLabel.OPERATOR_ROLE.value
    SOURCE_DOCUMENT = GraphNodeLabel.SOURCE_DOCUMENT.value
    TEXT_CHUNK = GraphNodeLabel.TEXT_CHUNK.value


class RelationshipType(str, Enum):
    # Phase 1 canonical relationship names.
    LOCATED_IN = GraphRelationshipType.LOCATED_IN.value
    CONTAINS = GraphRelationshipType.CONTAINS.value
    COMPRISED_OF = GraphRelationshipType.COMPRISED_OF.value
    PART_OF = GraphRelationshipType.PART_OF.value
    SUBASSEMBLY_OF = GraphRelationshipType.SUBASSEMBLY_OF.value
    MONITORED_BY = GraphRelationshipType.MONITORED_BY.value
    EMITS_STREAM = GraphRelationshipType.EMITS_STREAM.value
    EXHIBITS_ANOMALY = GraphRelationshipType.EXHIBITS_ANOMALY.value
    HAS_SYMPTOM = GraphRelationshipType.HAS_SYMPTOM.value
    TRIGGERED_BY = GraphRelationshipType.TRIGGERED_BY.value
    MITIGATED_BY = GraphRelationshipType.MITIGATED_BY.value
    REQUIRES_TOOL = GraphRelationshipType.REQUIRES_TOOL.value
    HAS_STEP = GraphRelationshipType.HAS_STEP.value
    HAS_HAZARD = GraphRelationshipType.HAS_HAZARD.value
    REQUIRES_ROLE = GraphRelationshipType.REQUIRES_ROLE.value
    APPLIES_TO_ASSET = GraphRelationshipType.APPLIES_TO_ASSET.value
    APPLIES_TO_COMPONENT = GraphRelationshipType.APPLIES_TO_COMPONENT.value
    EXECUTES_SOP = GraphRelationshipType.EXECUTES_SOP.value
    DOCUMENTED_BY = GraphRelationshipType.DOCUMENTED_BY.value
    CONTAINS_CHUNK = GraphRelationshipType.CONTAINS_CHUNK.value
    GROUNDS_ENTITY = GraphRelationshipType.GROUNDS_ENTITY.value
    DEPENDS_ON = GraphRelationshipType.DEPENDS_ON.value

    # Backward-compatible aliases for Phase 0 names. The value is the Phase 1
    # canonical relationship label; new graph data must use the canonical name.
    HAS_COMPONENT = GraphRelationshipType.COMPRISED_OF.value
    HAS_SENSOR = GraphRelationshipType.MONITORED_BY.value
    INDICATES_FAILURE = GraphRelationshipType.EXHIBITS_ANOMALY.value


UNIQUE_CONSTRAINTS: dict[NodeLabel, str] = {
    NodeLabel[label.name]: UNIQUE_KEY_BY_LABEL[label]
    for label in GraphNodeLabel
    if label.name in NodeLabel.__members__
}


ID_STRATEGIES: dict[NodeLabel, str] = {
    NodeLabel[label.name]: strategy
    for label, strategy in ID_STRATEGY_BY_LABEL.items()
    if label.name in NodeLabel.__members__
}
