# Phase 1 Industrial Knowledge Modelling Specification

**Project:** Industrial Operating Brain — AI Intelligence Platform  
**Owner:** Member 3 — AI & Knowledge Engineer  
**Status:** Phase 1 semantic blueprint, implementation-ready  
**Ontology version:** `1.0.0`  
**Last updated:** 2026-07-02  
**Machine-readable interface:** `app/models/ontology.py`

---

## 0. Scope, non-goals, and contract discipline

This document is the semantic backbone for the Phase 2 Neo4j Knowledge Graph and later GraphRAG/Predictive Maintenance pipelines. It defines entity classes, inheritance rules, node payloads, relationship semantics, edge properties, and downstream alignment to Phase 0 contracts.

**In scope**

- Industrial domain taxonomies for assets, components, sensors, failure modes, SOPs, roles, tools, and source-document hooks.
- Canonical graph labels and UPPERCASE_SNAKE_CASE relationship labels.
- Primary key strategies, strict attribute types, enums, and edge metadata.
- Traceability rules from natural-language answers to SOP/manual text chunks.
- Alignment with Member 2 telemetry schemas and existing `GraphContextMap` / `Citation` API contracts.

**Explicitly out of scope for Phase 1**

- No Cypher scripts, graph population jobs, Neo4j driver logic, or database bootstrap edits.
- No PDF parser, OCR parser, chunking algorithm, embedding pipeline, or Qdrant ingestion code.
- No React/Next.js UI changes.
- No ML model implementation, training, inference, or SHAP/LIME computation changes.

---

## 1. Global ontology rules

### 1.1 Naming conventions

| Concern | Rule |
|---|---|
| Node labels | PascalCase, singular: `Asset`, `FailureMode`, `SOPStep` |
| Relationship labels | UPPERCASE_SNAKE_CASE verbs: `COMPRISED_OF`, `MONITORED_BY` |
| Primary ID field | Every node has `id: String` as canonical graph key |
| Datetimes | ISO-8601 UTC datetimes unless a location timezone is explicitly modelled |
| Units | Use `SensorUnit` from `app/models/telemetry.py` wherever possible |
| Enums | Uppercase string enums to preserve stable JSON serialization |
| Descriptions | Human-readable text is optional except where it is core operating knowledge |

### 1.2 Required inherited fields for every node

Every entity inherits the following semantic payload from `SemanticEntity` in `app/models/ontology.py`:

| Field | Type | Required | Rule |
|---|---:|:---:|---|
| `id` | String | Yes | Canonical graph ID following the label-specific strategy in §1.3 |
| `display_name` | String | Yes | Human-readable label for UI/API graph rendering |
| `description` | String \/ null | No | Free-text definition or operating context |
| `aliases` | List[String] | No | Alternative tags, OEM names, legacy names |
| `ontology_version` | String | Yes | Defaults to `1.0.0` |
| `citation_anchors` | List[`CitationAnchor`] | No | Source text hooks for GraphRAG traceability |
| `metadata` | Map[String,String] | No | Non-authoritative integration metadata only |

### 1.3 Primary key strategy by label

| Label | Primary key strategy | Example |
|---|---|---|
| `Location` | `location:<site_code>:<functional_path>` | `location:SRP:plant-1:area-a` |
| `Asset` | `asset:<site_code>:<asset_tag>` | `asset:SRP:P-101A` |
| `Component` | `component:<asset_tag>:<component_type>:<position>` | `component:P-101A:BEARING:DE` |
| `Sensor` | `sensor:<site_code>:<instrument_tag>` | `sensor:SRP:TE-101A-DE` |
| `TelemetryStream` | `stream:<sensor_id>:<metric>` | `stream:sensor:SRP:TE-101A-DE:bearing_temp` |
| `FailureMode` | `failuremode:<equipment_class>:<component_type>:<slug>` | `failuremode:ROTARY_EQUIPMENT:BEARING:overheat` |
| `RootCause` | `rootcause:<category>:<slug>` | `rootcause:MAINTENANCE:under_lubrication` |
| `FailureSymptom` | `symptom:<metric_or_observation>:<slug>` | `symptom:vibration_rms:elevated` |
| `MaintenanceTask` | `task:<work_order_or_uuid>` | `task:WO-2026-000114` |
| `SOP` | `sop:<sop_number>:<revision>` | `sop:SOP-114:REV-C` |
| `SOPStep` | `sopstep:<sop_id>:<sequence_number>` | `sopstep:sop:SOP-114:REV-C:7` |
| `SafetyHazard` | `hazard:<category>:<slug>` | `hazard:MECHANICAL:rotating_shaft` |
| `Tooling` | `tooling:<tool_code>` | `tooling:TORQUE-WRENCH-50NM` |
| `OperatorRole` | `operatorrole:<role_code>` | `operatorrole:MAINT_TECH_L2` |
| `SourceDocument` | `document:<source_type>:<doc_id_or_checksum>` | `document:SOP:SOP-114-REV-C` |
| `TextChunk` | `chunk:<qdrant_point_id>` | `chunk:4c0f6e21-...` |

