# Neo4j Graph Schema Specification (Phase 0)

Status: **FROZEN** for Phase 0. Any change requires sign-off from Member 3 (owner)
and notification to Member 1 (Platform Backend) + Member 4 (Frontend), since
`GraphContextMap` (in `app/models/graphrag.py`) serializes these node/edge
shapes directly to the frontend's `GraphRagPanel.tsx`.

Corresponding code constants: `app/graph/schema.py`.
Bootstrap script: `scripts/init_neo4j_constraints.py`.

---

## 1. Node Labels

### `:Asset`
Physical or logical industrial equipment (pump, motor, compressor, etc.).

| Property      | Type      | Required | Notes                                             |
|---------------|-----------|----------|----------------------------------------------------|
| `id`          | string    | ✅ unique | Primary key. Matches frontend `Asset.id`.          |
| `name`        | string    | ✅        | Human-readable name.                               |
| `type`        | string    | ✅        | One of `AssetType` enum (`app.models.common`).     |
| `status`      | string    | ✅        | `OPERATIONAL`\|`DEGRADED`\|`CRITICAL`\|`OFFLINE`.  |
| `parent_id`   | string    | optional | Self-referential hierarchy pointer.                |
| `location`    | string    | optional | Plant/zone identifier.                             |
| `installed_at`| datetime  | optional | ISO-8601.                                          |

### `:Component`
A sub-assembly of an `:Asset` (e.g. a bearing, impeller, coupling).

| Property     | Type   | Required | Notes                          |
|--------------|--------|----------|----------------------------------|
| `id`         | string | ✅ unique | Primary key.                    |
| `name`       | string | ✅        | e.g. "Drive-End Bearing".       |
| `asset_id`   | string | ✅        | Denormalized FK to `:Asset.id`. |
| `component_type` | string | optional | e.g. "BEARING", "IMPELLER". |

### `:Sensor`
A physical sensor attached to a `:Component`.

| Property       | Type   | Required | Notes                                   |
|----------------|--------|----------|-------------------------------------------|
| `id`           | string | ✅ unique | Matches `TelemetryReading.SensorReading.sensor_id`. |
| `metric`       | string | ✅        | e.g. "vibration_x", "bearing_temp".      |
| `unit`         | string | ✅        | One of `SensorUnit` enum.                |
| `component_id` | string | ✅        | Denormalized FK to `:Component.id`.      |

### `:FailureMode`
A named degradation/failure mechanism.

| Property      | Type   | Required | Notes                                   |
|---------------|--------|----------|--------------------------------------------|
| `id`          | string | ✅ unique | Primary key.                               |
| `label`       | string | ✅        | e.g. "Bearing Overheat", "Cavitation".    |
| `description` | string | optional | Free text.                                 |
| `severity_class` | string | optional | e.g. "CRITICAL".                       |

### `:SOP`
A Standard Operating Procedure / maintenance manual document node.

| Property        | Type   | Required | Notes                                |
|-----------------|--------|----------|-----------------------------------------|
| `id`            | string | ✅ unique | Primary key.                            |
| `title`         | string | ✅        | Document title.                         |
| `document_url`  | string | optional | Link to source PDF/manual.              |
| `revision`      | string | optional | e.g. "Rev. C".                          |

---

## 2. Relationship Types (directional)

| Relationship          | From          | To            | Notes                                            |
|------------------------|---------------|---------------|---------------------------------------------------|
| `:HAS_COMPONENT`       | `:Asset`      | `:Component`  | Asset composition.                                |
| `:HAS_SENSOR`          | `:Component`  | `:Sensor`     | Sensor attachment.                                |
| `:INDICATES_FAILURE`   | `:Sensor`     | `:FailureMode`| Signal-to-failure-mode correlation (weighted).    |
| `:MITIGATED_BY`        | `:FailureMode`| `:SOP`        | Governing procedure for a failure mode.           |
| `:PART_OF`             | `:Component`  | `:Asset`      | Convenience inverse of `HAS_COMPONENT`.           |
| `:DEPENDS_ON`          | `:Asset`      | `:Asset`      | Upstream/downstream process dependency.           |

Relationship properties (all optional unless noted):

- `:INDICATES_FAILURE.weight` (float, 0.0–1.0) — correlation strength, used by GraphRAG traversal ranking.
- `:MITIGATED_BY.effectiveness` (float, 0.0–1.0) — historical mitigation effectiveness.

---

## 3. Constraints & Indexes (applied by `scripts/init_neo4j_constraints.py`)

```cypher
CREATE CONSTRAINT asset_id_unique IF NOT EXISTS FOR (a:Asset) REQUIRE a.id IS UNIQUE;
CREATE CONSTRAINT component_id_unique IF NOT EXISTS FOR (c:Component) REQUIRE c.id IS UNIQUE;
CREATE CONSTRAINT sensor_id_unique IF NOT EXISTS FOR (s:Sensor) REQUIRE s.id IS UNIQUE;
CREATE CONSTRAINT failuremode_id_unique IF NOT EXISTS FOR (f:FailureMode) REQUIRE f.id IS UNIQUE;
CREATE CONSTRAINT sop_id_unique IF NOT EXISTS FOR (s:SOP) REQUIRE s.id IS UNIQUE;

CREATE INDEX asset_status_idx IF NOT EXISTS FOR (a:Asset) ON (a.status);
CREATE INDEX asset_type_idx IF NOT EXISTS FOR (a:Asset) ON (a.type);
```

---

## 4. Frontend Fusion Mapping

`GraphContextMap` (returned by `POST /api/v1/graphrag/query`) serializes
Neo4j nodes/edges as:

```json
{
  "nodes": [{ "id": "...", "label": "Asset", "display_name": "Pump-101", "properties": {} }],
  "edges": [{ "source_id": "...", "target_id": "...", "relationship": "INDICATES_FAILURE", "properties": {} }],
  "root_node_ids": ["..."]
}
```

`label` always equals one of the five `NodeLabel` values above so
`GraphRagPanel.tsx` can apply consistent per-label styling/icons.
