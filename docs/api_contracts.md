# AI Platform API Contracts (Phase 0 — FROZEN)

Base path: `{API_V1_PREFIX}` = `/api/v1` (see `.env.example`).
Interactive schema always available at `GET /docs` (Swagger) and `GET /redoc`
once the service is running — treat this document as the human-readable
mirror of that OpenAPI schema, not a replacement for it.

Every response body is wrapped in the shared envelope:

```json
{
  "success": true,
  "data": { /* endpoint-specific payload */ },
  "error": null,
  "request_id": "uuid",
  "generated_at": "2026-07-02T12:00:00Z"
}
```

This matches the frontend's existing `APIResponse<T>` TypeScript contract
(`src/types/index.ts`, Section 11) verbatim.

---

## 1. `POST /api/v1/graphrag/query` → powers `GraphRagPanel.tsx`

**Request** (`GraphRagQueryRequest`):
```json
{
  "query": "Why is Pump-101 overheating?",
  "asset_ids": ["asset-101"],
  "asset_types": ["PUMP"],
  "time_bounds": { "start": "2026-06-01T00:00:00Z", "end": "2026-07-01T00:00:00Z" },
  "traversal_depth": 2,
  "top_k_vector": 8,
  "min_confidence": 0.5,
  "include_graph_context": true,
  "include_citations": true
}
```

**Response** (`data: GraphRagQueryResponse`):
```json
{
  "query": "...",
  "answer": "Synthesized natural-language answer.",
  "vector_context": [ { "chunk_id": "...", "text": "...", "source_document": "...", "source_type": "SOP", "confidence_score": 0.82, "page_number": 3 } ],
  "graph_context": { "nodes": [...], "edges": [...], "root_node_ids": ["..."] },
  "citations": [ { "citation_id": "...", "claim_span": "...", "source_document": "...", "source_type": "SOP", "source_node_id": "...", "confidence_score": 0.82 } ],
  "overall_confidence": 0.82,
  "latency_ms": 143.2,
  "generated_at": "..."
}
```

---

## 2. `POST /api/v1/predictive/infer` → powers `DigitalTwinView.tsx`

**Request** (`InferenceRequest`) wraps one or more `TelemetryReading`
frames (the frozen upstream contract from Member 2 — see §5).

**Response** (`data: InferenceResponse`):
```json
{
  "asset_id": "asset-101",
  "component_id": "component-55",
  "rul": { "value_days": 42.5, "lower_bound_days": 30.0, "upper_bound_days": 55.0, "confidence_level": 0.9, "model_name": "xgboost_rul_v1", "model_version": "1.0.0" },
  "failure_probability": {
    "probability": 0.23,
    "predicted_window": { "earliest": "...", "latest": "...", "most_likely": "..." },
    "failure_mode_id": "failuremode-stub-1",
    "failure_mode_label": "Bearing Overheat",
    "model_name": "xgboost_failure_classifier_v1",
    "model_version": "1.0.0"
  },
  "anomaly_flags": [ { "sensor_id": "...", "metric": "bearing_temp", "anomaly_score": -0.12, "is_anomalous": false, "severity": "LOW", "detected_at": "..." } ],
  "explanation_id": "uuid-linkable-to-/xai/explain",
  "inference_latency_ms": 12.4,
  "generated_at": "...",
  "fallback_used": false
}
```

---

## 3. `POST /api/v1/xai/explain` → powers `ShapExplainability.tsx`

**Request** (`ExplanationRequest`):
```json
{ "asset_id": "asset-101", "explanation_id": null, "method": "SHAP", "scope": "LOCAL", "target_model_name": "xgboost_failure_classifier_v1" }
```

**Response** (`data: ExplanationResponse`):
```json
{
  "explanation_id": "...",
  "asset_id": "asset-101",
  "method": "SHAP",
  "scope": "LOCAL",
  "base_value": 0.15,
  "predicted_value": 0.23,
  "global_feature_importance": null,
  "local_feature_importance": [ { "feature_name": "bearing_temp_c", "impact_weight": 0.34, "feature_value": 78.2, "rank": 1 } ],
  "root_cause": { "headline": "...", "narrative": "...", "contributing_failure_modes": ["failuremode-stub-1"] },
  "confidence_matrix": [ { "label": "Bearing Overheat", "confidence": 0.82 } ],
  "model_name": "xgboost_failure_classifier_v1",
  "model_version": "1.0.0",
  "generated_at": "..."
}
```

---

## 4. `POST /api/v1/decision/recommend` → Decision Engine

**Request** (`RecommendationRequest`):
```json
{ "asset_id": "asset-101", "component_id": "component-55", "risk_horizon_days": 30, "max_recommendations": 5 }
```

**Response** (`data: RecommendationResponse`):
```json
{
  "asset_id": "asset-101",
  "component_id": "component-55",
  "recommendations": [
    {
      "action_id": "...",
      "action_type": "LUBRICATE",
      "description": "Reduce bearing lubrication interval to 14 days per SOP-114.",
      "priority": "HIGH",
      "risk_score_if_ignored": 0.68,
      "estimated_cost_avoidance_usd": 15000.0,
      "recommended_completion_by": "...",
      "sop_linkage": { "sop_id": "sop-stub-1", "title": "SOP-114: Bearing Lubrication & Maintenance", "document_url": "...", "revision": "Rev. C" },
      "supporting_explanation_id": null
    }
  ],
  "overall_risk_score": 0.68,
  "generated_at": "..."
}
```

---

## 5. `POST /api/v1/ingestion/telemetry` → CONSUMES Member 2's contract

**Request** (`TelemetryBatch`):
```json
{
  "batch_id": "batch-0001",
  "produced_at": "...",
  "readings": [
    {
      "schema_version": "1.0.0",
      "asset_id": "asset-101",
      "component_id": "component-55",
      "timestamp": "...",
      "readings": [ { "sensor_id": "sensor-9", "metric": "bearing_temp", "value": 78.2, "unit": "C", "quality": 0.98 } ],
      "operating_mode": "RUNNING",
      "metadata": {}
    }
  ]
}
```

**Response**: `202 Accepted`, `data: { batch_id, accepted_readings, schema_version }`.

---

## 6. `GET /api/v1/health` and `GET /api/v1/health/ready`

Liveness / readiness probes for Member 1's enterprise gateway. Readiness
checks live Neo4j + Qdrant connectivity and returns `"degraded"` (still
HTTP 200) if either is down, so the gateway can make routing decisions
without receiving hard failures for partial degradation.