---

## 2. Domain ontology specifications

### 2.1 Asset & Machine Ontology

```text
IndustrialEntity
├── Location
│   ├── Site
│   ├── Plant
│   ├── Area
│   ├── Unit / Line
│   ├── Skid
│   └── FunctionalLocation
├── Asset
│   ├── RotaryEquipment
│   │   ├── Pump
│   │   │   ├── CentrifugalPump
│   │   │   └── PositiveDisplacementPump
│   │   ├── Compressor
│   │   │   ├── CentrifugalCompressor
│   │   │   └── ReciprocatingCompressor
│   │   ├── Turbine
│   │   ├── Fan / Blower
│   │   └── Mixer / Agitator
│   ├── StaticEquipment
│   │   ├── Tank / Vessel
│   │   ├── HeatExchanger
│   │   ├── PipingSegment
│   │   └── Valve
│   ├── ElectricalEquipment
│   │   ├── Motor
│   │   ├── VFD
│   │   ├── MCC
│   │   └── Transformer
│   ├── InstrumentationControl
│   │   ├── PLC
│   │   ├── RTU
│   │   ├── ControlPanel
│   │   └── SensorNode
│   └── MaterialHandling
│       ├── Conveyor
│       ├── Hoist
│       └── Feeder
└── Component
    ├── Bearing
    ├── Seal
    ├── Impeller
    ├── Shaft
    ├── Coupling
    ├── Gearbox
    ├── MotorWinding
    ├── Casing
    ├── ValveBody
    ├── Actuator
    ├── Filter
    ├── LubricationSystem
    ├── CoolingSystem
    └── ControlModule
```

**Inheritance rules**

1. Every `Asset` inherits global fields plus `asset_type`, `equipment_class`, `tag`, `status`, `criticality`, `location_id`, and `process_function`.
2. Asset subclassing is semantic, not a separate graph label in Phase 1. Use `equipment_class` and `asset_subclass` fields instead of proliferating labels.
3. Every maintainable `Component` belongs to one owning `Asset` through `(:Asset)-[:COMPRISED_OF]->(:Component)`.
4. Nested sub-assemblies are allowed through `(:Component)-[:SUBASSEMBLY_OF]->(:Component)` but must remain reachable from an `Asset`.
5. Physical location is modelled separately from process dependency. Use `LOCATED_IN` / `CONTAINS` for location and `DEPENDS_ON` for process dependency.

### 2.2 Sensor & Telemetry Ontology

```text
Sensor
├── VibrationSensor
│   ├── Accelerometer
│   ├── VelocityProbe
│   └── ProximityProbe
├── ThermalSensor
│   ├── RTD
│   ├── Thermocouple
│   └── InfraredSensor
├── PressureSensor
│   ├── GaugePressureTransmitter
│   └── DifferentialPressureTransmitter
├── FlowSensor
│   ├── MagneticFlowMeter
│   ├── CoriolisFlowMeter
│   └── UltrasonicFlowMeter
├── SpeedSensor
├── ElectricalSensor
│   ├── CurrentTransformer
│   ├── VoltageProbe
│   └── PowerMeter
├── AcousticSensor
└── QualitySensor

Sensor
└── TelemetryStream
    ├── metric
    ├── unit
    ├── sampling_frequency_hz
    ├── retention_policy
    └── historian_topic
```

**Sensor modelling rules**

| Rule | Description |
|---|---|
| Sensor-to-telemetry contract | `Sensor.id` must match `SensorReading.sensor_id` from Member 2 telemetry. |
| Metric contract | `Sensor.metric` must match `SensorReading.metric` exactly. |
| Unit contract | `Sensor.unit` must match `SensorReading.unit` and be one of `SensorUnit`. |
| Asset scope | `Sensor.asset_id` must match `TelemetryReading.asset_id`. |
| Component scope | `Sensor.component_id` may be null only for asset-level/process sensors. |
| Baselines | Normal/warning/critical ranges are represented as `BaselineConstraint` records on the `Sensor` or owning `OperatingEnvelope`. |
| Frequency | `sampling_frequency_hz` is required and must be greater than zero. |
| Quality | `signal_quality_expected_min` governs acceptance thresholds for live telemetry quality. |

