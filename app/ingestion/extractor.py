"""
Phase 3 — LLM-Driven Information Extraction (Triple Generation)

Uses structured outputs (Pydantic) to enforce Phase 1 ontology.
Supports:
 - instructor / OpenAI function calling
 - native OpenAI / Anthropic JSON mode
 - deterministic mock extractor for CI / tests (no API key required)
"""

from __future__ import annotations

import os
import json
import logging
import datetime
from typing import Optional

from .schemas import (
    ExtractionResult,
    ExtractedEntity,
    ExtractedRelationship,
    ChunkMetadata,
)
from .prompts import (
    EXTRACTION_SYSTEM_PROMPT,
    build_extraction_user_prompt,
)
from .entity_resolver import deduplicate_entities

logger = logging.getLogger(__name__)

# Try to import optional LLM client libraries
try:
    import instructor  # type: ignore
    from openai import OpenAI  # type: ignore
    HAS_INSTRUCTOR = True
except Exception:
    HAS_INSTRUCTOR = False


class ExtractionEngine:
    """
    Deterministic LLM extraction engine.
    If OPENAI_API_KEY is set and instructor is available, uses real LLM.
    Otherwise falls back to deterministic mock (perfect for CI).
    """

    def __init__(
        self,
        *,
        model: str = "gpt-4o-mini",
        use_mock: Optional[bool] = None,
        temperature: float = 0.0,
    ):
        self.model = model
        self.temperature = temperature
        api_key = os.getenv("OPENAI_API_KEY") or os.getenv("LLM_API_KEY")
        if use_mock is None:
            use_mock = not (HAS_INSTRUCTOR and api_key)
        self.use_mock = use_mock
        self._client = None
        if not self.use_mock and HAS_INSTRUCTOR:
            try:
                self._client = instructor.from_openai(OpenAI(api_key=api_key))
            except Exception as e:
                logger.warning("LLM client init failed, falling back to mock: %s", e)
                self.use_mock = True

    def extract(self, chunk: ChunkMetadata, chunk_text: Optional[str] = None) -> ExtractionResult:
        text = chunk_text or chunk.parent_metadata.get("text", "")
        if not text:
            return ExtractionResult(
                chunk_id=chunk.chunk_id,
                document_id=chunk.document_id,
                entities=[],
                relationships=[],
                warnings=["empty_chunk_text"],
            )
        if self.use_mock:
            result = self._mock_extract(chunk, text)
        else:
            result = self._llm_extract(chunk, text)

        # entity resolution & deduplication
        result.entities = deduplicate_entities(result.entities)
        # validate
        errors = result.validate_ontology_constraints()
        if errors:
            result.warnings.extend(errors)
            logger.warning("Extraction ontology validation warnings: %s", errors)
        return result

    # --- Mock deterministic extractor (for tests / CI) ---
    def _mock_extract(self, chunk: ChunkMetadata, text: str) -> ExtractionResult:
        """
        Deterministic rule-based mock that recognizes Phase 1 industrial patterns.
        Perfectly reproducible, no network.
        """
        import re
        entities: list[ExtractedEntity] = []
        relationships: list[ExtractedRelationship] = []
        lt = text.lower()

        def add_entity(eid: str, label: str, name: str, **props):
            # avoid duplicates in this chunk
            if any(x.entity_id == eid for x in entities):
                return
            entities.append(ExtractedEntity(
                entity_id=eid,
                label=label,  # type: ignore
                display_name=name,
                confidence=0.92,
                chunk_id=chunk.chunk_id,
                source_span=text[:240],
                properties=props,
                aliases=[],
            ))

        # Asset detection
        if re.search(r"\bP-?101A\b|pump[ -]?a|centrifugal pump", lt):
            add_entity("asset:SRP:P-101A", "Asset", "Pump P-101A",
                       asset_type="PUMP", equipment_class="ROTARY_EQUIPMENT")
        # Component
        if "bearing" in lt:
            pos = "DE" if "drive" in lt or "de" in lt else "NDE" if "nde" in lt or "non-drive" in lt else "DE"
            add_entity(f"component:P-101A:BEARING:{pos}", "Component", "Drive-end bearing" if pos=="DE" else "Bearing",
                       component_type="BEARING")
        # Sensor
        if "te-101a" in lt or "temperature sensor" in lt or "rtd" in lt or "bearing_temp" in lt:
            add_entity("sensor:SRP:TE-101A-DE", "Sensor", "Drive-end bearing RTD",
                       sensor_category="THERMAL", metric="bearing_temp", unit="CELSIUS")
        if "vibration" in lt or "accelerometer" in lt or "ve-" in lt:
            add_entity("sensor:SRP:VE-101A-DE", "Sensor", "Drive-end vibration probe",
                       sensor_category="VIBRATION", metric="vibration_rms", unit="MM_S")
        # FailureMode
        if "overheat" in lt or "high temperature" in lt or "bearing_temp" in lt:
            add_entity("failuremode:ROTARY_EQUIPMENT:BEARING:overheat", "FailureMode", "Bearing overheat",
                       severity_tier="DEGRADED")
        if "imbalance" in lt or "vibration" in lt:
            # avoid duplicate if already added overheat; still allow
            if not any(e.entity_id == "failuremode:ROTARY_EQUIPMENT:BEARING:imbalance" for e in entities):
                if "imbalance" in lt:
                    add_entity("failuremode:ROTARY_EQUIPMENT:BEARING:imbalance", "FailureMode", "Bearing imbalance",
                               severity_tier="DEGRADED")
        # RootCause
        if "lubricat" in lt:
            add_entity("rootcause:MAINTENANCE:under_lubrication", "RootCause", "Under-lubrication")
        # SOP
        if "sop" in lt or "lubrication" in lt or "procedure" in lt:
            add_entity("sop:SOP-114:REV-C", "SOP", "SOP-114 Bearing Lubrication")
            # SOPStep if numbered steps detected
            if re.search(r"\bstep\s*1\b|1\.\s*isolate", lt):
                add_entity("sopstep:sop:SOP-114:REV-C:1", "SOPStep", "Isolate pump")
        # Tooling
        if "torque" in lt or "wrench" in lt or "tool" in lt:
            add_entity("tooling:TORQUE-WRENCH-50NM", "Tooling", "50 Nm torque wrench")

        # Build relationships if endpoints exist
        ent_map = {e.entity_id: e for e in entities}

        def relate(sid, slabel, rel, tid, tlabel, props=None):
            if sid in ent_map and tid in ent_map:
                relationships.append(ExtractedRelationship(
                    source_id=sid,
                    source_label=slabel,  # type: ignore
                    relationship=rel,  # type: ignore
                    target_id=tid,
                    target_label=tlabel,  # type: ignore
                    confidence=0.9,
                    properties=props or {},
                    chunk_id=chunk.chunk_id,
                    evidence_text=text[:200],
                ))

        relate("asset:SRP:P-101A", "Asset", "COMPRISED_OF",
               "component:P-101A:BEARING:DE", "Component")
        relate("component:P-101A:BEARING:DE", "Component", "MONITORED_BY",
               "sensor:SRP:TE-101A-DE", "Sensor")
        relate("component:P-101A:BEARING:DE", "Component", "MONITORED_BY",
               "sensor:SRP:VE-101A-DE", "Sensor")
        # EXHIBITS_ANOMALY requires metric + confidence_weight
        if "sensor:SRP:TE-101A-DE" in ent_map and "failuremode:ROTARY_EQUIPMENT:BEARING:overheat" in ent_map:
            relate("sensor:SRP:TE-101A-DE", "Sensor", "EXHIBITS_ANOMALY",
                   "failuremode:ROTARY_EQUIPMENT:BEARING:overheat", "FailureMode",
                   {"metric": "bearing_temp", "confidence_weight": 0.87})
        if "sensor:SRP:VE-101A-DE" in ent_map and "failuremode:ROTARY_EQUIPMENT:BEARING:imbalance" in ent_map:
            relate("sensor:SRP:VE-101A-DE", "Sensor", "EXHIBITS_ANOMALY",
                   "failuremode:ROTARY_EQUIPMENT:BEARING:imbalance", "FailureMode",
                   {"metric": "vibration_rms", "confidence_weight": 0.82})
        relate("failuremode:ROTARY_EQUIPMENT:BEARING:overheat", "FailureMode", "TRIGGERED_BY",
               "rootcause:MAINTENANCE:under_lubrication", "RootCause")
        relate("failuremode:ROTARY_EQUIPMENT:BEARING:overheat", "FailureMode", "MITIGATED_BY",
               "sop:SOP-114:REV-C", "SOP", {"effectiveness": 0.91})
        relate("sop:SOP-114:REV-C", "SOP", "REQUIRES_TOOL",
               "tooling:TORQUE-WRENCH-50NM", "Tooling", {"quantity": 1})
        relate("sop:SOP-114:REV-C", "SOP", "HAS_STEP",
               "sopstep:sop:SOP-114:REV-C:1", "SOPStep", {"sequence_number": 1})

        return ExtractionResult(
            chunk_id=chunk.chunk_id,
            document_id=chunk.document_id,
            entities=entities,
            relationships=relationships,
            extraction_model="phase3-mock-deterministic-v1",
            extraction_timestamp=datetime.datetime.utcnow().isoformat() + "Z",
            warnings=[] if entities else ["no_industrial_entities_detected"],
        )

    def _llm_extract(self, chunk: ChunkMetadata, text: str) -> ExtractionResult:
        """Real LLM path via instructor structured output."""
        if not self._client:
            return self._mock_extract(chunk, text)
        user_prompt = build_extraction_user_prompt(text, chunk.model_dump())
        try:
            # instructor provides response_model parsing
            resp: ExtractionResult = self._client.chat.completions.create(
                model=self.model,
                temperature=self.temperature,
                response_model=ExtractionResult,
                messages=[
                    {"role": "system", "content": EXTRACTION_SYSTEM_PROMPT},
                    {"role": "user", "content": user_prompt},
                ],
                max_retries=2,
            )
            # ensure chunk_id/document_id echo correctly
            resp.chunk_id = chunk.chunk_id
            resp.document_id = chunk.document_id
            return resp
        except Exception as e:
            logger.error("LLM extraction failed, falling back to mock: %s", e)
            fallback = self._mock_extract(chunk, text)
            fallback.warnings.append(f"llm_fallback: {e}")
            return fallback
