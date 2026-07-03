"""
Phase 3 — Idempotent Graph Loading & Validation

Transactional pipeline execution into Neo4j using Phase 2 MERGE patterns.
Stores :TextChunk nodes and [:MENTIONS] / [:GROUNDS_ENTITY] audit edges.
"""

from __future__ import annotations

import logging
from typing import List, Optional, Any

from .schemas import (
    ExtractedEntity,
    ExtractedRelationship,
    ChunkMetadata,
    GraphLoadBatch,
)

logger = logging.getLogger(__name__)

# Import Phase 2 repository
try:
    from app.graph.graph_repository import Neo4jGraphRepository, to_graph_props
except Exception as e:
    Neo4jGraphRepository = None  # type: ignore
    to_graph_props = lambda x: x
    logger.warning("Graph repository import failed (ok for unit tests): %s", e)


# Map extraction label -> Neo4j label (mostly 1:1)
LABEL_MAP = {
    "Asset": "Asset",
    "Component": "Component",
    "Sensor": "Sensor",
    "FailureMode": "FailureMode",
    "RootCause": "RootCause",
    "SOP": "SOP",
    "SOPStep": "SOPStep",
    "Tooling": "Tooling",
    "SafetyHazard": "SafetyHazard",
    "Location": "Location",
    "MaintenanceTask": "MaintenanceTask",
    "FailureSymptom": "FailureSymptom",
    "OperatorRole": "OperatorRole",
    "TelemetryStream": "TelemetryStream",
    "TextChunk": "TextChunk",
}


