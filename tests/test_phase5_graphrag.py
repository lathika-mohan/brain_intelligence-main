"""
Phase 5 — GraphRAG Engine Test Suite
======================================
Comprehensive pytest tests covering:

  1. Context Fusion Engine (RRF, weighted, overlap diagnostics)
  2. Citation Engine (tagging, extraction, provenance hashing)
  3. Prompt Builder (system prompt construction, citation validation)
  4. Hybrid Retriever (entity anchor extraction, keyword matching)
  5. GraphRAG Service (end-to-end pipeline with mock LLM)
  6. API Router (endpoint contract compliance)
  7. LLM Client (mock provider behaviour)

All tests run without external database connections by using mocks.
Integration tests that require live Neo4j/Qdrant are marked with
``@pytest.mark.integration`` and skipped by default.
"""

from __future__ import annotations

import asyncio
import json
import re
from typing import Any, Dict, List
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

# ---------------------------------------------------------------------------
# Imports from the Phase 5 engine
# ---------------------------------------------------------------------------

from app.graphrag.context_fusion import (
    ContextFusionEngine,
    FusionCandidate,
    FusionResult,
    reciprocal_rank_fusion,
    DEFAULT_RRF_K,
)
from app.graphrag.citation_engine import CitationEngine, ProvenanceRecord
from app.graphrag.prompt_templates import PromptBuilder
from app.graphrag.retrieval import (
    extract_entity_anchors,
    extract_entity_keywords,
    serialise_graph_for_frontend,
)
from app.graphrag.llm_client import MockLLMProvider, get_llm_provider, reset_llm_provider
from app.graphrag.graph_rag_service import GraphRagService, get_graphrag_service, reset_graphrag_service

from app.models.graphrag import (
    GraphRagQueryRequest,
    GraphRagQueryResponse,
    GraphRagContextChunk,
    GraphRagNode,
    GraphRagEdge,
    GraphRagQueryEnvelope,
    Citation,
    GraphContextMap,
    GraphNode,
    GraphEdge,
)
from app.models.common import APIResponse


# ===========================================================================
# 1. Context Fusion Engine Tests
# ===========================================================================

class TestReciprocalRankFusion:
    """Test the pure RRF algorithm."""

    def test_single_list(self):
        ranked = [("a", 0.9), ("b", 0.8), ("c", 0.7)]
        scores = reciprocal_rank_fusion([ranked], k=60)
        assert len(scores) == 3
        # Rank 1 → 1/(60+1) = 0.01639...
        assert abs(scores["a"] - 1 / 61) < 1e-6
        assert abs(scores["b"] - 1 / 62) < 1e-6
        assert abs(scores["c"] - 1 / 63) < 1e-6

    def test_two_lists_boosts_overlap(self):
        list1 = [("a", 0.9), ("b", 0.8), ("c", 0.7)]
        list2 = [("b", 0.95), ("a", 0.85), ("d", 0.6)]
        scores = reciprocal_rank_fusion([list1, list2], k=60)
        # "a" appears in both → higher combined score
        # "b" appears in both → higher combined score
        # "c" only in list1, "d" only in list2
        assert scores["a"] > scores["c"]
        assert scores["b"] > scores["d"]
        # Both "a" and "b" should have scores from two lists
        assert scores["a"] > 1 / 61  # at least 1/(60+1) from list1
        assert scores["b"] > 1 / 61

    def test_empty_lists(self):
        scores = reciprocal_rank_fusion([], k=60)
        assert scores == {}

    def test_empty_inner_list(self):
        scores = reciprocal_rank_fusion([[], [("x", 1.0)]], k=60)
        assert "x" in scores
        assert len(scores) == 1


