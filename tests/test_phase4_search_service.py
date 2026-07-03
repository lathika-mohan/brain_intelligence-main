"""
Phase 4 — Search service filtering & score thresholding tests
"""

import pytest
from unittest.mock import MagicMock

from app.vector.search_service import VectorSearchService
from app.vector.models import SearchFilters


def make_mock_service():
    svc = VectorSearchService.__new__(VectorSearchService)
    # bypass __init__
    svc.client = MagicMock()
    svc.collection_name = "operational_knowledge_v4"
    svc.score_threshold = 0.70
    svc.default_top_k = 8
    # mock embedding
    emb = MagicMock()
    emb.model_name = "sentence-transformers/all-mpnet-base-v2"
    emb.encode_query.return_value = [0.1] * 768
    import numpy as np
    emb.encode_query.return_value = np.array([0.1]*768, dtype=np.float32)
    svc.embedding = emb
    return svc


def test_build_qdrant_filter_single():
    svc = make_mock_service()
    f = SearchFilters(document_type="SOP", asset_type=["PUMP", "MOTOR"])
    qf = svc.build_qdrant_filter(f)
    assert qf is not None
    assert len(qf.must) >= 2
    keys = [c.key for c in qf.must]
    assert "document_type" in keys
    assert "asset_type" in keys


def test_build_qdrant_filter_empty():
    svc = make_mock_service()
    qf = svc.build_qdrant_filter(SearchFilters())
    assert qf is None


def test_build_qdrant_filter_numeric_range():
    svc = make_mock_service()
    f = SearchFilters(min_token_count=100, max_token_count=800)
    qf = svc.build_qdrant_filter(f)
    assert qf is not None
    # find token_count condition
    token_conds = [c for c in qf.must if c.key == "token_count"]
    assert len(token_conds) == 1
    assert token_conds[0].range.gte == 100
    assert token_conds[0].range.lte == 800


@pytest.mark.asyncio
async def test_semantic_search_thresholding():
    svc = make_mock_service()
    # mock qdrant search return
    class Pt:
        def __init__(self, score, payload):
            self.id = payload.get("chunk_id", "x")
            self.score = score
            self.payload = payload

    mock_points = [
        Pt(0.92, {"chunk_id": "c1", "document_id": "d1", "document_type": "SOP", "text": "A"}),
        Pt(0.65, {"chunk_id": "c2", "document_id": "d1", "document_type": "SOP", "text": "B"}),  # below threshold
        Pt(0.81, {"chunk_id": "c3", "document_id": "d2", "document_type": "MANUAL", "text": "C"}),
    ]
    svc.client.search.return_value = mock_points

    resp = await svc.semantic_search("test query", top_k=5, score_threshold=0.70)
    # should filter out 0.65
    assert resp.returned == 2
    assert all(r.score >= 0.70 for r in resp.results)
    assert resp.results[0].chunk_id == "c1"


@pytest.mark.asyncio
async def test_semantic_search_empty_query_raises():
    svc = make_mock_service()
    with pytest.raises(ValueError):
        await svc.semantic_search("   ", top_k=5)
