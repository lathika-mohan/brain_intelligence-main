// ===========================================================================
// Phase 2 — RANGE + TEXT indexes for fast GraphRAG retrieval
// ---------------------------------------------------------------------------
// Community + Enterprise safe. Backs filters, sorting, and substring search.
// Generated from app/graph/schema_migrations.py — edit the registry, not here.
// ===========================================================================

CREATE RANGE INDEX range_Asset_status IF NOT EXISTS FOR (n:`Asset`) ON (n.status);

CREATE RANGE INDEX range_Asset_criticality IF NOT EXISTS FOR (n:`Asset`) ON (n.criticality);

CREATE RANGE INDEX range_Asset_location_id IF NOT EXISTS FOR (n:`Asset`) ON (n.location_id);

CREATE RANGE INDEX range_Asset_asset_type IF NOT EXISTS FOR (n:`Asset`) ON (n.asset_type);

CREATE RANGE INDEX range_Asset_equipment_class IF NOT EXISTS FOR (n:`Asset`) ON (n.equipment_class);

CREATE RANGE INDEX range_Component_asset_id IF NOT EXISTS FOR (n:`Component`) ON (n.asset_id);

CREATE RANGE INDEX range_Component_component_type IF NOT EXISTS FOR (n:`Component`) ON (n.component_type);

CREATE RANGE INDEX range_Component_maintainable IF NOT EXISTS FOR (n:`Component`) ON (n.maintainable);

CREATE RANGE INDEX range_Sensor_asset_id IF NOT EXISTS FOR (n:`Sensor`) ON (n.asset_id);

CREATE RANGE INDEX range_Sensor_component_id IF NOT EXISTS FOR (n:`Sensor`) ON (n.component_id);

CREATE RANGE INDEX range_Sensor_sensor_category IF NOT EXISTS FOR (n:`Sensor`) ON (n.sensor_category);

CREATE RANGE INDEX range_Sensor_sampling_frequency_hz IF NOT EXISTS FOR (n:`Sensor`) ON (n.sampling_frequency_hz);

CREATE RANGE INDEX range_TelemetryStream_sensor_id IF NOT EXISTS FOR (n:`TelemetryStream`) ON (n.sensor_id);

CREATE RANGE INDEX range_FailureMode_equipment_class IF NOT EXISTS FOR (n:`FailureMode`) ON (n.equipment_class);

CREATE RANGE INDEX range_FailureMode_component_type IF NOT EXISTS FOR (n:`FailureMode`) ON (n.component_type);

CREATE RANGE INDEX range_FailureMode_severity_tier IF NOT EXISTS FOR (n:`FailureMode`) ON (n.severity_tier);

CREATE RANGE INDEX range_MaintenanceTask_asset_id IF NOT EXISTS FOR (n:`MaintenanceTask`) ON (n.asset_id);

CREATE RANGE INDEX range_MaintenanceTask_component_id IF NOT EXISTS FOR (n:`MaintenanceTask`) ON (n.component_id);

CREATE RANGE INDEX range_MaintenanceTask_priority IF NOT EXISTS FOR (n:`MaintenanceTask`) ON (n.priority);

CREATE RANGE INDEX range_SOP_status IF NOT EXISTS FOR (n:`SOP`) ON (n.status);

CREATE RANGE INDEX range_SOP_safety_critical IF NOT EXISTS FOR (n:`SOP`) ON (n.safety_critical);

CREATE RANGE INDEX range_RootCause_category IF NOT EXISTS FOR (n:`RootCause`) ON (n.category);

CREATE RANGE INDEX range_SafetyHazard_risk_level IF NOT EXISTS FOR (n:`SafetyHazard`) ON (n.risk_level);

CREATE RANGE INDEX range_OperatorRole_role_code IF NOT EXISTS FOR (n:`OperatorRole`) ON (n.role_code);

CREATE RANGE INDEX range_TextChunk_source_document_id IF NOT EXISTS FOR (n:`TextChunk`) ON (n.source_document_id);

CREATE RANGE INDEX range_TextChunk_source_type IF NOT EXISTS FOR (n:`TextChunk`) ON (n.source_type);

CREATE TEXT INDEX text_Location_display_name IF NOT EXISTS FOR (n:`Location`) ON (n.display_name);

CREATE TEXT INDEX text_Location_site_code IF NOT EXISTS FOR (n:`Location`) ON (n.site_code);

CREATE TEXT INDEX text_Asset_display_name IF NOT EXISTS FOR (n:`Asset`) ON (n.display_name);

CREATE TEXT INDEX text_Asset_tag IF NOT EXISTS FOR (n:`Asset`) ON (n.tag);

CREATE TEXT INDEX text_Asset_process_function IF NOT EXISTS FOR (n:`Asset`) ON (n.process_function);

CREATE TEXT INDEX text_Component_display_name IF NOT EXISTS FOR (n:`Component`) ON (n.display_name);

CREATE TEXT INDEX text_Component_component_position IF NOT EXISTS FOR (n:`Component`) ON (n.component_position);

CREATE TEXT INDEX text_Sensor_display_name IF NOT EXISTS FOR (n:`Sensor`) ON (n.display_name);

CREATE TEXT INDEX text_Sensor_tag IF NOT EXISTS FOR (n:`Sensor`) ON (n.tag);

CREATE TEXT INDEX text_Sensor_metric IF NOT EXISTS FOR (n:`Sensor`) ON (n.metric);

CREATE TEXT INDEX text_FailureMode_display_name IF NOT EXISTS FOR (n:`FailureMode`) ON (n.display_name);

CREATE TEXT INDEX text_FailureMode_failure_effect IF NOT EXISTS FOR (n:`FailureMode`) ON (n.failure_effect);

CREATE TEXT INDEX text_FailureMode_iso_14224_code IF NOT EXISTS FOR (n:`FailureMode`) ON (n.iso_14224_code);

CREATE TEXT INDEX text_RootCause_causal_statement IF NOT EXISTS FOR (n:`RootCause`) ON (n.causal_statement);

CREATE TEXT INDEX text_FailureSymptom_observed_signal IF NOT EXISTS FOR (n:`FailureSymptom`) ON (n.observed_signal);

CREATE TEXT INDEX text_SOP_title IF NOT EXISTS FOR (n:`SOP`) ON (n.title);

CREATE TEXT INDEX text_SOP_sop_number IF NOT EXISTS FOR (n:`SOP`) ON (n.sop_number);

CREATE TEXT INDEX text_SOPStep_instruction IF NOT EXISTS FOR (n:`SOPStep`) ON (n.instruction);

CREATE TEXT INDEX text_SafetyHazard_hazard_statement IF NOT EXISTS FOR (n:`SafetyHazard`) ON (n.hazard_statement);

CREATE TEXT INDEX text_Tooling_tool_type IF NOT EXISTS FOR (n:`Tooling`) ON (n.tool_type);

CREATE TEXT INDEX text_OperatorRole_role_code IF NOT EXISTS FOR (n:`OperatorRole`) ON (n.role_code);

CREATE TEXT INDEX text_SourceDocument_source_document IF NOT EXISTS FOR (n:`SourceDocument`) ON (n.source_document);

CREATE TEXT INDEX text_TextChunk_text IF NOT EXISTS FOR (n:`TextChunk`) ON (n.text);
