"""
Phase 5 — GraphRAG Service Orchestrator
==========================================
The main service that ties together all Phase 5 components:

  1. Hybrid retrieval (Qdrant + Neo4j) via ``HybridRetriever``
  2. Context fusion (RRF) via ``ContextFusionEngine``
  3. Citation & provenance via ``CitationEngine``
  4. Grounded prompt construction via ``PromptBuilder``
  5. LLM synthesis via ``LLMProvider``
  6. Response formatting into Phase 0 contracts

The service is async-first and designed to be called from the FastAPI router.
It handles errors gracefully — if one component fails (e.g. Neo4j is down),
the pipeline degrades gracefully rather than failing entirely.
"""

from __future__ import annotations

import logging
import time
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from app.core.config import get_settings
from app.graphrag.citation_engine import CitationEngine, ProvenanceRecord
from app.graphrag.context_fusion import ContextFusionEngine, FusionResult
from app.graphrag.llm_client import LLMProvider, get_llm_provider
from app.graphrag.prompt_templates import PromptBuilder
from app.graphrag.retrieval import HybridRetriever, serialise_graph_for_frontend
from app.models.graphrag import (
    GraphRagContextChunk,
    GraphRagEdge,
    GraphRagNode,
    GraphRagQueryRequest,
    GraphRagQueryResponse,
    Citation,
)

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# GraphRAG Service
# ---------------------------------------------------------------------------