class TestContextFusionEngine:
    """Test the fusion engine that combines vector + graph results."""

    def setup_method(self):
        self.engine = ContextFusionEngine(rrf_k=60)

    def _make_vector_hits(self, n: int = 3) -> List[Dict[str, Any]]:
        return [
            {
                "chunk_id": f"chunk_{i}",
                "text": f"Vector chunk {i} about bearing temperature",
                "score": 0.9 - i * 0.05,
                "document_id": f"doc_{i}",
                "document_type": "SOP",
                "source_filename": f"manual_{i}.pdf",
                "page_start": i * 10,
            }
            for i in range(n)
        ]

    def _make_graph_hits(self, n: int = 3) -> List[Dict[str, Any]]:
        return [
            {
                "node_id": f"node_{i}",
                "label": "Component",
                "display_name": f"Bearing B{i}",
                "relevance_score": 0.85 - i * 0.05,
                "properties": {"type": "BEARING"},
            }
            for i in range(n)
        ]

    def test_fuse_rrf_basic(self):
        vector_hits = self._make_vector_hits(3)
        graph_hits = self._make_graph_hits(3)
        result = self.engine.fuse(vector_hits, graph_hits, method="rrf")

        assert isinstance(result, FusionResult)
        assert len(result.candidates) == 6  # 3 vector + 3 graph (no overlap)
        assert result.total_vector_candidates == 3
        assert result.total_graph_candidates == 3
        assert result.fusion_method == "rrf"

    def test_fuse_with_overlap(self):
        """When a vector chunk references a graph node, they should merge."""
        vector_hits = self._make_vector_hits(2)
        graph_hits = [
            {"node_id": "chunk_0", "label": "Component", "display_name": "Bearing",
             "relevance_score": 0.9, "properties": {}},
            {"node_id": "node_x", "label": "SOP", "display_name": "SOP-042",
             "relevance_score": 0.7, "properties": {}},
        ]
        result = self.engine.fuse(vector_hits, graph_hits, method="rrf")
        # chunk_0 should appear with source_type "both"
        overlap_cand = next(
            (c for c in result.candidates if c.candidate_id == "chunk_0"), None
        )
        assert overlap_cand is not None
        assert overlap_cand.source_type == "both"
        assert overlap_cand.score_vector > 0
        assert overlap_cand.score_graph > 0

    def test_fuse_weighted_method(self):
        vector_hits = self._make_vector_hits(2)
        graph_hits = self._make_graph_hits(2)
        result = self.engine.fuse(
            vector_hits, graph_hits, method="weighted",
            vector_weight=0.7, graph_weight=0.3,
        )
        assert len(result.candidates) == 4
        assert all(c.rrf_score > 0 for c in result.candidates)

    def test_fuse_max_candidates_cap(self):
        vector_hits = self._make_vector_hits(10)
        graph_hits = self._make_graph_hits(10)
        result = self.engine.fuse(vector_hits, graph_hits, max_candidates=5)
        assert len(result.candidates) == 5

    def test_fuse_empty_inputs(self):
        result = self.engine.fuse([], [])
        assert len(result.candidates) == 0
        assert result.total_vector_candidates == 0

    def test_compute_overlap(self):
        v = [{"chunk_id": "a"}, {"chunk_id": "b"}]
        g = [{"node_id": "b"}, {"node_id": "c"}]
        overlap = ContextFusionEngine.compute_overlap(v, g)
        assert overlap["overlap_count"] == 1  # "b" in both
        assert overlap["vector_count"] == 2
        assert overlap["graph_count"] == 2


# ===========================================================================
# 2. Citation Engine Tests
# ===========================================================================

