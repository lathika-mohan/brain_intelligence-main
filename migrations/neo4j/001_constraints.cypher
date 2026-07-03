// ===========================================================================
// Phase 2 — Uniqueness constraints (all 16 Phase 1 node labels)
// ---------------------------------------------------------------------------
// Community + Enterprise safe. Enforces the canonical graph key `id`.
// Generated from app/graph/schema_migrations.py — edit the registry, not here.
// ===========================================================================

CREATE CONSTRAINT un_Location_id IF NOT EXISTS FOR (n:`Location`) REQUIRE n.id IS UNIQUE;

CREATE CONSTRAINT un_Asset_id IF NOT EXISTS FOR (n:`Asset`) REQUIRE n.id IS UNIQUE;

CREATE CONSTRAINT un_Component_id IF NOT EXISTS FOR (n:`Component`) REQUIRE n.id IS UNIQUE;

CREATE CONSTRAINT un_Sensor_id IF NOT EXISTS FOR (n:`Sensor`) REQUIRE n.id IS UNIQUE;

CREATE CONSTRAINT un_TelemetryStream_id IF NOT EXISTS FOR (n:`TelemetryStream`) REQUIRE n.id IS UNIQUE;

CREATE CONSTRAINT un_FailureMode_id IF NOT EXISTS FOR (n:`FailureMode`) REQUIRE n.id IS UNIQUE;

CREATE CONSTRAINT un_RootCause_id IF NOT EXISTS FOR (n:`RootCause`) REQUIRE n.id IS UNIQUE;

CREATE CONSTRAINT un_FailureSymptom_id IF NOT EXISTS FOR (n:`FailureSymptom`) REQUIRE n.id IS UNIQUE;

CREATE CONSTRAINT un_MaintenanceTask_id IF NOT EXISTS FOR (n:`MaintenanceTask`) REQUIRE n.id IS UNIQUE;

CREATE CONSTRAINT un_SOP_id IF NOT EXISTS FOR (n:`SOP`) REQUIRE n.id IS UNIQUE;

CREATE CONSTRAINT un_SOPStep_id IF NOT EXISTS FOR (n:`SOPStep`) REQUIRE n.id IS UNIQUE;

CREATE CONSTRAINT un_SafetyHazard_id IF NOT EXISTS FOR (n:`SafetyHazard`) REQUIRE n.id IS UNIQUE;

CREATE CONSTRAINT un_Tooling_id IF NOT EXISTS FOR (n:`Tooling`) REQUIRE n.id IS UNIQUE;

CREATE CONSTRAINT un_OperatorRole_id IF NOT EXISTS FOR (n:`OperatorRole`) REQUIRE n.id IS UNIQUE;

CREATE CONSTRAINT un_SourceDocument_id IF NOT EXISTS FOR (n:`SourceDocument`) REQUIRE n.id IS UNIQUE;

CREATE CONSTRAINT un_TextChunk_id IF NOT EXISTS FOR (n:`TextChunk`) REQUIRE n.id IS UNIQUE;
