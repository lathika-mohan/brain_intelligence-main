"""Phase 1 semantic ontology smoke tests.

These tests do not require Neo4j, Qdrant, PDF parsing, or ML runtime. They
only validate that the industrial knowledge model is importable, that core
Pydantic interfaces accept production-shaped payloads, and that mandatory
relationship rules are present.
"""
from __future__ import annotations

from app.graph.schema import RelationshipType
from app.models.common import AssetStatus, AssetType
from app.models.ontology import (
    Asset,
    Component,
    ComponentType,
    CriticalityTier,
    EquipmentClass,
    FailureMechanism,
    FailureMode,
    FailureSeverityTier,
    GraphNodeLabel,
    GraphRelationshipType,
    MaintenanceAction,
    MaintenanceTask,
    OperatorRole,
    PermissionScope,
    RELATIONSHIP_CATALOG,
    RiskLevel,
    RootCause,
    RootCauseCategory,
    SOP,
    SOPStep,
    SOPStepType,
    SamplingMethod,
    Sensor,
    SensorCategory,
    SafetyHazard,
    HazardCategory,
    Tooling,
)
from app.models.telemetry import SensorUnit


def test_phase1_core_entities_validate_minimal_payloads() -> None:
    asset = Asset(
        id="asset:SRP:P-101A",
        display_name="Pump P-101A",
        asset_type=AssetType.PUMP,
        equipment_class=EquipmentClass.ROTARY_EQUIPMENT,
        tag="P-101A",
        status=AssetStatus.OPERATIONAL,
        criticality=CriticalityTier.PRODUCTION_CRITICAL,
        location_id="location:SRP:plant-1:area-a",
        process_function="Transfers process fluid from feed tank to reactor loop.",
    )
    component = Component(
        id="component:P-101A:BEARING:DE",
        display_name="Drive-end bearing",
        asset_id=asset.id,
        component_type=ComponentType.BEARING,
        criticality=CriticalityTier.PRODUCTION_CRITICAL,
    )
    sensor = Sensor(
        id="sensor:SRP:TE-101A-DE",
        display_name="Drive-end bearing RTD",
        sensor_category=SensorCategory.THERMAL,
        metric="bearing_temp",
        unit=SensorUnit.CELSIUS,
        asset_id=asset.id,
        component_id=component.id,
        tag="TE-101A-DE",
        sampling_method=SamplingMethod.CONTINUOUS,
        sampling_frequency_hz=1.0,
    )
    failure_mode = FailureMode(
        id="failuremode:ROTARY_EQUIPMENT:BEARING:overheat",
        display_name="Bearing overheat",
        equipment_class=EquipmentClass.ROTARY_EQUIPMENT,
        component_type=ComponentType.BEARING,
        severity_tier=FailureSeverityTier.DEGRADED,
        mechanisms=[FailureMechanism.OVERHEATING, FailureMechanism.WEAR],
        failure_effect="Elevated bearing temperature reduces bearing life and may trip the pump.",
        detection_metrics=[sensor.metric],
    )
    root_cause = RootCause(
        id="rootcause:MAINTENANCE:under_lubrication",
        display_name="Under-lubrication",
        category=RootCauseCategory.MAINTENANCE,
        causal_statement="Lubrication interval or quantity is insufficient for observed load.",
    )
    sop = SOP(
        id="sop:SOP-114:REV-C",
        display_name="SOP-114 Bearing Lubrication",
        sop_number="SOP-114",
        title="Bearing Lubrication and Inspection",
        revision="REV-C",
        safety_critical=True,
    )
    step = SOPStep(
        id="sopstep:sop:SOP-114:REV-C:1",
        display_name="Isolate pump",
        sop_id=sop.id,
        sequence_number=1,
        step_type=SOPStepType.ISOLATION,
        instruction="Isolate and lock out the pump drive before removing guards.",
        hold_point=True,
    )
    hazard = SafetyHazard(
        id="hazard:MECHANICAL:rotating_shaft",
        display_name="Rotating shaft exposure",
        category=HazardCategory.MECHANICAL,
        risk_level=RiskLevel.HIGH,
        hazard_statement="Exposed rotating shaft can cause entanglement or impact injury.",
        control_measures=["Apply lockout/tagout", "Verify zero energy", "Keep guards installed"],
    )
    tool = Tooling(
        id="tooling:TORQUE-WRENCH-50NM",
        display_name="50 Nm torque wrench",
        tool_type="TORQUE_WRENCH",
        calibrated=True,
    )
    role = OperatorRole(
        id="operatorrole:MAINT_TECH_L2",
        display_name="Maintenance Technician Level 2",
        role_code="MAINT_TECH_L2",
        permissions=[PermissionScope.READ, PermissionScope.EXECUTE_SOP],
    )
    task = MaintenanceTask(
        id="task:WO-2026-000114",
        display_name="Lubricate drive-end bearing",
        task_type=MaintenanceAction.LUBRICATE,
        asset_id=asset.id,
        component_id=component.id,
        sop_id=sop.id,
        priority=RiskLevel.HIGH,
    )

    assert asset.id == sensor.asset_id
    assert component.id == sensor.component_id
    assert sensor.metric in failure_mode.detection_metrics
    assert root_cause.category == RootCauseCategory.MAINTENANCE
    assert step.sop_id == sop.id
    assert hazard.control_measures
    assert tool.minimum_quantity == 1
    assert PermissionScope.EXECUTE_SOP in role.permissions
    assert task.sop_id == sop.id


def test_mandatory_phase1_relationship_rules_are_present() -> None:
    required = {
        (GraphNodeLabel.ASSET, GraphRelationshipType.COMPRISED_OF, GraphNodeLabel.COMPONENT),
        (GraphNodeLabel.COMPONENT, GraphRelationshipType.MONITORED_BY, GraphNodeLabel.SENSOR),
        (GraphNodeLabel.SENSOR, GraphRelationshipType.EXHIBITS_ANOMALY, GraphNodeLabel.FAILURE_MODE),
        (GraphNodeLabel.FAILURE_MODE, GraphRelationshipType.TRIGGERED_BY, GraphNodeLabel.ROOT_CAUSE),
        (GraphNodeLabel.FAILURE_MODE, GraphRelationshipType.MITIGATED_BY, GraphNodeLabel.SOP),
        (GraphNodeLabel.SOP, GraphRelationshipType.REQUIRES_TOOL, GraphNodeLabel.TOOLING),
    }
    actual = {
        (rule.source_label, rule.relationship, rule.target_label)
        for rule in RELATIONSHIP_CATALOG
    }
    assert required <= actual


def test_phase0_relationship_aliases_map_to_phase1_canonical_labels() -> None:
    assert RelationshipType.HAS_COMPONENT.value == "COMPRISED_OF"
    assert RelationshipType.HAS_SENSOR.value == "MONITORED_BY"
    assert RelationshipType.INDICATES_FAILURE.value == "EXHIBITS_ANOMALY"
