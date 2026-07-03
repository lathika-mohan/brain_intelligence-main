"""
Phase 3 — Data Quality Assertions

Post-ingestion verification scripts.
"""

from __future__ import annotations

import re
from typing import List, Dict, Any

from .schemas import ExtractedEntity, ExtractedRelationship, ChunkMetadata

UPPER_SNAKE_RE = re.compile(r"^[A-Z][A-Z0-9_]*$")


def assert_no_isolated_nodes(
    entities: List[ExtractedEntity],
    relationships: List[ExtractedRelationship],
) -> List[str]:
    """Ensure zero isolated nodes were created without accompanying properties / edges."""
    errors: List[str] = []
    ent_ids = {e.entity_id for e in entities}
    connected = set()
    for r in relationships:
        connected.add(r.source_id)
        connected.add(r.target_id)
    isolated = ent_ids - connected
    # Isolated is allowed ONLY if entity has property hash / provenance chunk_id
    for eid in isolated:
        ent = next((e for e in entities if e.entity_id == eid), None)
        if not ent:
            continue
        if not ent.chunk_id:
            errors.append(f"Isolated node without provenance chunk_id: {eid}")
        # check mandatory hash-like properties: must have display_name + confidence
        if not ent.display_name or ent.confidence is None:
            errors.append(f"Isolated node missing mandatory properties: {eid}")
    return errors


def assert_relationship_naming(relationships: List[ExtractedRelationship]) -> List[str]:
    """Relationship strings strictly conform to Phase 1 UPPERCASE_SNAKE_CASE."""
    errors = []
    for r in relationships:
        rel = r.relationship.value if hasattr(r.relationship, "value") else str(r.relationship)
        if not UPPER_SNAKE_RE.match(rel):
            errors.append(f"Relationship not UPPERCASE_SNAKE_CASE: {rel} ({r.source_id}->{r.target_id})")
    return errors


def assert_chunk_traceability(
    entities: List[ExtractedEntity],
    relationships: List[ExtractedRelationship],
    chunks: List[ChunkMetadata],
) -> List[str]:
    """Every triple maintains traceable linkage back to parent source document chunk."""
    errors = []
    chunk_ids = {c.chunk_id for c in chunks}
    for e in entities:
        if e.chunk_id and e.chunk_id not in chunk_ids:
            errors.append(f"Entity {e.entity_id} references missing chunk {e.chunk_id}")
        if not e.chunk_id:
            errors.append(f"Entity {e.entity_id} missing chunk_id provenance")
    for r in relationships:
        if r.chunk_id and r.chunk_id not in chunk_ids:
            errors.append(f"Relationship {r.source_id}-[{r.relationship}]->{r.target_id} references missing chunk {r.chunk_id}")
    return errors


def assert_required_edge_properties(relationships: List[ExtractedRelationship]) -> List[str]:
    errors = []
    for r in relationships:
        rel = r.relationship.value if hasattr(r.relationship, "value") else str(r.relationship)
        props = r.properties or {}
        if rel == "EXHIBITS_ANOMALY":
            if "metric" not in props:
                errors.append(f"EXHIBITS_ANOMALY missing metric: {r.source_id}->{r.target_id}")
            if "confidence_weight" not in props:
                errors.append(f"EXHIBITS_ANOMALY missing confidence_weight: {r.source_id}->{r.target_id}")
            else:
                cw = props.get("confidence_weight")
                try:
                    if not (0 <= float(cw) <= 1):
                        errors.append(f"confidence_weight out of range: {cw}")
                except Exception:
                    errors.append(f"confidence_weight invalid: {cw}")
        if rel == "HAS_STEP":
            if "sequence_number" not in props:
                errors.append(f"HAS_STEP missing sequence_number: {r.source_id}->{r.target_id}")
    return errors


def run_quality_assertions(
    entities: List[ExtractedEntity],
    relationships: List[ExtractedRelationship],
    chunks: List[ChunkMetadata],
) -> Dict[str, Any]:
    """
    Run all Phase 3 data quality assertions.
    Returns dict with passed: bool, errors: list
    """
    errors = []
    errors.extend(assert_no_isolated_nodes(entities, relationships))
    errors.extend(assert_relationship_naming(relationships))
    errors.extend(assert_chunk_traceability(entities, relationships, chunks))
    errors.extend(assert_required_edge_properties(relationships))

    # Check property hashes exist (simulate Phase 2 property hash requirement)
    for e in entities:
        # Every node must have id + display_name (already Pydantic enforced)
        # Additional: ensure ontology_version would be set at load time
        if not e.entity_id or ":" not in e.entity_id:
            errors.append(f"Node {e.entity_id} fails ID strategy check")

    return {
        "passed": len(errors) == 0,
        "error_count": len(errors),
        "errors": errors,
        "entity_count": len(entities),
        "relationship_count": len(relationships),
        "chunk_count": len(chunks),
    }


# Async helper to run assertions against live Neo4j (optional)
async def validate_graph_integrity(repo) -> Dict[str, Any]:
    """
    Run Cypher-based post-ingestion checks against Neo4j.
    Returns findings.
    Requires a Neo4jGraphRepository instance.
    """
    findings: Dict[str, Any] = {}
    # 1. isolated nodes
    try:
        cypher_isolated = """
        MATCH (n)
        WHERE NOT (n)--()
        RETURN labels(n)[0] AS label, n.id AS id
        LIMIT 25
        """
        rows = await repo._read(cypher_isolated, {})
        findings["isolated_nodes"] = rows
    except Exception as e:
        findings["isolated_nodes_error"] = str(e)

    # 2. relationship naming check
    try:
        cypher_bad_rel = """
        MATCH ()-[r]->()
        WITH DISTINCT type(r) AS t
        WHERE NOT t =~ '^[A-Z][A-Z0-9_]*$'
        RETURN collect(t) AS bad_relationships
        """
        rows = await repo._read(cypher_bad_rel, {})
        findings["bad_relationship_names"] = rows[0]["bad_relationships"] if rows else []
    except Exception as e:
        findings["bad_rel_error"] = str(e)

    # 3. chunk traceability: entities without MENTIONS inbound
    try:
        cypher_orphan = """
        MATCH (e)
        WHERE NOT e:TextChunk AND NOT e:SourceDocument
          AND NOT ()-[:MENTIONS]->(e)
          AND NOT ()-[:GROUNDS_ENTITY]->(e)
        RETURN labels(e)[0] AS label, e.id AS id
        LIMIT 20
        """
        rows = await repo._read(cypher_orphan, {})
        findings["entities_without_chunk_mention"] = rows
    except Exception as e:
        findings["traceability_error"] = str(e)

    return findings
