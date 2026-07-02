#!/usr/bin/env python3
"""
Bootstrap Qdrant collections per docs/qdrant_schema.md.

Usage:
    python scripts/init_qdrant_collections.py
"""
from __future__ import annotations

import logging
import sys

sys.path.insert(0, ".")

from qdrant_client.models import Distance, PayloadSchemaType, VectorParams  # noqa: E402

from app.vector.client import get_client  # noqa: E402
from app.vector.schema import collection_config  # noqa: E402

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

_DISTANCE_MAP = {
    "Cosine": Distance.COSINE,
    "Euclid": Distance.EUCLID,
    "Dot": Distance.DOT,
}


def main() -> None:
    client = get_client()
    for name, cfg in collection_config().items():
        logger.info("Ensuring collection '%s' (size=%s, distance=%s)", name, cfg["size"], cfg["distance"])
        client.recreate_collection(
            collection_name=name,
            vectors_config=VectorParams(size=cfg["size"], distance=_DISTANCE_MAP[cfg["distance"]]),
        )
        for field in ("asset_ids", "asset_types", "source_type"):
            client.create_payload_index(
                collection_name=name,
                field_name=field,
                field_schema=PayloadSchemaType.KEYWORD,
            )
    logger.info("Qdrant collection bootstrap complete.")


if __name__ == "__main__":
    main()
