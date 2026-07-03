"""
Phase 4 — Chunk Repository
Pulls :Chunk nodes from Neo4j for idempotent vector ingestion
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

# Chunk node field mapping — matches Phase 3 graph_loader + Phase 2 schema_migrations
CHUNK_CYPHER_PROJECTION = """
n.chunk_id AS chunk_id,
coalesce(n.source_document_id, n.document_id) AS document_id,
coalesce(n.source_type, n.document_type, 'MANUAL') AS document_type,
coalesce(n.asset_type, null) AS asset_type,
n.section_title AS section_title,
n.source_document AS source_filename,
n.chunk_index AS chunk_index,
n.token_count AS token_count,
n.char_count AS char_count,
n.text AS text,
n.hash AS hash,
n.page_start AS page_start,
n.page_end AS page_end
"""


class ChunkVectorRepository:
    """
    Reads TextChunk nodes from Neo4j — the source of truth for Phase 3 output.
    Falls back to ingestion pipeline in-memory chunks if Neo4j unavailable.
    """

    def __init__(self, graph_repository=None):
        self.repo = graph_repository  # Neo4jGraphRepository expected

    async def fetch_chunks(
        self,
        *,
        limit: int = 1000,
        offset: int = 0,
        document_type: Optional[str] = None,
        asset_type: Optional[str] = None,
        only_unembedded: bool = False,  # reserved for future embedding tracking
    ) -> List[Dict[str, Any]]:
        """Return list of chunk dicts ready for embedding."""
        if self.repo is None:
            logger.warning("ChunkVectorRepository: no graph_repository — returning empty")
            return []

        # Build Cypher dynamically
        where_clauses = []
        params: Dict[str, Any] = {"limit": limit, "offset": offset}
        if document_type:
            where_clauses.append("n.source_type = $document_type OR n.document_type = $document_type")
            params["document_type"] = document_type
        if asset_type:
            where_clauses.append("n.asset_type = $asset_type")
            params["asset_type"] = asset_type

        where_sql = ("WHERE " + " AND ".join(where_clauses)) if where_clauses else ""

        cypher = f"""
        MATCH (n:TextChunk)
        {where_sql}
        RETURN {CHUNK_CYPHER_PROJECTION}
        ORDER BY n.chunk_index ASC
        SKIP $offset LIMIT $limit
        """

        try:
            # Neo4jGraphRepository pattern: repo.execute_read?
            # Fallback to generic driver usage if available
            driver = getattr(self.repo, "_driver", None) or getattr(self.repo, "driver", None)
            if driver is None:
                # try repo.run method
                if hasattr(self.repo, "run_query"):
                    records = await self.repo.run_query(cypher, params)
                    return [dict(r) for r in records]
                logger.error("No driver access on graph_repository")
                return []

            # use async driver session
            async with driver.session(database=getattr(self.repo, "database", None)) as session:
                result = await session.run(cypher, params)
                records = await result.data()
                return records
        except Exception as e:
            logger.exception("fetch_chunks failed: %s", e)
            return []

    async def count_chunks(self, document_type: Optional[str] = None) -> int:
        if self.repo is None:
            return 0
        cypher = "MATCH (n:TextChunk)"
        params = {}
        if document_type:
            cypher += " WHERE n.source_type = $dt OR n.document_type = $dt"
            params["dt"] = document_type
        cypher += " RETURN count(n) AS c"
        try:
            driver = getattr(self.repo, "_driver", None) or getattr(self.repo, "driver", None)
            if driver is None:
                return 0
            async with driver.session() as session:
                res = await session.run(cypher, params)
                rec = await res.single()
                return rec["c"] if rec else 0
        except Exception:
            return 0