class GraphLoader:
    """
    Idempotent loader wrapping Neo4jGraphRepository.
    """

    def __init__(self, repository: Optional[Any] = None):
        self.repo = repository
        # counters for reporting
        self.nodes_upserted = 0
        self.relationships_created = 0
        self.chunks_stored = 0

    async def upsert_entity(self, entity: ExtractedEntity) -> dict:
        if not self.repo:
            # dry-run mode
            self.nodes_upserted += 1
            return {"id": entity.entity_id, "dry_run": True}
        label = LABEL_MAP.get(entity.label.value if hasattr(entity.label, "value") else str(entity.label), str(entity.label))
        props = {
            "display_name": entity.display_name,
            "confidence": entity.confidence,
            "ontology_version": "1.0.0",
            "aliases": entity.aliases,
            "source_span": entity.source_span,
            "chunk_id": entity.chunk_id,
        }
        # flatten known typed properties
        for k in ("asset_type", "equipment_class", "component_type", "sensor_category", "metric", "unit", "severity_tier"):
            v = getattr(entity, k, None)
            if v:
                props[k] = v
        # merge free-form properties
        props.update(entity.properties or {})
        # clean None
        props = {k: v for k, v in props.items() if v is not None}
        result = await self.repo.upsert_node(label, entity.entity_id, props)
        self.nodes_upserted += 1
        return result

    async def store_chunk_node(self, chunk: ChunkMetadata, text: Optional[str] = None) -> dict:
        """Store :TextChunk node per Phase 1 ontology."""
        if not self.repo:
            self.chunks_stored += 1
            return {"id": chunk.chunk_id, "dry_run": True}
        props = {
            "chunk_id": chunk.chunk_id,
            "source_document_id": chunk.document_id,
            "source_document": chunk.source_filename,
            "source_type": chunk.document_category,
            "text": text or chunk.parent_metadata.get("text", "")[:8000],  # truncate for graph storage
            "page_number": chunk.page_start,
            "section_heading": chunk.section_title,
            "asset_ids": [],
            "asset_types": [],
            "token_count": chunk.token_count,
            "char_count": chunk.char_count,
            "chunk_index": chunk.chunk_index,
            "hash": chunk.hash,
            "display_name": f"Chunk {chunk.chunk_index} — {chunk.source_filename}",
            "ontology_version": "1.0.0",
        }
        result = await self.repo.upsert_node("TextChunk", chunk.chunk_id, props)
        self.chunks_stored += 1
        return result

    async def link_relationship(self, rel: ExtractedRelationship) -> dict:
        if not self.repo:
            self.relationships_created += 1
            return {"dry_run": True, **rel.model_dump()}
        source_label = LABEL_MAP.get(
            rel.source_label.value if hasattr(rel.source_label, "value") else str(rel.source_label),
            str(rel.source_label)
        )
        target_label = LABEL_MAP.get(
            rel.target_label.value if hasattr(rel.target_label, "value") else str(rel.target_label),
            str(rel.target_label)
        )
        relationship = rel.relationship.value if hasattr(rel.relationship, "value") else str(rel.relationship)
        props = dict(rel.properties or {})
        props["confidence"] = rel.confidence
        if rel.evidence_text:
            props["evidence_text"] = rel.evidence_text[:2000]
        if rel.chunk_id:
            props["chunk_id"] = rel.chunk_id
        try:
            out = await self.repo.link_nodes(
                source_label, rel.source_id,
                relationship,
                target_label, rel.target_id,
                props,
            )
            self.relationships_created += 1
            return out
        except Exception as e:
            logger.error("Link failed %s -[%s]-> %s : %s", rel.source_id, relationship, rel.target_id, e)
            raise

    async def link_chunk_mentions(
        self,
        chunk_id: str,
        entity_id: str,
        entity_label: str,
        *,
        confidence: float = 0.9,
        claim_field: Optional[str] = None,
        relationship: str = "MENTIONS",
    ) -> dict:
        """Create (:TextChunk)-[:MENTIONS|:GROUNDS_ENTITY]->(Entity)"""
        if not self.repo:
            self.relationships_created += 1
            return {"dry_run": True}
        props = {"confidence_score": confidence, "confidence": confidence}
        if claim_field:
            props["claim_field"] = claim_field
        # Ensure TextChunk node exists — caller should have stored it
        try:
            return await self.repo.link_nodes(
                "TextChunk", chunk_id,
                relationship,
                LABEL_MAP.get(entity_label, entity_label), entity_id,
                props,
            )
        except Exception as e:
            logger.warning("Chunk mention link failed (may be missing endpoints): %s", e)
            return {"error": str(e)}

    async def load_batch(
        self,
        chunks: List[ChunkMetadata],
        entities: List[ExtractedEntity],
        relationships: List[ExtractedRelationship],
        *,
        create_mentions: bool = True,
    ) -> dict:
        """
        Transactional-ish batch load:
        1. upsert chunks
        2. upsert entities
        3. link relationships
        4. link chunk mentions
        """
        # reset counters
        self.nodes_upserted = 0
        self.relationships_created = 0
        self.chunks_stored = 0

        # 1. chunks
        chunk_map = {c.chunk_id: c for c in chunks}
        for c in chunks:
            try:
                await self.store_chunk_node(c)
            except Exception as e:
                logger.error("Chunk store failed %s: %s", c.chunk_id, e)

        # 2. entities (dedupe first)
        seen = set()
        unique_entities = []
        for e in entities:
            if e.entity_id not in seen:
                seen.add(e.entity_id)
                unique_entities.append(e)
        for ent in unique_entities:
            try:
                await self.upsert_entity(ent)
            except Exception as e:
                logger.error("Entity upsert failed %s: %s", ent.entity_id, e)

        # 3. relationships
        rel_errors = []
        for r in relationships:
            try:
                await self.link_relationship(r)
            except Exception as e:
                rel_errors.append(f"{r.source_id}-[{r.relationship}]->{r.target_id}: {e}")

        # 4. chunk mentions auditability
        mentions_created = 0
        if create_mentions:
            # map entity -> chunk_id
            for ent in unique_entities:
                if ent.chunk_id and ent.chunk_id in chunk_map:
                    try:
                        await self.link_chunk_mentions(
                            ent.chunk_id,
                            ent.entity_id,
                            ent.label.value if hasattr(ent.label, "value") else str(ent.label),
                            confidence=ent.confidence,
                            relationship="MENTIONS",
                        )
                        mentions_created += 1
                    except Exception:
                        pass
            # also GROUNDS_ENTITY for FailureMode / SOP / SOPStep / SafetyHazard
            grounding_labels = {"FailureMode", "SOP", "SOPStep", "SafetyHazard"}
            for ent in unique_entities:
                lbl = ent.label.value if hasattr(ent.label, "value") else str(ent.label)
                if lbl in grounding_labels and ent.chunk_id:
                    try:
                        await self.link_chunk_mentions(
                            ent.chunk_id,
                            ent.entity_id,
                            lbl,
                            confidence=ent.confidence,
                            claim_field="display_name",
                            relationship="GROUNDS_ENTITY",
                        )
                        mentions_created += 1
                    except Exception:
                        pass

        return {
            "chunks_stored": self.chunks_stored,
            "nodes_upserted": self.nodes_upserted,
            "relationships_created": self.relationships_created,
            "mentions_created": mentions_created,
            "relationship_errors": rel_errors,
            "success": len(rel_errors) == 0,
        }


# Synchronous wrapper for tests that don't want asyncio
def load_batch_sync(*args, **kwargs):
    import asyncio
    loader: GraphLoader = kwargs.pop("loader", GraphLoader(repository=None))
    return asyncio.run(loader.load_batch(*args, **kwargs))