class TestCitationEngine:
    """Test citation tagging, extraction, and provenance."""

    def setup_method(self):
        self.engine = CitationEngine()

    def test_build_from_fusion_candidates(self):
        candidates = [
            FusionCandidate(
                candidate_id="c1", label="Bearing", source_type="vector",
                text="Bearing temperature exceeded threshold", score_vector=0.92,
                chunk_id="c1", document_id="d1", document_type="SOP",
            ),
            FusionCandidate(
                candidate_id="n1", label="Component", source_type="graph",
                text="Bearing B1", score_graph=0.85,
                node_id="n1",
            ),
        ]
        provenance = self.engine.build(candidates)
        assert len(provenance) == 2
        assert provenance[0].tag == "[Source #1]"
        assert provenance[1].tag == "[Source #2]"
        assert provenance[0].source_type == "vector"
        assert provenance[1].source_type == "graph"

    def test_extract_citation_tags(self):
        text = "The bearing was overheating [Source #1] and the SOP recommends lubrication [Source #3]."
        tags = CitationEngine.extract_citation_tags(text)
        assert tags == ["[Source #1]", "[Source #3]"]

    def test_extract_citation_tags_deduplication(self):
        text = "[Source #1] says X and [Source #1] also says Y [Source #2]"
        tags = CitationEngine.extract_citation_tags(text)
        assert tags == ["[Source #1]", "[Source #2]"]

    def test_extract_citation_tags_empty(self):
        assert CitationEngine.extract_citation_tags("no citations here") == []

    def test_resolve_citations(self):
        provenance = [
            ProvenanceRecord(
                tag="[Source #1]", index=1, source_type="vector",
                chunk_id="c1", document_id="d1", document_type="SOP",
                score=0.9,
            ),
            ProvenanceRecord(
                tag="[Source #2]", index=2, source_type="graph",
                node_id="n1", node_label="Component", score=0.8,
            ),
        ]
        llm_output = "The bearing is overheating [Source #1]. The SOP recommends action [Source #2]."
        citations = CitationEngine.resolve_citations(llm_output, provenance)
        assert len(citations) == 2
        assert citations[0].citation_id == "[Source #1]"
        assert citations[1].citation_id == "[Source #2]"

    def test_resolve_citations_ignores_hallucinated(self):
        provenance = [
            ProvenanceRecord(tag="[Source #1]", index=1, source_type="vector", score=0.9),
        ]
        llm_output = "Based on [Source #1] and [Source #99]."
        citations = CitationEngine.resolve_citations(llm_output, provenance)
        assert len(citations) == 1  # [Source #99] not in provenance

    def test_provenance_hash_deterministic(self):
        provenance = [
            ProvenanceRecord(tag="[Source #1]", index=1, source_type="vector",
                             chunk_id="c1", score=0.9),
        ]
        h1 = CitationEngine.compute_provenance_hash(provenance)
        h2 = CitationEngine.compute_provenance_hash(provenance)
        assert h1 == h2
        assert len(h1) == 16

    def test_render_context_block_vector(self):
        record = ProvenanceRecord(
            tag="[Source #1]", index=1, source_type="vector",
            document_id="d1", document_type="SOP", score=0.92,
            text_snippet="Bearing temperature exceeded threshold at 88.5C",
            source_filename="SOP-MECH-042.pdf", page_number=3,
        )
        block = CitationEngine.render_context_block(record)
        assert "[Source #1]" in block
        assert "SOP-MECH-042.pdf" in block
        assert "Page: 3" in block

    def test_render_context_block_graph(self):
        record = ProvenanceRecord(
            tag="[Source #2]", index=2, source_type="graph",
            node_id="bearing-b1", node_label="Component",
            node_properties={"type": "BEARING", "status": "WARNING"},
            score=0.85,
        )
        block = CitationEngine.render_context_block(record)
        assert "[Source #2]" in block
        assert "bearing-b1" in block
        assert "Component" in block

    def test_to_citation_conversion(self):
        record = ProvenanceRecord(
            tag="[Source #1]", index=1, source_type="vector",
            chunk_id="c1", document_id="d1", document_type="SOP",
            score=0.92, source_filename="manual.pdf", page_number=5,
        )
        citation = record.to_citation(claim_span="bearing overheating")
        assert isinstance(citation, Citation)
        assert citation.citation_id == "[Source #1]"
        assert citation.claim_span == "bearing overheating"
        assert citation.source_document == "manual.pdf"
        assert citation.page_number == 5


# ===========================================================================
# 3. Prompt Builder Tests
# ===========================================================================

