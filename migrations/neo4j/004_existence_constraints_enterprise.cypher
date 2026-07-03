// ===========================================================================
// Phase 2 — IS NOT NULL property-existence constraints
// ---------------------------------------------------------------------------
// ENTERPRISE EDITION ONLY. Community silently ignores these. The Python runner (apply_migrations) applies them conditionally based on dbms edition.
// Generated from app/graph/schema_migrations.py — edit the registry, not here.
// ===========================================================================

CREATE CONSTRAINT exists_Location_display_name IF NOT EXISTS FOR (n:`Location`) REQUIRE n.display_name IS NOT NULL;

CREATE CONSTRAINT exists_Location_location_type IF NOT EXISTS FOR (n:`Location`) REQUIRE n.location_type IS NOT NULL;

CREATE CONSTRAINT exists_Location_site_code IF NOT EXISTS FOR (n:`Location`) REQUIRE n.site_code IS NOT NULL;

CREATE CONSTRAINT exists_Asset_display_name IF NOT EXISTS FOR (n:`Asset`) REQUIRE n.display_name IS NOT NULL;

CREATE CONSTRAINT exists_Asset_asset_type IF NOT EXISTS FOR (n:`Asset`) REQUIRE n.asset_type IS NOT NULL;

CREATE CONSTRAINT exists_Asset_equipment_class IF NOT EXISTS FOR (n:`Asset`) REQUIRE n.equipment_class IS NOT NULL;

CREATE CONSTRAINT exists_Asset_tag IF NOT EXISTS FOR (n:`Asset`) REQUIRE n.tag IS NOT NULL;

CREATE CONSTRAINT exists_Asset_status IF NOT EXISTS FOR (n:`Asset`) REQUIRE n.status IS NOT NULL;

CREATE CONSTRAINT exists_Asset_criticality IF NOT EXISTS FOR (n:`Asset`) REQUIRE n.criticality IS NOT NULL;

CREATE CONSTRAINT exists_Asset_location_id IF NOT EXISTS FOR (n:`Asset`) REQUIRE n.location_id IS NOT NULL;

CREATE CONSTRAINT exists_Asset_process_function IF NOT EXISTS FOR (n:`Asset`) REQUIRE n.process_function IS NOT NULL;

CREATE CONSTRAINT exists_Component_display_name IF NOT EXISTS FOR (n:`Component`) REQUIRE n.display_name IS NOT NULL;

CREATE CONSTRAINT exists_Component_asset_id IF NOT EXISTS FOR (n:`Component`) REQUIRE n.asset_id IS NOT NULL;

CREATE CONSTRAINT exists_Component_component_type IF NOT EXISTS FOR (n:`Component`) REQUIRE n.component_type IS NOT NULL;

CREATE CONSTRAINT exists_Component_criticality IF NOT EXISTS FOR (n:`Component`) REQUIRE n.criticality IS NOT NULL;

CREATE CONSTRAINT exists_Sensor_display_name IF NOT EXISTS FOR (n:`Sensor`) REQUIRE n.display_name IS NOT NULL;

CREATE CONSTRAINT exists_Sensor_sensor_category IF NOT EXISTS FOR (n:`Sensor`) REQUIRE n.sensor_category IS NOT NULL;

CREATE CONSTRAINT exists_Sensor_metric IF NOT EXISTS FOR (n:`Sensor`) REQUIRE n.metric IS NOT NULL;

CREATE CONSTRAINT exists_Sensor_unit IF NOT EXISTS FOR (n:`Sensor`) REQUIRE n.unit IS NOT NULL;

CREATE CONSTRAINT exists_Sensor_asset_id IF NOT EXISTS FOR (n:`Sensor`) REQUIRE n.asset_id IS NOT NULL;

CREATE CONSTRAINT exists_Sensor_tag IF NOT EXISTS FOR (n:`Sensor`) REQUIRE n.tag IS NOT NULL;

CREATE CONSTRAINT exists_Sensor_sampling_method IF NOT EXISTS FOR (n:`Sensor`) REQUIRE n.sampling_method IS NOT NULL;

CREATE CONSTRAINT exists_Sensor_sampling_frequency_hz IF NOT EXISTS FOR (n:`Sensor`) REQUIRE n.sampling_frequency_hz IS NOT NULL;