**Baseline constraint payload**

| Field | Type | Required | Meaning |
|---|---:|:---:|---|
| `metric` | String | Yes | Telemetry metric name |
| `unit` | Enum[`SensorUnit`] | Yes | Unit for all numeric limits |
| `normal_min`, `normal_max` | Float \/ null | No | Expected baseline range |
| `warning_min`, `warning_max` | Float \/ null | No | Warning threshold range |
| `critical_min`, `critical_max` | Float \/ null | No | Critical threshold range |
| `operating_mode` | String \/ null | No | RUNNING, STARTUP, IDLE, SHUTDOWN, etc. |
| `baseline_window_hours` | Float \/ null | No | Rolling statistical baseline window |
| `source` | String \/ null | No | OEM/SOP/manual reference |

### 2.3 Failure & Maintenance Ontology

This ontology follows the ISO 14224-style separation between **failure mode**, **failure mechanism**, **failure cause/root cause**, **failure symptom**, and **failure effect**.

```text
FailureKnowledge
├── FailureMode
│   ├── Critical
│   ├── Degraded
│   └── Incipient
├── FailureMechanism
│   ├── Fatigue
│   ├── Wear
│   ├── Corrosion
│   ├── Erosion
│   ├── Cavitation
│   ├── Fouling
│   ├── Leakage
│   ├── Overheating
│   ├── Misalignment
│   ├── Imbalance
│   ├── ElectricalFault
│   ├── Contamination
│   ├── SoftwareControlFault
│   └── HumanError
├── RootCause
│   ├── Design
│   ├── Manufacturing
│   ├── Installation
│   ├── Operational
│   ├── Maintenance
│   ├── Environmental
│   ├── Material
│   ├── ControlSystem
│   └── HumanFactor
└── FailureSymptom
    ├── TelemetryAnomaly
    ├── VisualObservation
    ├── AcousticObservation
    ├── Odour / Leak Observation
    └── MaintenanceLogEvidence
```

**Failure chain semantics**

```text
Sensor/Telemetry anomaly
    -> EXHIBITS_ANOMALY
FailureMode
    -> TRIGGERED_BY
RootCause
FailureMode
    -> HAS_SYMPTOM
FailureSymptom
FailureMode
    -> MITIGATED_BY
SOP
```

**Severity tiers**

| Tier | Meaning | GraphRAG / PdM behaviour |
|---|---|---|
| `CRITICAL` | Immediate safety, environmental, or production risk | Must surface safety hazards, isolation requirements, and urgent SOPs first |
| `DEGRADED` | Reduced capability or rising risk, but not immediate trip/failure | Recommend planned maintenance and likely root causes |
| `INCIPIENT` | Early evidence of abnormality or weak anomaly | Prefer diagnostics, inspection, and monitoring SOPs |

### 2.4 SOP Ontology

```text
ProcedureKnowledge
├── SOP
│   ├── MaintenanceSOP
│   ├── OperatingSOP
│   ├── CalibrationSOP
│   ├── EmergencySOP
│   └── InspectionSOP
├── SOPStep
│   ├── PreJobBrief
│   ├── SafetyCheck
│   ├── Isolation
│   ├── Execution
│   ├── Inspection
│   ├── Calibration
│   ├── Verification
│   ├── ReturnToService
│   └── Documentation
├── MaintenanceTask
│   ├── Inspect
│   ├── Isolate
│   ├── LockoutTagout
│   ├── Lubricate
│   ├── Calibrate
│   ├── Align
│   ├── Balance
│   ├── Replace
│   ├── Test
│   ├── Restore
│   └── Document
├── SafetyHazard
├── Tooling
└── OperatorRole
```

**SOP workflow rules**

1. An `SOP` is an ordered workflow made of `SOPStep` nodes through `HAS_STEP` edges.
2. Safety-critical SOPs must include at least one safety check/isolation step and at least one `SafetyHazard` link.
3. Role permissions are explicit; do not encode permissions only as text in a step.
4. Required tooling belongs on `(:SOP)-[:REQUIRES_TOOL]->(:Tooling)` so the decision engine can reason about execution readiness.
5. `MaintenanceTask` is a planned or recommended executable work item that may execute an SOP and apply to an asset/component.

