#!/usr/bin/env python3
"""
Phase 4 — Idempotent Vector Ingestion CLI
Pulls :Chunk nodes from Neo4j (Phase 3 output), embeds, upserts to Qdrant
"""

from __future__ import annotations

import argparse
import asyncio
import json
import logging
import sys
from pathlib import Path

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger("embed_chunks")

async def main_async(args):
    # 1. Try Neo4j repository
    graph_repo = None
    if not args.input_json:
        try:
            from app.graph.client import get_neo4j_driver
            from app.graph.graph_repository import Neo4jGraphRepository
            driver = get_neo4j_driver()
            await driver.verify_connectivity()
            graph_repo = Neo4jGraphRepository(driver)
            logger.info("✓ Neo4j connected")
        except Exception as e:
            logger.warning("Neo4j unavailable: %s", e)
            graph_repo = None

    from app.vector.pipeline import VectorIngestionPipeline
    from app.vector.embedding_engine import get_embedding_engine

    eng = get_embedding_engine(model_name=args.model)
    logger.info("Embedding model: %s dim=%d device=%s", eng.model_name, eng.vector_dim, eng.device)

    pipeline = VectorIngestionPipeline(
        embedding_engine=eng,
        collection_name=args.collection,
        batch_size=args.batch_size,
    )

    if args.input_json:
        # load chunks from JSON file (exported from Phase 3)
        data = json.loads(Path(args.input_json).read_text())
        chunks = data if isinstance(data, list) else data.get("chunks", [])
        logger.info("Loaded %d chunks from %s", len(chunks), args.input_json)
        result = await pipeline.ingest_chunks(chunks, skip_existing=not args.force)
    else:
        # pull from Neo4j
        result = await pipeline.ingest_from_graph(
            graph_repository=graph_repo,
            limit=args.limit,
            document_type=args.document_type,
        )

    print(json.dumps(result.model_dump(), indent=2, default=str))

    # close
    if graph_repo and hasattr(graph_repo, "_driver"):
        try:
            await graph_repo._driver.close()
        except Exception:
            pass

    return 0 if result.failed == 0 else 1


def main():
    p = argparse.ArgumentParser(description="Phase 4 embedding ingestion")
    p.add_argument("--collection", default="operational_knowledge_v4", help="Qdrant collection")
    p.add_argument("--model", default=None, help="Embedding model override (e.g. sentence-transformers/all-mpnet-base-v2)")
    p.add_argument("--batch-size", type=int, default=32)
    p.add_argument("--limit", type=int, default=2000, help="Max chunks to pull from Neo4j")
    p.add_argument("--document-type", default=None, help="Filter: MANUAL|SOP|…")
    p.add_argument("--input-json", default=None, help="Offline mode: JSON array of chunk dicts")
    p.add_argument("--force", action="store_true", help="Re-embed even if already in Qdrant")
    args = p.parse_args()
    try:
        code = asyncio.run(main_async(args))
        sys.exit(code)
    except KeyboardInterrupt:
        sys.exit(130)
    except Exception as e:
        logger.exception("Fatal: %s", e)
        sys.exit(1)


if __name__ == "__main__":
    main()
