"""
Pydantic v2 schema layer for the IOB AI Intelligence Platform.

Every request/response contract exposed over the FastAPI boundary is
frozen here. These schemas are the single source of truth for Member 4
(Frontend) and Member 1 (Platform Backend) integrations during Phase 0.

Modules
-------
common          Shared envelopes, enums, and primitives used across all
                subsystems (mirrors `src/types/index.ts` Section 11 shapes
                on the frontend where applicable).
telemetry       Upstream ingestion contract (Member 2 / PLC-SCADA).
graphrag        GraphRAG Engine request/response contracts.
predictive      Predictive Maintenance (RUL / failure / anomaly) contracts.
xai             Explainable AI (SHAP/LIME) contracts.
decision        Prescriptive Decision Engine contracts.
"""