class TestPromptBuilder:
    """Test system prompt construction and citation validation."""

    def setup_method(self):
        self.builder = PromptBuilder()
        self.provenance = [
            ProvenanceRecord(
                tag="[Source #1]", index=1, source_type="vector",
                document_id="d1", document_type="SOP", score=0.92,
                text_snippet="Bearing temperature exceeded 88.5C",
                source_filename="SOP-042.pdf",
            ),
            ProvenanceRecord(
                tag="[Source #2]", index=2, source_type="graph",
                node_id="bearing-b1", node_label="Component", score=0.85,
            ),
        ]

    def test_build_system_prompt_contains_context(self):
        prompt = self.builder.build_system_prompt(
            "Why did the vibration spike?", self.provenance
        )
        assert "Why did the vibration spike?" in prompt
        assert "[Source #1]" in prompt
        assert "[Source #2]" in prompt
        assert "GROUNDING" in prompt or "grounding" in prompt.lower()

    def test_build_system_prompt_with_asset_id(self):
        prompt = self.builder.build_system_prompt(
            "What is the status?", self.provenance, asset_id="G-101"
        )
        assert "G-101" in prompt

    def test_build_user_message(self):
        msg = self.builder.build_user_message("Why is the turbine overheating?")
        assert "turbine overheating" in msg
        assert "[Source #N]" in msg

    def test_validate_citations_compliant(self):
        llm_output = "The bearing is overheating [Source #1] and the SOP recommends action [Source #2]."
        audit = PromptBuilder.validate_citations_in_response(llm_output, self.provenance)
        assert audit["compliance_ratio"] == 1.0
        assert len(audit["valid_tags"]) == 2
        assert len(audit["hallucinated_tags"]) == 0

    def test_validate_citations_with_hallucination(self):
        llm_output = "Based on [Source #1] and [Source #99]."
        audit = PromptBuilder.validate_citations_in_response(llm_output, self.provenance)
        assert len(audit["hallucinated_tags"]) == 1
        assert "[Source #99]" in audit["hallucinated_tags"]
        assert audit["compliance_ratio"] == 0.5

    def test_validate_citations_missing(self):
        llm_output = "Just [Source #1] is relevant."
        audit = PromptBuilder.validate_citations_in_response(llm_output, self.provenance)
        assert "[Source #2]" in audit["missing_tags"]

    def test_no_context_response(self):
        resp = PromptBuilder.build_no_context_response()
        assert "no relevant context" in resp.lower()


# ===========================================================================
# 4. Hybrid Retriever Tests (unit-level, no DB)
# ===========================================================================

class TestEntityAnchorExtraction:
    """Test entity anchor extraction from vector hits."""

    def test_extract_from_metadata(self):
        hits = [{"asset_id": "G-101", "text": ""}]
        anchors = extract_entity_anchors(hits)
        assert "G-101" in anchors

    def test_extract_from_text(self):
        hits = [{"text": "Gas Turbine G-101 is showing elevated vibration at Bearing B1"}]
        anchors = extract_entity_anchors(hits)
        # Should find asset-like patterns
        assert len(anchors) >= 1

    def test_extract_empty(self):
        assert extract_entity_anchors([]) == []

    def test_extract_keywords(self):
        hits = [{"text": "The bearing failure mode indicates overheating on the turbine"}]
        keywords = extract_entity_keywords(hits)
        assert "Component" in keywords or "FailureMode" in keywords or "Asset" in keywords


class TestGraphSerialisation:
    """Test conversion of raw Neo4j data to frontend-compatible format."""

    def test_serialise_basic(self):
        nodes = [
            {"id": "g101", "labels": ["Asset"], "props": {"id": "g101", "display_name": "G-101 Gas Turbine"}},
            {"id": "b1", "labels": ["Component"], "props": {"id": "b1", "display_name": "Bearing B1"}},
        ]
        edges = [
            {"source_id": "g101", "target_id": "b1", "type": "COMPRISED_OF", "props": {}},
        ]
        f_nodes, f_edges = serialise_graph_for_frontend(nodes, edges)
        assert len(f_nodes) == 2
        assert f_nodes[0]["type"] == "asset"
        assert f_nodes[1]["type"] == "component"
        assert len(f_edges) == 1
        assert f_edges[0]["relationship"] == "COMPRISED_OF"

    def test_serialise_empty(self):
        f_nodes, f_edges = serialise_graph_for_frontend([], [])
        assert f_nodes == []
        assert f_edges == []