---

## 3. Comprehensive entity dictionary

The authoritative Pydantic V2 interfaces are in `app/models/ontology.py`. The following tables are the human-readable entity dictionary.

### 3.1 Location

| Field | Type | Required | Notes |
|---|---:|:---:|---|
| inherited fields | See §1.2 | Yes | Includes `id`, `display_name`, `ontology_version` |
| `location_type` | Enum[`LocationType`] | Yes | SITE, PLANT, AREA, UNIT, LINE, SKID, ROOM, FUNCTIONAL_LOCATION |
| `site_code` | String | Yes | Plant/site code used in primary key strategy |
| `parent_location_id` | String \/ null | No | Parent in location hierarchy |
| `timezone` | String \/ null | No | IANA timezone for local schedules |

### 3.2 Asset

| Field | Type | Required | Notes |
|---|---:|:---:|---|
| inherited fields | See §1.2 | Yes | `id` maps to Phase 0 `TelemetryReading.asset_id` |
| `asset_type` | Enum[`AssetType`] | Yes | Existing Phase 0 enum: PUMP, MOTOR, COMPRESSOR, etc. |
| `equipment_class` | Enum[`EquipmentClass`] | Yes | ROTARY_EQUIPMENT, STATIC_EQUIPMENT, etc. |
| `tag` | String | Yes | Plant asset tag |
| `status` | Enum[`AssetStatus`] | Yes | Existing Phase 0 status enum |
| `criticality` | Enum[`CriticalityTier`] | Yes | Safety/production/quality criticality |
| `location_id` | String | Yes | Must resolve to `Location.id` |
| `process_function` | String | Yes | Functional role in the plant process |
| `asset_subclass` | String \/ null | No | e.g. CENTRIFUGAL_PUMP |
| `manufacturer`, `model_number`, `serial_number` | String \/ null | No | OEM identity |
| `installed_at` | ISO-8601 Datetime \/ null | No | Installation timestamp |
| `parent_asset_id` | String \/ null | No | Asset hierarchy for packages/skids |
| `operating_envelope` | `OperatingEnvelope` \/ null | No | Rated load, pressure, temp, speed and baselines |

### 3.3 Component

| Field | Type | Required | Notes |
|---|---:|:---:|---|
| inherited fields | See §1.2 | Yes | Canonical graph payload |
| `asset_id` | String | Yes | Owning `Asset.id` |
| `component_type` | Enum[`ComponentType`] | Yes | BEARING, SEAL, IMPELLER, etc. |
| `criticality` | Enum[`CriticalityTier`] | Yes | Component-level risk criticality |
| `maintainable` | Boolean | Yes | Defaults true |
| `component_position` | String \/ null | No | DE, NDE, suction, discharge, etc. |
| `parent_component_id` | String \/ null | No | For nested assemblies |
| `material`, `manufacturer`, `model_number`, `serial_number` | String \/ null | No | Engineering identity fields |
| `installed_at` | ISO-8601 Datetime \/ null | No | Installation timestamp |
| `design_life_hours` | Float \/ null | No | Non-negative design life |
| `operating_envelope` | `OperatingEnvelope` \/ null | No | Component-specific operating constraints |

### 3.4 Sensor

| Field | Type | Required | Notes |
|---|---:|:---:|---|
| inherited fields | See §1.2 | Yes | `id` maps to `SensorReading.sensor_id` |
| `sensor_category` | Enum[`SensorCategory`] | Yes | VIBRATION, THERMAL, PRESSURE, etc. |
| `metric` | String | Yes | Must match `SensorReading.metric` |
| `unit` | Enum[`SensorUnit`] | Yes | Must match `SensorReading.unit` |
| `asset_id` | String | Yes | Must match telemetry `asset_id` |
| `component_id` | String \/ null | No | Must match telemetry `component_id` when present |
| `tag` | String | Yes | Instrument tag |
| `sampling_method` | Enum[`SamplingMethod`] | Yes | CONTINUOUS, PERIODIC, EVENT_DRIVEN, MANUAL |
| `sampling_frequency_hz` | Float | Yes | Must be > 0 |
| `signal_quality_expected_min` | Float | Yes | 0.0 to 1.0, default 0.95 |
| `baseline_constraints` | List[`BaselineConstraint`] | No | Normal/warning/critical thresholds |
| `installation_date`, `last_calibrated_at` | ISO-8601 Datetime \/ null | No | Lifecycle timestamps |
| `calibration_interval_days` | Integer \/ null | No | Must be > 0 when provided |
| `calibration_offset` | Float \/ null | No | Calibration offset for normalized readings |