CREATE CONSTRAINT exists_TelemetryStream_display_name IF NOT EXISTS FOR (n:`TelemetryStream`) REQUIRE n.display_name IS NOT NULL;

CREATE CONSTRAINT exists_TelemetryStream_sensor_id IF NOT EXISTS FOR (n:`TelemetryStream`) REQUIRE n.sensor_id IS NOT NULL;

CREATE CONSTRAINT exists_TelemetryStream_asset_id IF NOT EXISTS FOR (n:`TelemetryStream`) REQUIRE n.asset_id IS NOT NULL;

CREATE CONSTRAINT exists_TelemetryStream_metric IF NOT EXISTS FOR (n:`TelemetryStream`) REQUIRE n.metric IS NOT NULL;

CREATE CONSTRAINT exists_TelemetryStream_unit IF NOT EXISTS FOR (n:`TelemetryStream`) REQUIRE n.unit IS NOT NULL;

CREATE CONSTRAINT exists_FailureMode_display_name IF NOT EXISTS FOR (n:`FailureMode`) REQUIRE n.display_name IS NOT NULL;

CREATE CONSTRAINT exists_FailureMode_equipment_class IF NOT EXISTS FOR (n:`FailureMode`) REQUIRE n.equipment_class IS NOT NULL;

CREATE CONSTRAINT exists_FailureMode_severity_tier IF NOT EXISTS FOR (n:`FailureMode`) REQUIRE n.severity_tier IS NOT NULL;

CREATE CONSTRAINT exists_FailureMode_mechanisms IF NOT EXISTS FOR (n:`FailureMode`) REQUIRE n.mechanisms IS NOT NULL;

CREATE CONSTRAINT exists_RootCause_display_name IF NOT EXISTS FOR (n:`RootCause`) REQUIRE n.display_name IS NOT NULL;

CREATE CONSTRAINT exists_RootCause_category IF NOT EXISTS FOR (n:`RootCause`) REQUIRE n.category IS NOT NULL;

CREATE CONSTRAINT exists_RootCause_causal_statement IF NOT EXISTS FOR (n:`RootCause`) REQUIRE n.causal_statement IS NOT NULL;

CREATE CONSTRAINT exists_FailureSymptom_display_name IF NOT EXISTS FOR (n:`FailureSymptom`) REQUIRE n.display_name IS NOT NULL;

CREATE CONSTRAINT exists_FailureSymptom_observed_signal IF NOT EXISTS FOR (n:`FailureSymptom`) REQUIRE n.observed_signal IS NOT NULL;

CREATE CONSTRAINT exists_MaintenanceTask_display_name IF NOT EXISTS FOR (n:`MaintenanceTask`) REQUIRE n.display_name IS NOT NULL;

CREATE CONSTRAINT exists_MaintenanceTask_task_type IF NOT EXISTS FOR (n:`MaintenanceTask`) REQUIRE n.task_type IS NOT NULL;

CREATE CONSTRAINT exists_MaintenanceTask_asset_id IF NOT EXISTS FOR (n:`MaintenanceTask`) REQUIRE n.asset_id IS NOT NULL;

CREATE CONSTRAINT exists_MaintenanceTask_priority IF NOT EXISTS FOR (n:`MaintenanceTask`) REQUIRE n.priority IS NOT NULL;

CREATE CONSTRAINT exists_SOP_display_name IF NOT EXISTS FOR (n:`SOP`) REQUIRE n.display_name IS NOT NULL;

CREATE CONSTRAINT exists_SOP_sop_number IF NOT EXISTS FOR (n:`SOP`) REQUIRE n.sop_number IS NOT NULL;

CREATE CONSTRAINT exists_SOP_title IF NOT EXISTS FOR (n:`SOP`) REQUIRE n.title IS NOT NULL;

CREATE CONSTRAINT exists_SOP_revision IF NOT EXISTS FOR (n:`SOP`) REQUIRE n.revision IS NOT NULL;

CREATE CONSTRAINT exists_SOP_status IF NOT EXISTS FOR (n:`SOP`) REQUIRE n.status IS NOT NULL;

