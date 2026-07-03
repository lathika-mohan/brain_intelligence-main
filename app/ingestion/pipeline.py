"""
Phase 3 — End-to-End Knowledge Extraction Pipeline

Orchestrates: parse -> chunk -> extract -> resolve -> validate -> load
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Optional, List, Dict, Any

from .pdf_parser import parse_document, DocumentCategory
from .chunker import SemanticChunker
from .extractor import ExtractionEngine
from .entity_resolver import deduplicate_entities
from .validator import run_quality_assertions
from .graph_loader import GraphLoader
from .schemas import ChunkMetadata, ExtractionResult

logger = logging.getLogger(__name__)


class KnowledgeExtractionPipeline:
    """
    Deterministic, production-grade ingestion pipeline.
    """

    def __init__(
        self,
        *,
        chunk_tokens: int = 768,
        overlap_tokens: int = 120,
        extraction_model: str = "gpt-4o-mini",
        use_mock_extractor: Optional[bool] = None,
        repository=None,
    ):
        self.chunker = SemanticChunker(
            chunk_tokens=chunk_tokens,
            overlap_tokens=overlap_tokens,
        )
        self.extractor = ExtractionEngine(
            model=extraction_model,
            use_mock=use_mock_extractor,
        )
        self.graph_loader = GraphLoader(repository=repository)
        self.repository = repository

    def parse(self, file_path: str | Path, document_category: DocumentCategory = "MANUAL"):
        return parse_document(file_path, document_category=document_category)

    def chunk(self, parsed_doc):
        return self.chunker.chunk_document(parsed_doc)

    def extract_chunk(self, chunk: ChunkMetadata) -> ExtractionResult:
        text = chunk.parent_metadata.get("text", "")
        return self.extractor.extract(chunk, text)

    def extract_batch(self, chunks: List[ChunkMetadata]) -> List[ExtractionResult]:
        results = []
        for ch in chunks:
            try:
                res = self.extract_chunk(ch)
                results.append(res)
            except Exception as e:
                logger.error("Extraction failed for chunk %s: %s", ch.chunk_id, e)
        return results

    @staticmethod
    def aggregate_results(results: List[ExtractionResult]):
        entities = []
        relationships = []
        chunk_ids = []
        for r in results:
            entities.extend(r.entities)
            relationships.extend(r.relationships)
            chunk_ids.append(r.chunk_id)
        # global deduplication
        entities = deduplicate_entities(entities)
        # deduplicate relationships by (source, rel, target)
        seen = set()
        uniq_rels = []
        for rel in relationships:
            key = (
                rel.source_id,
                rel.relationship.value if hasattr(rel.relationship, "value") else str(rel.relationship),
                rel.target_id,
            )
            if key not in seen:
                seen.add(key)
                uniq_rels.append(rel)
        return entities, uniq_rels, chunk_ids

    async def load_to_graph(
        self,
        chunks: List[ChunkMetadata],
        entities,
        relationships,
    ) -> Dict[str, Any]:
        return await self.graph_loader.load_batch(chunks, entities, relationships, create_mentions=True)

    async def run(
        self,
        file_path: str | Path,
        *,
        document_category: DocumentCategory = "MANUAL",
        validate: bool = True,
        load: bool = True,
    ) -> Dict[str, Any]:
        """
        End-to-end run: parse -> chunk -> extract -> validate -> load
        """
        # 1. Parse
        parsed = self.parse(file_path, document_category=document_category)
        # 2. Chunk
        chunks = self.chunk(parsed)
        if not chunks:
            return {"success": False, "error": "no_chunks_produced", "parsed": parsed.model_dump()}
        # 3. Extract
        results = self.extract_batch(chunks)
        entities, relationships, _ = self.aggregate_results(results)
        # 4. Validate
        validation = run_quality_assertions(entities, relationships, chunks) if validate else {"passed": True}
        # 5. Load
        load_report = {}
        if load and validation.get("passed", True):
            load_report = await self.load_to_graph(chunks, entities, relationships)
        else:
            if not validation.get("passed"):
                logger.warning("Validation failed, skipping load: %s", validation.get("errors"))

        return {
            "success": validation.get("passed", True) and (load_report.get("success", True) if load else True),
            "document_id": parsed.document_id,
            "source_filename": parsed.source_filename,
            "total_pages": parsed.total_pages,
            "chunks": len(chunks),
            "entities_extracted": len(entities),
            "relationships_extracted": len(relationships),
            "validation": validation,
            "load_report": load_report,
            "extraction_results": [r.model_dump() for r in results],
        }


# ---------------------------------------------------------------------------
# CLI entrypoint
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    import asyncio, sys, json, argparse
    parser = argparse.ArgumentParser(description="Phase 3 Knowledge Extraction Pipeline")
    parser.add_argument("input", help="PDF / text file to ingest")
    parser.add_argument("--category", default="SOP", choices=["MANUAL", "SOP", "SPEC_SHEET", "MAINTENANCE_LOG", "INCIDENT_REPORT"])
    parser.add_argument("--mock", action="store_true", help="Force mock extractor (no LLM API)")
    parser.add_argument("--no-load", action="store_true", help="Skip graph load, validate only")
    args = parser.parse_args()

    async def _main():
        # try to get a real repo if Neo4j env is configured
        repo = None
        try:
            from app.graph.client import get_neo4j_driver
            from app.graph.graph_repository import Neo4jGraphRepository
            driver = get_neo4j_driver()
            # quick ping
            await driver.verify_connectivity()
            repo = Neo4jGraphRepository(driver)
            print("✓ Neo4j repository connected", file=sys.stderr)
        except Exception as e:
            print(f"⚠ Neo4j not available, running dry-run: {e}", file=sys.stderr)
            repo = None

        pipeline = KnowledgeExtractionPipeline(
            use_mock_extractor=args.mock or repo is None,
            repository=repo,
        )
        report = await pipeline.run(
            args.input,
            document_category=args.category,  # type: ignore
            load=not args.no_load and repo is not None,
        )
        print(json.dumps(report, indent=2, default=str))
        if repo:
            try:
                await repo._driver.close()
            except Exception:
                pass

    asyncio.run(_main())