### 3.5 TelemetryStream

| Field | Type | Required | Notes |
|---|---:|:---:|---|
| inherited fields | See §1.2 | Yes | Canonical stream node |
| `sensor_id` | String | Yes | Source `Sensor.id` |
| `asset_id` | String | Yes | Parent `Asset.id` |
| `component_id` | String \/ null | No | Parent `Component.id` if scoped |
| `metric` | String | Yes | Stream metric |
| `unit` | Enum[`SensorUnit`] | Yes | Stream unit |
| `sampling_frequency_hz` | Float | Yes | Expected sampling rate |
| `retention_policy` | String \/ null | No | Historian retention policy |
| `historian_topic` | String \/ null | No | Kafka/MQTT/historian topic |

### 3.6 FailureMode

| Field | Type | Required | Notes |
|---|---:|:---:|---|
| inherited fields | See §1.2 | Yes | `id` maps to `FailureProbability.failure_mode_id` |
| `iso_14224_code` | String \/ null | No | Local ISO 14224-aligned classification code |
| `equipment_class` | Enum[`EquipmentClass`] | Yes | Equipment family affected |
| `component_type` | Enum[`ComponentType`] \/ null | No | Component affected when known |
| `severity_tier` | Enum[`FailureSeverityTier`] | Yes | CRITICAL, DEGRADED, INCIPIENT |
| `mechanisms` | List[`FailureMechanism`] | Yes | At least one mechanism required |
| `failure_effect` | String | Yes | Operational effect of failure mode |
| `symptoms` | List[String] | No | Historical symptoms or observable signs |
| `detection_metrics` | List[String] | No | Telemetry metric names used for detection |
| `recommended_sop_ids` | List[String] | No | SOPs commonly associated with mitigation |
| `mtbf_hours` | Float \/ null | No | Historical mean time between failures |
| `risk_priority_number` | Integer \/ null | No | 1 to 1000 where provided |

### 3.7 RootCause

| Field | Type | Required | Notes |
|---|---:|:---:|---|
| inherited fields | See §1.2 | Yes | Canonical root-cause node |
| `category` | Enum[`RootCauseCategory`] | Yes | DESIGN, MAINTENANCE, OPERATIONAL, etc. |
| `causal_statement` | String | Yes | Root-cause assertion |
| `evidence_required` | List[String] | No | Evidence needed before confirming this cause |
| `prevention_controls` | List[String] | No | Controls that reduce recurrence |

### 3.8 FailureSymptom

| Field | Type | Required | Notes |
|---|---:|:---:|---|
| inherited fields | See §1.2 | Yes | Symptom node |
| `observed_signal` | String | Yes | Human/operator/telemetry observation |
| `metric` | String \/ null | No | Metric when telemetry-derived |
| `unit` | Enum[`SensorUnit`] \/ null | No | Unit for thresholded symptom |
| `symptom_threshold` | String \/ null | No | Human-readable rule |
| `detection_method` | String \/ null | No | Inspection, telemetry, lab test, etc. |

### 3.9 SOP

| Field | Type | Required | Notes |
|---|---:|:---:|---|
| inherited fields | See §1.2 | Yes | `id` maps to `Citation.source_node_id` when citing SOPs |
| `sop_number` | String | Yes | Procedure number |
| `title` | String | Yes | Procedure title |
| `revision` | String | Yes | Revision code |
| `status` | String | Yes | ACTIVE, DRAFT, SUPERSEDED, RETIRED |
| `source_document_id` | String \/ null | No | Linked `SourceDocument.id` |
| `effective_at` | ISO-8601 Datetime \/ null | No | Revision effective date |
| `owner_role_id` | String \/ null | No | Responsible `OperatorRole.id` |
| `safety_critical` | Boolean | Yes | Whether safety checks are mandatory |

### 3.10 SOPStep

