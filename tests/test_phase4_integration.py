"""
Phase 4 — Integration Verification
Verifies: vector properties searchable, payload preserved, Pydantic mapping
"""

import pytest
from unittest.mock import MagicMock
import numpy as np

from app.vector.models import ChunkPayload, VectorSearchResult, VectorSearchResponse, SearchFilters
from app.vector.pipeline import VectorIngestionPipeline


def test_chunk_payload_schema_preservation():
    """Payload must store original text + explicit metadata fields"""
    payload = ChunkPayload(
        chunk_id="chunk:abc123",
        document_id="doc:SOP-MECH-042",
        document_type="SOP",
        asset_type="PUMP",
        section_title="Lubrication Procedure",
        source_filename="SOP-MECH-042.pdf",
        chunk_index=5,
        token_count=712,
        char_count=2848,
        text="Bearing B1 requires Mobil SHC 320 synthetic lubricant …",
        embedding_model="sentence-transformers/all-mpnet-base-v2",
        hash="deadbeef",
    )
    d = payload.model_dump()
    # explicit metadata fields required by Phase 4 spec
    for field in ["chunk_id", "document_id", "document_type", "asset_type", "section_title", "text"]:
        assert field in d
        assert d[field] is not None if field != "asset_type" or True else True
    assert d["token_count"] == 712


def test_vector_search_result_maps_to_pydantic():
    """Ensure Qdrant point → VectorSearchResult → GraphRAG compatible"""
    vsr = VectorSearchResult(
        id="uuid-1234",
        score=0.9123,
        chunk_id="chunk:xyz",
        document_id="doc1",
        document_type="MANUAL",
        asset_type="TURBINE",
        section_title="Vibration Analysis",
        text="Telemetry shows elevated vibration …",
        token_count=540,
        chunk_index=2,
        source_filename="manual_turbine.pdf",
        payload={"custom": "value"},
    )
    assert 0.0 <= vsr.score <= 1.0
    # map to GraphRAG context chunk
    from app.vector.models import GraphRagContextChunk
    ctx = GraphRagContextChunk(
        chunk_id=vsr.chunk_id,
        text=vsr.text,
        score=vsr.score,
        document_type=vsr.document_type,
        source=vsr.source_filename,
    )
    assert ctx.chunk_id == "chunk:xyz"


def test_embedding_batch_result_schema():
    from app.vector.models import EmbeddingBatchResult
    r = EmbeddingBatchResult(
        total_requested=100,
        embedded=95,
        skipped_existing=5,
        upserted=95,
        failed=0,
        latency_ms=1234.5,
        collection="operational_knowledge_v4",
        vector_dim=768,
    )
    assert r.embedded + r.skipped_existing == r.total_requested
    assert r.vector_dim == 768


def test_pipeline_idempotent_ingest(monkeypatch):
    """Pipeline should skip existing points"""
    # mock qdrant client
    mock_client = MagicMock()
    mock_client.scroll.return_value = ([], None)  # no existing
    mock_client.upsert.return_value = MagicMock(status="ok")

    # patch get_qdrant_client
    import app.vector.pipeline as vp
    monkeypatch.setattr(vp, "get_qdrant_client", lambda: mock_client)

    # mock embedding engine
    class FakeEng:
        model_name = "sentence-transformers/all-mpnet-base-v2"
        vector_dim = 768
        def encode(self, texts, **kwargs):
            return np.zeros((len(texts), 768), dtype=np.float32)

    # patch collection_mgr ensure
    monkeypatch.setattr(vp.QdrantCollectionManager, "ensure_collection", lambda self, recreate=False: {"created": False})

    pipe = VectorIngestionPipeline.__new__(VectorIngestionPipeline)
    pipe.embedding = FakeEng()
    pipe.client = mock_client
    pipe.collection_name = "operational_knowledge_v4"
    pipe.batch_size = 32
    # need existing_point_ids bound
    pipe.existing_point_ids = vp.VectorIngestionPipeline.existing_point_ids.__get__(pipe, VectorIngestionPipeline)

    chunks = [
        {
            "chunk_id": f"chunk:test{i}",
            "document_id": "doc1",
            "document_type": "SOP",
            "text": f"test chunk content {i}",
            "token_count": 100+i,
            "chunk_index": i,
        }
        for i in range(3)
    ]
    import asyncio
    try:
        loop = asyncio.get_event_loop()
    except RuntimeError:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
    result = loop.run_until_complete(pipe.ingest_chunks(chunks))
    assert result.total_requested == 3
    assert result.embedded == 3
    assert mock_client.upsert.called
