"""
Phase 3 — Production Prompt Templates (Industry 5.0 deterministic IE)

Injects Phase 1 Entity Dictionary + Relationship Catalogue as strict boundary constraints.
"""

from __future__ import annotations

ONTOLOGY_ENTITY_DICTIONARY = """
PHASE 1 INDUSTRIAL KNOWLEDGE ONTOLOGY — ENTITY BOUNDARY

Node Labels (PascalCase, singular):
- Asset: RotaryEquipment / StaticEquipment / ElectricalEquipment. id=`asset:<site_code>:<asset_tag>` e.g. asset:SRP:P-101A
- Component: Bearing, Seal, Impeller, Shaft, Coupling, Gearbox, MotorWinding, etc. id=`component:<asset_tag>:<component_type>:<position>`
- Sensor: VibrationSensor, ThermalSensor, PressureSensor, FlowSensor, SpeedSensor, ElectricalSensor. id=`sensor:<site_code>:<instrument_tag>`
- FailureMode: CRITICAL / DEGRADED / INCIPIENT. id=`failuremode:<equipment_class>:<component_type>:<slug>`
- RootCause: DESIGN, MANUFACTURING, INSTALLATION, OPERATIONAL, MAINTENANCE, ENVIRONMENTAL. id=`rootcause:<category>:<slug>`
- SOP: MaintenanceSOP / OperatingSOP / EmergencySOP. id=`sop:<sop_number>:<revision>`
- SOPStep: ordered workflow step. id=`sopstep:<sop_id>:<sequence_number>`
- Tooling: id=`tooling:<tool_code>`
- SafetyHazard, OperatorRole, MaintenanceTask, FailureSymptom, Location, TelemetryStream, SourceDocument, TextChunk

All nodes MUST include: id, display_name, ontology_version="1.0.0".
IDs MUST follow Phase 1 primary key strategy. Use uppercase enums.
"""

RELATIONSHIP_CATALOGUE = """
PHASE 1 RELATIONSHIP CATALOGUE — UPPERCASE_SNAKE_CASE ONLY

Mandatory extraction targets:
1. (Asset)-[:COMPRISED_OF]->(Component)
2. (Component)-[:MONITORED_BY]->(Sensor)
3. (Sensor)-[:EXHIBITS_ANOMALY]->(FailureMode)
   REQUIRED EDGE PROPS: metric: String, confidence_weight: Float[0,1]
4. (FailureMode)-[:TRIGGERED_BY]->(RootCause)
5. (FailureMode)-[:MITIGATED_BY]->(SOP)
6. (SOP)-[:REQUIRES_TOOL]->(Tooling)
7. (SOP)-[:HAS_STEP]->(SOPStep)
   REQUIRED EDGE PROP: sequence_number: Integer

Additional allowed:
- (Asset)-[:LOCATED_IN]->(Location)
- (FailureMode)-[:HAS_SYMPTOM]->(FailureSymptom)
- (SOPStep)-[:HAS_HAZARD]->(SafetyHazard)
- (SOPStep)-[:REQUIRES_ROLE]->(OperatorRole)
- (Sensor)-[:EMITS_STREAM]->(TelemetryStream)
- (MaintenanceTask)-[:EXECUTES_SOP]->(SOP)

AUDITABILITY:
- (TextChunk)-[:MENTIONS]->(Entity)
- (TextChunk)-[:GROUNDS_ENTITY]->(SOP | SOPStep | FailureMode | SafetyHazard)
  REQUIRED EDGE PROP: claim_field: String
"""