| Field | Type | Required | Notes |
|---|---:|:---:|---|
| inherited fields | See §1.2 | Yes | `id` can be used as citation node for step-level grounding |
| `sop_id` | String | Yes | Parent `SOP.id` |
| `sequence_number` | Integer | Yes | Must be >= 1 and unique within SOP |
| `step_type` | Enum[`SOPStepType`] | Yes | Safety, isolation, execution, verification, etc. |
| `instruction` | String | Yes | Actionable step instruction |
| `expected_outcome` | String \/ null | No | Observable success condition |
| `hold_point` | Boolean | Yes | Requires explicit hold/approval |
| `estimated_duration_minutes` | Float \/ null | No | Non-negative estimate |
| `required_role_ids` | List[String] | No | Linked roles |
| `hazard_ids` | List[String] | No | Linked safety hazards |

### 3.11 MaintenanceTask

| Field | Type | Required | Notes |
|---|---:|:---:|---|
| inherited fields | See §1.2 | Yes | Decision engine work item |
| `task_type` | Enum[`MaintenanceAction`] | Yes | ISOLATE, LUBRICATE, CALIBRATE, etc. |
| `asset_id` | String | Yes | Target asset |
| `component_id` | String \/ null | No | Target component |
| `sop_id` | String \/ null | No | Governing SOP when available |
| `priority` | Enum[`RiskLevel`] | Yes | LOW, MEDIUM, HIGH, CRITICAL |
| `planned_start_at`, `due_at` | ISO-8601 Datetime \/ null | No | Planning dates |
| `estimated_duration_minutes` | Float \/ null | No | Non-negative estimate |
| `required_role_ids`, `required_tool_ids` | List[String] | No | Execution readiness links |

### 3.12 SafetyHazard

| Field | Type | Required | Notes |
|---|---:|:---:|---|
| inherited fields | See §1.2 | Yes | Safety knowledge node |
| `category` | Enum[`HazardCategory`] | Yes | ELECTRICAL, MECHANICAL, PRESSURE, etc. |
| `risk_level` | Enum[`RiskLevel`] | Yes | LOW to CRITICAL |
| `hazard_statement` | String | Yes | Hazard description |
| `control_measures` | List[String] | Yes | At least one control required |
| `required_ppe` | List[String] | No | PPE list |
| `permit_required` | Boolean | Yes | Permit-to-work requirement |

### 3.13 Tooling

| Field | Type | Required | Notes |
|---|---:|:---:|---|
| inherited fields | See §1.2 | Yes | Tool/equipment needed for SOP execution |
| `tool_type` | String | Yes | Torque wrench, dial indicator, vibration analyzer, etc. |
| `calibrated` | Boolean | Yes | Whether tool is calibration-controlled |
| `calibration_due_at` | ISO-8601 Datetime \/ null | No | Due date if calibration-controlled |
| `minimum_quantity` | Integer | Yes | Defaults to 1, must be >= 1 |
| `certification_required` | String \/ null | No | Required certificate/standard |

### 3.14 OperatorRole

| Field | Type | Required | Notes |
|---|---:|:---:|---|
| inherited fields | See §1.2 | Yes | Role/permission node |
| `role_code` | String | Yes | Stable enterprise role code |
| `permissions` | List[`PermissionScope`] | Yes | At least one permission required |
| `minimum_certifications` | List[String] | No | Required certifications |
| `can_authorize_return_to_service` | Boolean | Yes | Explicit RTS authorization flag |

### 3.15 SourceDocument and TextChunk

| Entity | Required fields | Optional fields | Purpose |
|---|---|---|---|
| `SourceDocument` | `source_type`, `source_document` | `revision`, `document_url`, `effective_at`, `checksum_sha256` | Represents SOP/manual/incident source artifact |
| `TextChunk` | `chunk_id`, `source_document_id`, `source_document`, `source_type`, `text` | `page_number`, `section_heading`, `asset_ids`, `asset_types` | GraphRAG retrievable chunk aligned with Qdrant payload |

---

## 4. Strict relationship and edge catalogue

