#!/usr/bin/env python3
"""
Phase 4 — Qdrant Collection Bootstrap
Idempotent creation of vector collections + payload indexes
"""

from __future__ import annotations

import argparse
import json
import logging
import sys

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
logger = logging.getLogger("init_qdrant")

def main():
    parser = argparse.ArgumentParser(description="Initialize Qdrant collections for Phase 4")
    parser.add_argument("--recreate", action="store_true", help="Drop and recreate collections (DANGER)")
    parser.add_argument("--collection", default=None, help="Initialize single collection only")
    parser.add_argument("--vector-size", type=int, default=None, help="Override vector dimensions")
    args = parser.parse_args()

    try:
        from app.vector.qdrant_manager import QdrantCollectionManager, init_default_collections
        from app.vector.embedding_engine import get_embedding_engine
        from app.vector.client import check_qdrant_health

        health = check_qdrant_health()
        print(json.dumps({"qdrant_health": health}, indent=2))
        if health.get("status") != "ok":
            logger.error("Qdrant not healthy — aborting")
            sys.exit(2)

        eng = get_embedding_engine()
        logger.info("Embedding engine: %s dim=%d", eng.model_name, eng.vector_dim)

        if args.collection:
            mgr = QdrantCollectionManager(
                collection_name=args.collection,
                vector_size=args.vector_size or eng.vector_dim,
            )
            report = mgr.ensure_collection(recreate=args.recreate)
            report["describe"] = mgr.describe()
            print(json.dumps(report, indent=2, default=str))
        else:
            reports = init_default_collections(recreate=args.recreate)
            # describe each
            from app.vector.qdrant_manager import QdrantCollectionManager
            for coll in reports.keys():
                try:
                    mgr = QdrantCollectionManager(collection_name=coll)
                    reports[coll]["describe"] = mgr.describe()
                except Exception:
                    pass
            print(json.dumps(reports, indent=2, default=str))

        logger.info("✓ Qdrant collections initialized")
        sys.exit(0)

    except Exception as e:
        logger.exception("Init failed: %s", e)
        print(json.dumps({"success": False, "error": str(e)}))
        sys.exit(1)


if __name__ == "__main__":
    main()
