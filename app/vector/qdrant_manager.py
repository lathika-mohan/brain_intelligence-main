"""
Phase 4 — Qdrant Collection Configuration & Vector Engineering
Programmatic collection lifecycle via qdrant-client SDK
"""

from __future__ import annotations

import logging
import time
from typing import Any, Dict, List, Optional

from qdrant_client import QdrantClient
from qdrant_client.http import models as qm

from app.core.config import get_settings
from .client import get_qdrant_client
from .schema import (
    DEFAULT_COLLECTION,
    DEFAULT_DISTANCE,
    DEFAULT_VECTOR_DIM,
    HNSW_CONFIG,
    OPTIMIZERS_CONFIG,
    PAYLOAD_INDEXED_FIELDS,
    QdrantCollection,
)

logger = logging.getLogger(__name__)


class QdrantCollectionManager:
    """
    Idempotent collection provisioning + payload indexing.
    Ensures vector size / distance metric alignment with embedding model.
    """

    def __init__(
        self,
        client: Optional[QdrantClient] = None,
        collection_name: Optional[str] = None,
        vector_size: Optional[int] = None,
        distance: Optional[str] = None,
    ):
        self.client = client or get_qdrant_client()
        settings = get_settings()
        self.collection_name = collection_name or str(DEFAULT_COLLECTION.value if hasattr(DEFAULT_COLLECTION, "value") else DEFAULT_COLLECTION)
        # vector size: explicit > settings > schema default
        self.vector_size = vector_size or settings.qdrant_vector_size or DEFAULT_VECTOR_DIM
        # Allow runtime override to match embedding model automatically
        try:
            from .embedding_engine import get_embedding_engine
            eng = get_embedding_engine()
            if eng.vector_dim != self.vector_size:
                logger.info("Vector size auto-align: settings=%d → engine=%d", self.vector_size, eng.vector_dim)
                self.vector_size = eng.vector_dim
        except Exception:
            pass

        dist_str = (distance or settings.qdrant_distance_metric or DEFAULT_DISTANCE).lower()
        self.distance = {
            "cosine": qm.Distance.COSINE,
            "dot": qm.Distance.DOT,
            "euclid": qm.Distance.EUCLID,
            "euclidean": qm.Distance.EUCLID,
        }.get(dist_str, qm.Distance.COSINE)

    # -----------------------------------------------------------------------
    # Collection lifecycle
    # -----------------------------------------------------------------------

    def ensure_collection(self, recreate: bool = False) -> Dict[str, Any]:
        """Idempotent create — validates dim / distance, recreates on mismatch if requested."""
        name = self.collection_name
        exists = self.client.collection_exists(collection_name=name)

        if exists and recreate:
            logger.warning("Recreating Qdrant collection %s", name)
            self.client.delete_collection(collection_name=name)
            exists = False

        if exists:
            # validate existing config
            try:
                info = self.client.get_collection(collection_name=name)
                cfg = info.config.params.vectors
                # vectors can be single or dict — handle both
                if isinstance(cfg, qm.VectorParams):
                    current_size = cfg.size
                    current_distance = cfg.distance
                else:
                    # named vector — take first
                    first = next(iter(cfg.values())) if isinstance(cfg, dict) else cfg
                    current_size = getattr(first, "size", self.vector_size)
                    current_distance = getattr(first, "distance", self.distance)

                if current_size != self.vector_size:
                    msg = f"Collection {name} vector size mismatch: {current_size} != {self.vector_size}"
                    logger.error(msg)
                    if recreate:
                        return self.ensure_collection(recreate=True)
                    raise ValueError(msg)
            except Exception as e:
                logger.warning("Could not validate existing collection %s: %s", name, e)

            logger.info("Qdrant collection %s already exists — skipping create", name)
            self.ensure_payload_indexes()
            return {"created": False, "name": name, "vector_size": self.vector_size}

        # create collection
        logger.info("Creating Qdrant collection %s dim=%d distance=%s", name, self.vector_size, self.distance)
        t0 = time.perf_counter()
        self.client.create_collection(
            collection_name=name,
            vectors_config=qm.VectorParams(
                size=self.vector_size,
                distance=self.distance,
                hnsw_config=qm.HnswConfigDiff(
                    m=HNSW_CONFIG["m"],
                    ef_construct=HNSW_CONFIG["ef_construct"],
                    payload_m=16,
                ),
            ),
            optimizers_config=qm.OptimizersConfigDiff(
                default_segment_number=OPTIMIZERS_CONFIG["default_segment_number"],
                memmap_threshold=OPTIMIZERS_CONFIG["memmap_threshold"],
            ),
            timeout=60,
        )
        elapsed_ms = (time.perf_counter() - t0) * 1000
        logger.info("Collection %s created in %.1fms", name, elapsed_ms)
        self.ensure_payload_indexes()
        return {"created": True, "name": name, "vector_size": self.vector_size, "latency_ms": elapsed_ms}

    # -----------------------------------------------------------------------
    # Payload indexing — critical for hybrid filtering performance
    # -----------------------------------------------------------------------

    def ensure_payload_indexes(self) -> List[str]:
        """Create keyword / integer payload indexes on high-traffic filter fields."""
        created: List[str] = []
        field_schemas = {
            "chunk_id": qm.PayloadSchemaType.KEYWORD,
            "document_id": qm.PayloadSchemaType.KEYWORD,
            "document_type": qm.PayloadSchemaType.KEYWORD,
            "asset_type": qm.PayloadSchemaType.KEYWORD,
            "source_filename": qm.PayloadSchemaType.KEYWORD,
            "chunk_index": qm.PayloadSchemaType.INTEGER,
            "token_count": qm.PayloadSchemaType.INTEGER,
            "section_title": qm.PayloadSchemaType.TEXT,
        }
        for field in PAYLOAD_INDEXED_FIELDS:
            schema = field_schemas.get(field, qm.PayloadSchemaType.KEYWORD)
            try:
                self.client.create_payload_index(
                    collection_name=self.collection_name,
                    field_name=field,
                    field_schema=schema,
                    wait=True,
                )
                created.append(field)
                logger.debug("Payload index ensured: %s (%s)", field, schema)
            except Exception as e:
                # index likely exists — qdrant raises if duplicate
                if "already exists" in str(e).lower() or "already" in str(e).lower():
                    continue
                logger.debug("Payload index %s skipped: %s", field, e)
        if created:
            logger.info("Payload indexes created for %s: %s", self.collection_name, ", ".join(created))
        return created

    # -----------------------------------------------------------------------
    # Introspection
    # -----------------------------------------------------------------------

    def describe(self) -> Dict[str, Any]:
        try:
            info = self.client.get_collection(collection_name=self.collection_name)
            points_count = info.points_count
            vectors_cfg = info.config.params.vectors
            if isinstance(vectors_cfg, qm.VectorParams):
                size = vectors_cfg.size
                distance = str(vectors_cfg.distance)
            else:
                size = self.vector_size
                distance = str(self.distance)
            return {
                "collection": self.collection_name,
                "points_count": points_count,
                "vector_size": size,
                "distance": distance,
                "status": str(info.status),
                "optimizer_status": str(getattr(info, "optimizer_status", "unknown")),
            }
        except Exception as e:
            return {"collection": self.collection_name, "error": str(e), "exists": False}

    def count_points(self) -> int:
        try:
            info = self.client.get_collection(self.collection_name)
            return info.points_count or 0
        except Exception:
            return 0

    def wipe(self, confirm: bool = False) -> bool:
        """Danger: delete collection — requires confirm=True"""
        if not confirm:
            raise ValueError("wipe requires confirm=True")
        if self.client.collection_exists(self.collection_name):
            self.client.delete_collection(self.collection_name)
            logger.warning("Wiped collection %s", self.collection_name)
            return True
        return False


# ---------------------------------------------------------------------------
# Convenience bootstrap
# ---------------------------------------------------------------------------

def init_default_collections(
    client: Optional[QdrantClient] = None,
    recreate: bool = False,
) -> Dict[str, Any]:
    """
    Initialize all Phase 4 collections:
    - operational_knowledge_v4 (primary)
    - sop_documents, technical_manuals, incident_reports (legacy Phase 0 names)
    """
    client = client or get_qdrant_client()
    reports = {}
    collections_to_init = [
        QdrantCollection.OPERATIONAL_KNOWLEDGE.value,
        QdrantCollection.SOP_DOCS.value,
        QdrantCollection.TECHNICAL_MANUALS.value,
        QdrantCollection.INCIDENT_REPORTS.value,
    ]
    for coll in collections_to_init:
        mgr = QdrantCollectionManager(client=client, collection_name=coll)
        try:
            reports[coll] = mgr.ensure_collection(recreate=recreate)
        except Exception as e:
            reports[coll] = {"error": str(e), "created": False}
    return reports