| Source → Relationship → Target | Cardinality | Required edge properties | Optional edge properties | Rule |
|---|---|---|---|---|
| `(:Location)-[:CONTAINS]->(:Asset)` | One-to-many | — | `effective_from: ISO-8601 Datetime` | Every asset must be reachable from one operational location path. |
| `(:Asset)-[:LOCATED_IN]->(:Location)` | Many-to-one | — | `location_confidence: Float[0,1]` | Must agree with `Asset.location_id`. |
| `(:Asset)-[:COMPRISED_OF]->(:Component)` | One-to-many | — | `installed_at`, `position` | Mandatory asset composition relationship. |
| `(:Component)-[:SUBASSEMBLY_OF]->(:Component)` | Many-to-one | — | `position`, `assembly_sequence` | Nested components must remain reachable from an asset. |
| `(:Component)-[:MONITORED_BY]->(:Sensor)` | One-to-many | — | `installation_date`, `calibration_offset`, `mounting_position` | Mandatory component-sensor attachment. |
| `(:Sensor)-[:EMITS_STREAM]->(:TelemetryStream)` | One-to-many | `sampling_frequency_hz: Float` | `historian_topic`, `retention_policy` | Stream fields must match source sensor metric/unit. |
| `(:Sensor)-[:EXHIBITS_ANOMALY]->(:FailureMode)` | Many-to-many | `metric: String`, `confidence_weight: Float[0,1]` | `threshold_rule`, `detection_window_seconds`, `baseline_window_hours` | Mandatory anomaly-to-failure candidate relationship. |
| `(:FailureMode)-[:HAS_SYMPTOM]->(:FailureSymptom)` | Many-to-many | — | `symptom_confidence: Float[0,1]` | Symptoms are evidence, not causes. |
| `(:FailureMode)-[:TRIGGERED_BY]->(:RootCause)` | Many-to-many | — | `causal_confidence: Float[0,1]`, `evidence_type` | Mandatory failure-root cause relationship. |
| `(:FailureMode)-[:MITIGATED_BY]->(:SOP)` | Many-to-many | — | `effectiveness: Float[0,1]`, `required_severity_tier` | Mandatory failure-SOP relationship. |
| `(:SOP)-[:REQUIRES_TOOL]->(:Tooling)` | Many-to-many | — | `quantity: Integer`, `calibration_required: Boolean` | Mandatory SOP-tool relationship. |
| `(:SOP)-[:HAS_STEP]->(:SOPStep)` | One-to-many | `sequence_number: Integer` | `is_parallel_allowed: Boolean` | SOP steps are ordered by edge/step sequence. |
| `(:SOPStep)-[:HAS_HAZARD]->(:SafetyHazard)` | Many-to-many | — | `control_verified_by_role: String` | Safety-critical steps require hazard links. |
| `(:SOPStep)-[:REQUIRES_ROLE]->(:OperatorRole)` | Many-to-many | — | `permission_scope: PermissionScope`, `approval_required: Boolean` | Procedure permissions are explicit. |
| `(:MaintenanceTask)-[:EXECUTES_SOP]->(:SOP)` | Many-to-one | — | `work_order_id: String` | Task may be SOP-backed; recommended tasks should prefer SOP-backed actions. |
| `(:MaintenanceTask)-[:APPLIES_TO_ASSET]->(:Asset)` | Many-to-one | — | `planned_outage_required: Boolean` | Asset-scoped maintenance target. |
| `(:MaintenanceTask)-[:APPLIES_TO_COMPONENT]->(:Component)` | Many-to-one | — | `planned_outage_required: Boolean` | Component-scoped work must resolve to owning asset. |
| `(:Asset)-[:DEPENDS_ON]->(:Asset)` | Many-to-many | — | `dependency_type`, `process_direction`, `criticality_weight` | Process dependency, not physical location. |
| `(:SourceDocument)-[:CONTAINS_CHUNK]->(:TextChunk)` | One-to-many | `chunk_id: String` | `page_number`, `section_heading` | Every chunk must resolve to one source document. |
| `(:TextChunk)-[:GROUNDS_ENTITY]->(:SOP)` | Many-to-many | `claim_field: String` | `confidence_score: Float[0,1]` | Supports GraphRAG citation to SOP fields. |
| `(:TextChunk)-[:GROUNDS_ENTITY]->(:SOPStep)` | Many-to-many | `claim_field: String` | `confidence_score: Float[0,1]` | Supports step-level answer grounding. |
| `(:TextChunk)-[:GROUNDS_ENTITY]->(:FailureMode)` | Many-to-many | `claim_field: String` | `confidence_score: Float[0,1]` | Supports failure-mode explanation grounding. |
| `(:TextChunk)-[:GROUNDS_ENTITY]->(:SafetyHazard)` | Many-to-many | `claim_field: String` | `confidence_score: Float[0,1]` | Supports safety statement citations. |

### 4.1 Mandatory relationship checklist

The prompt-mandated relationships are included exactly as canonical labels:

- `(:Asset)-[:COMPRISED_OF]->(:Component)`
- `(:Component)-[:MONITORED_BY]->(:Sensor)`
- `(:Sensor)-[:EXHIBITS_ANOMALY]->(:FailureMode)`
- `(:FailureMode)-[:TRIGGERED_BY]->(:RootCause)`
- `(:FailureMode)-[:MITIGATED_BY]->(:SOP)`
- `(:SOP)-[:REQUIRES_TOOL]->(:Tooling)`