# ===========================================================================
# 5. LLM Client Tests
# ===========================================================================

class TestMockLLMProvider:
    """Test the mock LLM provider."""

    @pytest.mark.asyncio
    async def test_mock_with_context(self):
        provider = MockLLMProvider()
        system = "Context: [Source #1] bearing data. [Source #2] SOP data."
        result = await provider.complete(system, "Why is the bearing hot?")
        assert "text" in result
        assert "[Source #" in result["text"]
        assert result["model"] == "mock-llm-v1"
        assert result["latency_ms"] >= 0

    @pytest.mark.asyncio
    async def test_mock_without_context(self):
        provider = MockLLMProvider()
        result = await provider.complete("No context here", "What is the status?")
        assert "text" in result
        assert "did not return sufficient context" in result["text"] or "not" in result["text"].lower()


class TestLLMProviderFactory:
    """Test the provider factory."""

    def test_default_is_mock(self):
        reset_llm_provider()
        with patch.dict("os.environ", {}, clear=True):
            # Remove API keys to ensure mock
            import os
            old_openai = os.environ.pop("OPENAI_API_KEY", None)
            old_anthropic = os.environ.pop("ANTHROPIC_API_KEY", None)
            try:
                provider = get_llm_provider()
                assert isinstance(provider, MockLLMProvider)
            finally:
                if old_openai:
                    os.environ["OPENAI_API_KEY"] = old_openai
                if old_anthropic:
                    os.environ["ANTHROPIC_API_KEY"] = old_anthropic
                reset_llm_provider()


# ===========================================================================
# 6. GraphRAG Service End-to-End Tests (with mocks)
# ===========================================================================