CREATE CONSTRAINT exists_SOPStep_display_name IF NOT EXISTS FOR (n:`SOPStep`) REQUIRE n.display_name IS NOT NULL;

CREATE CONSTRAINT exists_SOPStep_sop_id IF NOT EXISTS FOR (n:`SOPStep`) REQUIRE n.sop_id IS NOT NULL;

CREATE CONSTRAINT exists_SOPStep_sequence_number IF NOT EXISTS FOR (n:`SOPStep`) REQUIRE n.sequence_number IS NOT NULL;

CREATE CONSTRAINT exists_SOPStep_step_type IF NOT EXISTS FOR (n:`SOPStep`) REQUIRE n.step_type IS NOT NULL;

CREATE CONSTRAINT exists_SOPStep_instruction IF NOT EXISTS FOR (n:`SOPStep`) REQUIRE n.instruction IS NOT NULL;

CREATE CONSTRAINT exists_SafetyHazard_display_name IF NOT EXISTS FOR (n:`SafetyHazard`) REQUIRE n.display_name IS NOT NULL;

CREATE CONSTRAINT exists_SafetyHazard_category IF NOT EXISTS FOR (n:`SafetyHazard`) REQUIRE n.category IS NOT NULL;

CREATE CONSTRAINT exists_SafetyHazard_risk_level IF NOT EXISTS FOR (n:`SafetyHazard`) REQUIRE n.risk_level IS NOT NULL;

CREATE CONSTRAINT exists_SafetyHazard_hazard_statement IF NOT EXISTS FOR (n:`SafetyHazard`) REQUIRE n.hazard_statement IS NOT NULL;

CREATE CONSTRAINT exists_Tooling_display_name IF NOT EXISTS FOR (n:`Tooling`) REQUIRE n.display_name IS NOT NULL;

CREATE CONSTRAINT exists_Tooling_tool_type IF NOT EXISTS FOR (n:`Tooling`) REQUIRE n.tool_type IS NOT NULL;

CREATE CONSTRAINT exists_Tooling_calibrated IF NOT EXISTS FOR (n:`Tooling`) REQUIRE n.calibrated IS NOT NULL;

CREATE CONSTRAINT exists_OperatorRole_display_name IF NOT EXISTS FOR (n:`OperatorRole`) REQUIRE n.display_name IS NOT NULL;

CREATE CONSTRAINT exists_OperatorRole_role_code IF NOT EXISTS FOR (n:`OperatorRole`) REQUIRE n.role_code IS NOT NULL;

CREATE CONSTRAINT exists_OperatorRole_permissions IF NOT EXISTS FOR (n:`OperatorRole`) REQUIRE n.permissions IS NOT NULL;

CREATE CONSTRAINT exists_SourceDocument_display_name IF NOT EXISTS FOR (n:`SourceDocument`) REQUIRE n.display_name IS NOT NULL;

CREATE CONSTRAINT exists_SourceDocument_source_type IF NOT EXISTS FOR (n:`SourceDocument`) REQUIRE n.source_type IS NOT NULL;

CREATE CONSTRAINT exists_SourceDocument_source_document IF NOT EXISTS FOR (n:`SourceDocument`) REQUIRE n.source_document IS NOT NULL;

CREATE CONSTRAINT exists_TextChunk_display_name IF NOT EXISTS FOR (n:`TextChunk`) REQUIRE n.display_name IS NOT NULL;

CREATE CONSTRAINT exists_TextChunk_chunk_id IF NOT EXISTS FOR (n:`TextChunk`) REQUIRE n.chunk_id IS NOT NULL;

CREATE CONSTRAINT exists_TextChunk_source_document_id IF NOT EXISTS FOR (n:`TextChunk`) REQUIRE n.source_document_id IS NOT NULL;

CREATE CONSTRAINT exists_TextChunk_source_document IF NOT EXISTS FOR (n:`TextChunk`) REQUIRE n.source_document IS NOT NULL;

CREATE CONSTRAINT exists_TextChunk_source_type IF NOT EXISTS FOR (n:`TextChunk`) REQUIRE n.source_type IS NOT NULL;

CREATE CONSTRAINT exists_TextChunk_text IF NOT EXISTS FOR (n:`TextChunk`) REQUIRE n.text IS NOT NULL;