---

## 5. Downstream alignment and integration readiness

### 5.1 GraphRAG mapping

| GraphRAG contract field | Ontology mapping | Rule |
|---|---|---|
| `GraphNode.id` | Any entity `id` | Must be canonical ID from §1.3 |
| `GraphNode.label` | Node label enum | Must be one of `GraphNodeLabel` |
| `GraphNode.display_name` | `SemanticEntity.display_name` | Required for graph renderer |
| `GraphNode.properties` | Entity-specific public fields | Should exclude sensitive metadata |
| `GraphEdge.relationship` | `GraphRelationshipType` | Canonical Phase 1 labels preferred |
| `VectorContextChunk.chunk_id` | `TextChunk.chunk_id` | Must match Qdrant point ID |
| `VectorContextChunk.source_document` | `SourceDocument.source_document` | Source filename or enterprise doc ID |
| `VectorContextChunk.source_type` | `SourceDocument.source_type` | SOP, MANUAL, INCIDENT_REPORT, MAINTENANCE_LOG |
| `Citation.source_node_id` | `SOP.id`, `SOPStep.id`, `FailureMode.id`, `SafetyHazard.id`, etc. | Prefer most specific node that grounds the claim |
| `Citation.claim_span` | `CitationAnchor.claim_field` + source text | Claim must map to a grounded node field when possible |

**Citation grounding rule:** a generated answer should prefer citations linked through `(:TextChunk)-[:GROUNDS_ENTITY]->(:SOPStep)` for procedural instructions, `(:TextChunk)-[:GROUNDS_ENTITY]->(:SafetyHazard)` for safety statements, and `(:TextChunk)-[:GROUNDS_ENTITY]->(:FailureMode)` for diagnostic claims.

### 5.2 Predictive maintenance mapping

| Member 2 / PdM field | Ontology target | Rule |
|---|---|---|
| `TelemetryReading.asset_id` | `Asset.id` | Required; frame rejected or quarantined if unresolved in Phase 2 |
| `TelemetryReading.component_id` | `Component.id` | Optional in telemetry but required for component-scoped sensors |
| `SensorReading.sensor_id` | `Sensor.id` | Required for sensor-level anomaly linking |
| `SensorReading.metric` | `Sensor.metric` / `TelemetryStream.metric` | Exact string match required |
| `SensorReading.unit` | `Sensor.unit` / `TelemetryStream.unit` | Exact enum match required |
| `SensorReading.quality` | `Sensor.signal_quality_expected_min` | Quality below expected minimum may suppress inference |
| `FailureProbability.failure_mode_id` | `FailureMode.id` | Enables PdM response to link into GraphRAG failure/SOP graph |
| `AnomalyFlag.sensor_id` | `Sensor.id` | Allows anomaly flags to traverse to failure modes via `EXHIBITS_ANOMALY` |

### 5.3 Compatibility notes for Phase 0 relationship labels

Phase 0 examples used `HAS_COMPONENT`, `HAS_SENSOR`, and `INDICATES_FAILURE`. Phase 1 canonical labels are stricter:

| Phase 0 name | Phase 1 canonical name |
|---|---|
| `HAS_COMPONENT` | `COMPRISED_OF` |
| `HAS_SENSOR` | `MONITORED_BY` |
| `INDICATES_FAILURE` | `EXHIBITS_ANOMALY` |

`app/graph/schema.py` keeps alias names for backward-safe imports, but new graph data and documentation must use the Phase 1 canonical labels.

---

## 6. Phase 2 handoff checklist

Before implementing database population in Phase 2, confirm:

- [ ] Member 2 telemetry sensor IDs match planned `Sensor.id` values.
- [ ] Asset and component tag naming conventions are agreed with plant engineering.
- [ ] SOP document IDs and revision formats are finalized.
- [ ] Safety-critical SOPs have `SafetyHazard`, `OperatorRole`, and `Tooling` coverage.
- [ ] Failure modes have at least one mechanism and at least one mitigation SOP.
- [ ] Text chunk payloads can carry `chunk_id`, `source_document`, `source_type`, `page_number`, `asset_ids`, and `asset_types` as required by `docs/qdrant_schema.md`.
- [ ] No Cypher/ingestion/parser code is merged until this ontology is accepted.