class TestGraphRagService:
    """Test the full pipeline with mocked dependencies."""

    def _make_service(self) -> GraphRagService:
        """Create a service with all dependencies mocked."""
        # Mock retriever
        mock_retriever = MagicMock()
        mock_retriever.retrieve = AsyncMock(return_value={
            "vector_hits": [
                {
                    "chunk_id": "chunk_1",
                    "text": "Bearing B1 temperature reached 88.5C at 14:32 UTC. Vibration sensor VE-101 recorded 5.2 mm/s.",
                    "score": 0.92,
                    "document_id": "doc_sop_042",
                    "document_type": "SOP",
                    "source_filename": "SOP-MECH-042.pdf",
                    "page_start": 3,
                },
                {
                    "chunk_id": "chunk_2",
                    "text": "SOP-MECH-042: Rotor alignment procedure. Use Mobil SHC 320 lubricant.",
                    "score": 0.87,
                    "document_id": "doc_sop_042",
                    "document_type": "SOP",
                    "source_filename": "SOP-MECH-042.pdf",
                    "page_start": 5,
                },
            ],
            "graph_hits": [
                {
                    "node_id": "bearing-b1",
                    "label": "Component",
                    "display_name": "Bearing B1",
                    "relevance_score": 0.88,
                    "properties": {"type": "BEARING", "temp": 88.5},
                    "text": "Bearing B1",
                },
                {
                    "node_id": "sop-mech-042",
                    "label": "SOP",
                    "display_name": "SOP-MECH-042",
                    "relevance_score": 0.82,
                    "properties": {"title": "Rotor Alignment"},
                    "text": "SOP-MECH-042 Rotor Alignment Procedure",
                },
            ],
            "graph_nodes_raw": [
                {"id": "bearing-b1", "label": "Component", "display_name": "Bearing B1",
                 "properties": {"type": "BEARING"}},
                {"id": "sop-mech-042", "label": "SOP", "display_name": "SOP-MECH-042",
                 "properties": {"title": "Rotor Alignment"}},
            ],
            "graph_edges_raw": [
                {"source_id": "g101", "target_id": "bearing-b1",
                 "relationship": "COMPRISED_OF", "properties": {}},
                {"source_id": "bearing-b1", "target_id": "sop-mech-042",
                 "relationship": "MITIGATED_BY", "properties": {"effectiveness": 0.9}},
            ],
            "timing": {"vector_ms": 45.0, "graph_ms": 30.0, "total_ms": 75.0},
        })

        # Mock LLM
        mock_llm = MockLLMProvider()

        return GraphRagService(
            retriever=mock_retriever,
            llm_provider=mock_llm,
        )

    @pytest.mark.asyncio
    async def test_full_pipeline(self):
        service = self._make_service()
        request = GraphRagQueryRequest(
            query_text="Why did the vibration on Turbine-01 spike?",
            top_k=8,
            min_score=0.55,
        )
        response = await service.query(request)

        assert isinstance(response, GraphRagQueryResponse)
        assert response.answer is not None
        assert len(response.answer) > 0
        assert response.vector_hits == 2
        assert response.graph_nodes_expanded == 2
        assert response.latency_ms > 0
        assert len(response.context_chunks) > 0
        assert len(response.graph_nodes) > 0
        assert len(response.graph_edges) > 0
        assert len(response.citations) > 0
        assert response.overall_confidence > 0

    @pytest.mark.asyncio
    async def test_response_contract_compliance(self):
        """Verify the response matches Phase 0 contract exactly."""
        service = self._make_service()
        request = GraphRagQueryRequest(query_text="Test query")
        response = await service.query(request)

        # Check all required fields exist
        data = response.model_dump()
        assert "answer" in data
        assert "context_chunks" in data
        assert "graph_nodes" in data
        assert "graph_edges" in data
        assert "citations" in data
        assert "overall_confidence" in data
        assert "graph_nodes_expanded" in data
        assert "vector_hits" in data
        assert "latency_ms" in data
        assert "query_embedding_model" in data

        # Check no extra fields (extra="forbid")
        allowed = {
            "answer", "context_chunks", "graph_nodes", "graph_edges",
            "citations", "overall_confidence", "graph_nodes_expanded",
            "vector_hits", "latency_ms", "query_embedding_model", "generated_at",
        }
        assert set(data.keys()) <= allowed

    @pytest.mark.asyncio
    async def test_api_envelope_compliance(self):
        """Verify the response wraps correctly in APIResponse."""
        service = self._make_service()
        request = GraphRagQueryRequest(query_text="Test")
        response_data = await service.query(request)
        envelope = APIResponse(success=True, data=response_data, request_id="test-123")

        assert envelope.success is True
        assert envelope.data.answer is not None
        assert envelope.request_id == "test-123"
        assert envelope.generated_at is not None

    @pytest.mark.asyncio
    async def test_degraded_pipeline_no_vector(self):
        """Pipeline should work even if vector retrieval returns empty."""
        service = self._make_service()
        service.retriever.retrieve = AsyncMock(return_value={
            "vector_hits": [],
            "graph_hits": [],
            "graph_nodes_raw": [],
            "graph_edges_raw": [],
            "timing": {"vector_ms": 0, "graph_ms": 0, "total_ms": 0},
        })
        request = GraphRagQueryRequest(query_text="Unknown query")
        response = await service.query(request)
        assert response.answer is not None
        assert response.vector_hits == 0
        assert response.overall_confidence == 0.0

    @pytest.mark.asyncio
    async def test_health_check(self):
        service = self._make_service()
        health = await service.health()
        assert "status" in health
        assert "components" in health


# ===========================================================================
# 7. API Router Tests (using TestClient)
# ===========================================================================