EXTRACTION_SYSTEM_PROMPT = f"""
You are Member 3 — AI & Knowledge Engineer, Industrial Operating Brain (Industry 5.0).
Task: Deterministic Information Extraction from technical manuals, SOPs, and asset specification sheets.

STRICT ONTOLOGY BOUNDARIES — DO NOT INVENT LABELS
{ONTOLOGY_ENTITY_DICTIONARY}

{RELATIONSHIP_CATALOGUE}

EXTRACTION RULES
1. Output ONLY entities that map to the Phase 1 labels above. No other node types.
2. entity_id MUST follow Phase 1 ID strategy exactly. If tag is "P-101A" and site "SRP": asset id = "asset:SRP:P-101A".
   - Component: "component:P-101A:BEARING:DE"
   - Sensor: "sensor:SRP:TE-101A-DE"
   - FailureMode: "failuremode:ROTARY_EQUIPMENT:BEARING:overheat"
   - RootCause: "rootcause:MAINTENANCE:under_lubrication"
   - SOP: "sop:SOP-114:REV-C"
   - SOPStep: "sopstep:sop:SOP-114:REV-C:1"
   - Tooling: "tooling:TORQUE-WRENCH-50NM"
3. Normalize variant surface forms:
   "Centrifugal Pump A", "Pump-A", "CP-A", "P-101A" => canonical "asset:SRP:P-101A", display_name "Pump P-101A"
4. Output triples ONLY as (Source) -> [RELATIONSHIP] -> (Target) using the catalogue above.
5. For EXHIBITS_ANOMALY edges include metric (e.g. "bearing_temp", "vibration_rms") and confidence_weight 0.0-1.0.
6. For HAS_STEP edges include sequence_number: int >=1.
7. Every entity must include confidence 0.0-1.0 and source_span quoted from input text.
8. Be conservative: if uncertain, omit rather than hallucinate. Warnings array must list low-confidence decisions.
9. Output STRICT JSON matching the provided Pydantic schema. No markdown, no prose.
10. Relationship strings MUST be UPPERCASE_SNAKE_CASE and present in the catalogue.
11. All IDs, enums, and units must be uppercase where the ontology specifies enums.
12. Traceability: copy chunk_id into each entity/relationship.

PRIORITY EXTRACTION TARGETS
- Components, sensors, failure modes, mitigation rules
- Asset/component hierarchy (COMPRISED_OF)
- Sensor monitoring links (MONITORED_BY)
- Anomaly → FailureMode (EXHIBITS_ANOMALY)
- FailureMode → RootCause (TRIGGERED_BY)
- FailureMode → SOP (MITIGATED_BY)
- SOP → Tooling (REQUIRES_TOOL)
- SOP → SOPStep (HAS_STEP)

Return a JSON object with keys: chunk_id, document_id, entities[], relationships[], extraction_model, warnings[].
"""

def build_extraction_user_prompt(chunk_text: str, chunk_meta: dict) -> str:
    """Deterministic user prompt injecting chunk + metadata."""
    meta_lines = [
        f"chunk_id: {chunk_meta.get('chunk_id')}",
        f"document_id: {chunk_meta.get('document_id')}",
        f"source_filename: {chunk_meta.get('source_filename')}",
        f"document_category: {chunk_meta.get('document_category')}",
        f"section_title: {chunk_meta.get('section_title', 'N/A')}",
        f"page_start: {chunk_meta.get('page_start', 'N/A')}",
        f"page_end: {chunk_meta.get('page_end', 'N/A')}",
        f"chunk_index: {chunk_meta.get('chunk_index')}",
    ]
    header = "\n".join(meta_lines)
    return f"""CHUNK METADATA
{header}

INDUSTRIAL TEXT TO EXTRACT (SOP / Manual / Spec Sheet)
---
{chunk_text}
---

Extract entities and relationships per Phase 1 ontology. Output structured JSON only.
If no relevant industrial entities are present, return empty entities[] and relationships[] with a warning.
"""


# Few-shot anchor examples (deterministic)
FEW_SHOT_EXAMPLES = [
    {
        "input_hint": "Centrifugal Pump P-101A drive-end bearing temperature sensor TE-101A-DE",
        "entities": [
            {"entity_id": "asset:SRP:P-101A", "label": "Asset", "display_name": "Pump P-101A", "asset_type": "PUMP", "equipment_class": "ROTARY_EQUIPMENT"},
            {"entity_id": "component:P-101A:BEARING:DE", "label": "Component", "display_name": "Drive-end bearing", "component_type": "BEARING"},
            {"entity_id": "sensor:SRP:TE-101A-DE", "label": "Sensor", "display_name": "Drive-end bearing RTD", "sensor_category": "THERMAL", "metric": "bearing_temp", "unit": "CELSIUS"}
        ],
        "relationships": [
            {"source_id": "asset:SRP:P-101A", "source_label": "Asset", "relationship": "COMPRISED_OF", "target_id": "component:P-101A:BEARING:DE", "target_label": "Component"},
            {"source_id": "component:P-101A:BEARING:DE", "source_label": "Component", "relationship": "MONITORED_BY", "target_id": "sensor:SRP:TE-101A-DE", "target_label": "Sensor"}
        ]
    }
]

ENTITY_RESOLUTION_INSTRUCTION = """
ENTITY RESOLUTION & STANDARDIZATION

Map variant text to single standardized node identity:
- "Centrifugal Pump A", "Pump-A", "CP-A", "P-101A" -> asset:SRP:P-101A
- "Drive End Bearing", "DE bearing", "bearing DE" -> component:P-101A:BEARING:DE
- "TE-101A-DE", "bearing temp sensor", "RTD DE" -> sensor:SRP:TE-101A-DE
- "bearing overheat", "overheating", "high bearing temp" -> failuremode:ROTARY_EQUIPMENT:BEARING:overheat
- "under lubrication", "lack of grease" -> rootcause:MAINTENANCE:under_lubrication

Rules:
1. Exact tag match wins (e.g., P-101A, TE-101A-DE).
2. Fuzzy match >=0.92 OR LLM-assisted alias confirmation required before merging.
3. Never merge across different equipment_class or component_type.
4. Preserve all observed aliases in the aliases[] array.
5. If ambiguous, create distinct nodes with warning "possible_duplicate: <ids>".
"""