class GraphRagService:
    """
    End-to-end GraphRAG pipeline orchestrator.

    Lifecycle:
        service = GraphRagService()  # or use get_graphrag_service()
        response = await service.query(GraphRagQueryRequest(...))
    """

    def __init__(
        self,
        *,
        retriever: Optional[HybridRetriever] = None,
        fusion_engine: Optional[ContextFusionEngine] = None,
        citation_engine: Optional[CitationEngine] = None,
        prompt_builder: Optional[PromptBuilder] = None,
        llm_provider: Optional[LLMProvider] = None,
        graph_repository=None,
        graph_query_service=None,
        vector_search_service=None,
    ) -> None:
        self.settings = get_settings()
        self.retriever = retriever or HybridRetriever(
            vector_search_service=vector_search_service,
            graph_query_service=graph_query_service,
            graph_repository=graph_repository,
        )
        self.fusion = fusion_engine or ContextFusionEngine(
            rrf_k=self.settings.graphrag_top_k_vector
        )
        self.citation = citation_engine or CitationEngine()
        self.prompt = prompt_builder or PromptBuilder()
        self.llm = llm_provider or get_llm_provider()

    # ------------------------------------------------------------------
    # Public API — the main query pipeline
    # ------------------------------------------------------------------

    async def query(self, request: GraphRagQueryRequest) -> GraphRagQueryResponse:
        """
        Execute the full GraphRAG pipeline for a single query.

        Steps:
          1. Hybrid retrieval (vector + graph in parallel)
          2. Context fusion (RRF)
          3. Citation assignment
          4. Prompt construction
          5. LLM synthesis
          6. Response formatting

        Returns a Phase 0 ``GraphRagQueryResponse``.
        """
        t0 = time.perf_counter()

        # --- Step 1: Hybrid retrieval ---
        retrieval_result = await self.retriever.retrieve(
            query_text=request.query_text,
            top_k=request.top_k,
            min_score=request.min_score,
            max_graph_hops=request.max_graph_hops,
            asset_id=request.asset_id,
            filters=request.filters,
        )

        vector_hits = retrieval_result["vector_hits"]
        graph_hits = retrieval_result["graph_hits"]
        graph_nodes_raw = retrieval_result["graph_nodes_raw"]
        graph_edges_raw = retrieval_result["graph_edges_raw"]
        retrieval_timing = retrieval_result["timing"]

        logger.info(
            "Retrieval complete: %d vector hits, %d graph hits (%.1f ms)",
            len(vector_hits), len(graph_hits), retrieval_timing["total_ms"],
        )

        # --- Step 2: Context fusion ---
        fusion_result: FusionResult = self.fusion.fuse(
            vector_hits=vector_hits,
            graph_hits=graph_hits,
            method="rrf",
            max_candidates=self.settings.graphrag_max_context_chunks,
        )

        logger.info(
            "Fusion complete: %d candidates (vector=%d, graph=%d)",
            len(fusion_result.candidates),
            fusion_result.total_vector_candidates,
            fusion_result.total_graph_candidates,
        )

        # --- Step 3: Citation assignment ---
        provenance = self.citation.build(fusion_result.candidates)
        prov_hash = self.citation.compute_provenance_hash(provenance)
        logger.debug("Provenance hash: %s (%d records)", prov_hash, len(provenance))

        # --- Step 4 & 5: Prompt + LLM synthesis ---
        answer: Optional[str] = None
        llm_latency = 0.0
        llm_model = ""

        if provenance:
            try:
                system_prompt = self.prompt.build_system_prompt(
                    user_query=request.query_text,
                    provenance=provenance,
                    asset_id=request.asset_id,
                )
                user_message = self.prompt.build_user_message(request.query_text)

                llm_result = await self.llm.complete(
                    system_prompt=system_prompt,
                    user_message=user_message,
                    max_tokens=1024,
                    temperature=0.1,
                )
                answer = llm_result.get("text", "")
                llm_latency = llm_result.get("latency_ms", 0.0)
                llm_model = llm_result.get("model", "")

                # Validate citations
                citation_audit = PromptBuilder.validate_citations_in_response(answer, provenance)
                logger.info(
                    "LLM synthesis: %d valid citations, %d hallucinated, compliance=%.1f%%",
                    len(citation_audit["valid_tags"]),
                    len(citation_audit["hallucinated_tags"]),
                    citation_audit["compliance_ratio"] * 100,
                )
            except Exception as e:
                logger.error("LLM synthesis failed: %s", e, exc_info=True)
                answer = None
        else:
            answer = self.prompt.build_no_context_response()
            logger.warning("No context retrieved — returning fallback response")

        # --- Step 6: Build response ---
        total_latency = (time.perf_counter() - t0) * 1000.0

        # Build context chunks from fusion results
        context_chunks = self._build_context_chunks(fusion_result, provenance)

        # Build graph nodes/edges for frontend
        graph_nodes, graph_edges = self._build_graph_response(
            graph_nodes_raw, graph_edges_raw
        )

        # Build citations from LLM output
        citations: List[Citation] = []
        if answer:
            citations = CitationEngine.resolve_citations(answer, provenance)

        # Compute overall confidence
        overall_confidence = self._compute_overall_confidence(
            fusion_result, provenance, answer
        )

        # Embedding model name
        embedding_model = ""
        if vector_hits:
            embedding_model = self.settings.embedding_model_name

        response = GraphRagQueryResponse(
            answer=answer,
            context_chunks=context_chunks,
            graph_nodes=graph_nodes,
            graph_edges=graph_edges,
            citations=citations,
            overall_confidence=overall_confidence,
            graph_nodes_expanded=len(graph_nodes_raw),
            vector_hits=len(vector_hits),
            latency_ms=round(total_latency, 2),
            query_embedding_model=embedding_model,
            generated_at=datetime.now(timezone.utc).isoformat(),
        )

        logger.info(
            "GraphRAG query complete: latency=%.1fms, vector_hits=%d, graph_nodes=%d, citations=%d",
            total_latency, len(vector_hits), len(graph_nodes), len(citations),
        )

        return response

    # ------------------------------------------------------------------
    # Response building helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _build_context_chunks(
        fusion_result: FusionResult,
        provenance: List[ProvenanceRecord],
    ) -> List[GraphRagContextChunk]:
        """Convert fusion candidates to Phase 0 context chunks."""
        prov_by_id = {p.chunk_id or p.node_id or "": p for p in provenance}
        chunks: List[GraphRagContextChunk] = []
        for cand in fusion_result.candidates:
            cid = cand.chunk_id or cand.candidate_id
            if not cand.text and not cand.node_id:
                continue
            chunks.append(GraphRagContextChunk(
                chunk_id=cid,
                text=cand.text or cand.label or "",
                score=cand.rrf_score or max(cand.score_vector, cand.score_graph),
                document_type=cand.document_type or cand.source_type or "UNKNOWN",
                source=cand.source_filename or cand.document_id,
            ))
        return chunks

    @staticmethod
    def _build_graph_response(
        nodes_raw: List[Dict[str, Any]],
        edges_raw: List[Dict[str, Any]],
    ) -> tuple[List[GraphRagNode], List[GraphRagEdge]]:
        """Convert raw graph data to Phase 0 response models."""
        graph_nodes: List[GraphRagNode] = []
        for n in nodes_raw:
            graph_nodes.append(GraphRagNode(
                id=n.get("id", ""),
                label=n.get("display_name", "") or n.get("label", ""),
                type=n.get("label", "Node"),
                properties=n.get("properties", {}),
            ))

        graph_edges: List[GraphRagEdge] = []
        for e in edges_raw:
            graph_edges.append(GraphRagEdge(
                source=e.get("source_id", ""),
                target=e.get("target_id", ""),
                relationship=e.get("relationship", ""),
                weight=e.get("properties", {}).get("confidence_weight", 1.0),
            ))

        return graph_nodes, graph_edges

    @staticmethod
    def _compute_overall_confidence(
        fusion_result: FusionResult,
        provenance: List[ProvenanceRecord],
        answer: Optional[str],
    ) -> float:
        """
        Compute an overall confidence score for the response.

        Based on:
          - Number of fused candidates (more = higher confidence)
          - Average score of top candidates
          - Whether an answer was generated
        """
        if not answer:
            return 0.0
        if not provenance:
            return 0.0

        # Average of top-3 scores
        top_scores = [p.score for p in provenance[:3]]
        avg_top_score = sum(top_scores) / len(top_scores) if top_scores else 0.0

        # Candidate count factor (diminishing returns after 5)
        count_factor = min(len(provenance) / 5.0, 1.0)

        # Cross-modal overlap bonus
        cross_modal = sum(1 for p in provenance if p.source_type == "both")
        overlap_bonus = min(cross_modal * 0.05, 0.15)

        confidence = (avg_top_score * 0.7 + count_factor * 0.2 + overlap_bonus) * (1.0 if answer else 0.0)
        return round(min(confidence, 1.0), 3)

    # ------------------------------------------------------------------
    # Health / diagnostics
    # ------------------------------------------------------------------

    async def health(self) -> Dict[str, Any]:
        """Return health status of all GraphRAG subsystems."""
        health: Dict[str, Any] = {
            "status": "ok",
            "components": {},
        }

        # Check vector service
        try:
            from app.vector.client import check_qdrant_health
            qdrant_health = check_qdrant_health()
            health["components"]["qdrant"] = qdrant_health
        except Exception as e:
            health["components"]["qdrant"] = {"status": "error", "error": str(e)}
            health["status"] = "degraded"

        # Check graph service
        try:
            from app.graph.client import GraphDriverManager
            if GraphDriverManager.is_connected():
                health["components"]["neo4j"] = {"status": "ok"}
            else:
                health["components"]["neo4j"] = {"status": "disconnected"}
                health["status"] = "degraded"
        except Exception as e:
            health["components"]["neo4j"] = {"status": "error", "error": str(e)}
            health["status"] = "degraded"

        # LLM provider
        health["components"]["llm"] = {
            "provider": type(self.llm).__name__,
            "model": getattr(self.llm, "model", "unknown"),
        }

        return health


# ---------------------------------------------------------------------------
# Singleton accessor
# ---------------------------------------------------------------------------

_service_instance: Optional[GraphRagService] = None


def get_graphrag_service(**overrides: Any) -> GraphRagService:
    """Return the singleton GraphRagService instance."""
    global _service_instance
    if _service_instance is None or overrides:
        _service_instance = GraphRagService(**overrides)
    return _service_instance


def reset_graphrag_service() -> None:
    """Reset the singleton — useful for testing."""
    global _service_instance
    _service_instance = None