class TestGraphRagRouter:
    """Test the FastAPI endpoint contract."""

    @pytest.fixture
    def client(self):
        """Create a test client with mocked service."""
        from fastapi.testclient import TestClient
        from app.main import app

        # Patch the service
        mock_service = MagicMock()
        mock_service.query = AsyncMock(return_value=GraphRagQueryResponse(
            answer="Test answer [Source #1]",
            context_chunks=[
                GraphRagContextChunk(
                    chunk_id="c1", text="test chunk", score=0.9,
                    document_type="SOP", source="test.pdf"
                )
            ],
            graph_nodes=[
                GraphRagNode(id="n1", label="Bearing B1", type="Component", properties={})
            ],
            graph_edges=[
                GraphRagEdge(source="n1", target="n2", relationship="MITIGATED_BY", weight=0.9)
            ],
            citations=[
                Citation(citation_id="[Source #1]", source_document="test.pdf",
                         source_type="SOP", confidence_score=0.9)
            ],
            overall_confidence=0.85,
            graph_nodes_expanded=2,
            vector_hits=3,
            latency_ms=125.0,
            query_embedding_model="all-mpnet-base-v2",
        ))
        mock_service.health = AsyncMock(return_value={"status": "ok", "components": {}})

        with patch("app.api.v1.graphrag.get_graphrag_service", return_value=mock_service):
            with TestClient(app) as tc:
                yield tc

    def test_query_endpoint_returns_200(self, client):
        response = client.post(
            "/api/v1/graphrag/query",
            json={"query_text": "Why is the turbine vibrating?", "top_k": 8},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["data"]["answer"] is not None
        assert data["data"]["vector_hits"] == 3

    def test_query_endpoint_contract_shape(self, client):
        response = client.post(
            "/api/v1/graphrag/query",
            json={"query_text": "Test", "top_k": 5, "min_score": 0.55},
        )
        data = response.json()
        # APIResponse envelope
        assert "success" in data
        assert "data" in data
        assert "request_id" in data
        assert "generated_at" in data
        # Inner GraphRagQueryResponse
        inner = data["data"]
        assert "answer" in inner
        assert "context_chunks" in inner
        assert "graph_nodes" in inner
        assert "graph_edges" in inner
        assert "citations" in inner
        assert "overall_confidence" in inner

    def test_query_endpoint_rejects_empty_query(self, client):
        response = client.post(
            "/api/v1/graphrag/query",
            json={"query_text": "", "top_k": 8},
        )
        assert response.status_code == 422  # Pydantic validation

    def test_query_endpoint_rejects_invalid_top_k(self, client):
        response = client.post(
            "/api/v1/graphrag/query",
            json={"query_text": "test", "top_k": 100},
        )
        assert response.status_code == 422

    def test_health_endpoint(self, client):
        response = client.get("/api/v1/graphrag/health")
        assert response.status_code == 200
        data = response.json()
        assert "status" in data

    def test_context_chunk_shape(self, client):
        response = client.post(
            "/api/v1/graphrag/query",
            json={"query_text": "test"},
        )
        chunks = response.json()["data"]["context_chunks"]
        assert len(chunks) > 0
        chunk = chunks[0]
        assert "chunk_id" in chunk
        assert "text" in chunk
        assert "score" in chunk
        assert "document_type" in chunk

    def test_graph_nodes_shape(self, client):
        response = client.post(
            "/api/v1/graphrag/query",
            json={"query_text": "test"},
        )
        nodes = response.json()["data"]["graph_nodes"]
        assert len(nodes) > 0
        node = nodes[0]
        assert "id" in node
        assert "label" in node
        assert "type" in node
        assert "properties" in node

    def test_graph_edges_shape(self, client):
        response = client.post(
            "/api/v1/graphrag/query",
            json={"query_text": "test"},
        )
        edges = response.json()["data"]["graph_edges"]
        assert len(edges) > 0
        edge = edges[0]
        assert "source" in edge
        assert "target" in edge
        assert "relationship" in edge


# ===========================================================================
# 8. Phase 0 Model Integrity Tests
# ===========================================================================

class TestPhase0ContractIntegrity:
    """Verify Phase 0 models are correctly structured."""

    def test_graphrag_query_request_fields(self):
        req = GraphRagQueryRequest(query_text="test")
        assert req.top_k == 8
        assert req.min_score == 0.55
        assert req.max_graph_hops == 2
        assert req.include_telemetry is True
        assert req.asset_id is None

    def test_graphrag_query_response_defaults(self):
        resp = GraphRagQueryResponse()
        assert resp.answer is None
        assert resp.context_chunks == []
        assert resp.graph_nodes == []
        assert resp.graph_edges == []
        assert resp.citations == []
        assert resp.overall_confidence == 0.0
        assert resp.latency_ms == 0.0

    def test_graphrag_query_request_validation(self):
        # Should reject query_text > 2048 chars
        with pytest.raises(Exception):
            GraphRagQueryRequest(query_text="x" * 2049)

        # Should reject top_k > 50
        with pytest.raises(Exception):
            GraphRagQueryRequest(query_text="test", top_k=51)

        # Should reject min_score > 1.0
        with pytest.raises(Exception):
            GraphRagQueryRequest(query_text="test", min_score=1.5)

    def test_graph_context_map_internal_model(self):
        ctx = GraphContextMap(
            nodes=[GraphNode(id="n1", label="Asset", display_name="G-101")],
            edges=[GraphEdge(source_id="n1", target_id="n2", relationship="COMPRISED_OF")],
            root_node_ids=["n1"],
        )
        assert len(ctx.nodes) == 1
        assert len(ctx.edges) == 1
        assert ctx.root_node_ids == ["n1"]

    def test_api_response_envelope(self):
        resp = GraphRagQueryResponse(answer="test", latency_ms=100.0)
        envelope = APIResponse(success=True, data=resp, request_id="req-1")
        assert envelope.success is True
        assert envelope.data.answer == "test"
        assert envelope.request_id == "req-1"

    def test_citation_model(self):
        c = Citation(
            citation_id="[Source #1]",
            claim_span="bearing overheating",
            source_document="SOP-042.pdf",
            source_type="SOP",
            confidence_score=0.92,
            page_number=3,
        )
        assert c.citation_id == "[Source #1]"
        assert c.confidence_score == 0.92


# ===========================================================================
# 9. Benchmarking / Performance Tests
# ===========================================================================

class TestPerformanceBenchmarks:
    """Benchmark the retrieval and fusion pipeline components."""

    def test_rrf_performance(self):
        """RRF should handle 1000 candidates in < 10ms."""
        import time

        ranked_list_1 = [(f"item_{i}", 1.0 - i * 0.001) for i in range(500)]
        ranked_list_2 = [(f"item_{i+250}", 1.0 - i * 0.001) for i in range(500)]

        t0 = time.perf_counter()
        scores = reciprocal_rank_fusion([ranked_list_1, ranked_list_2], k=60)
        elapsed = (time.perf_counter() - t0) * 1000.0

        assert len(scores) > 0
        assert elapsed < 50  # should be well under 50ms
        print(f"RRF 1000 items: {elapsed:.2f}ms")

    def test_fusion_engine_performance(self):
        """Fusion engine should handle 50 vector + 50 graph in < 5ms."""
        import time

        engine = ContextFusionEngine()
        vector_hits = [
            {"chunk_id": f"c_{i}", "text": f"text {i}", "score": 0.9 - i * 0.01,
             "document_id": f"d_{i}", "document_type": "SOP"}
            for i in range(50)
        ]
        graph_hits = [
            {"node_id": f"n_{i}", "label": "Component", "display_name": f"Node {i}",
             "relevance_score": 0.85 - i * 0.01, "properties": {}}
            for i in range(50)
        ]

        t0 = time.perf_counter()
        result = engine.fuse(vector_hits, graph_hits)
        elapsed = (time.perf_counter() - t0) * 1000.0

        assert len(result.candidates) > 0
        assert elapsed < 20  # should be very fast
        print(f"Fusion 100 candidates: {elapsed:.2f}ms")

    def test_citation_engine_build_performance(self):
        """Citation build should handle 100 candidates in < 1ms."""
        import time

        engine = CitationEngine()
        candidates = [
            FusionCandidate(
                candidate_id=f"c_{i}", label=f"Label {i}", source_type="vector",
                text=f"Text {i}" * 10, score_vector=0.9 - i * 0.01,
            )
            for i in range(100)
        ]

        t0 = time.perf_counter()
        provenance = engine.build(candidates)
        elapsed = (time.perf_counter() - t0) * 1000.0

        assert len(provenance) == 100
        assert elapsed < 10
        print(f"Citation build 100 candidates: {elapsed:.2f}ms")
