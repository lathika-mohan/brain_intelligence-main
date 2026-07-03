"""
Phase 4 — Retrieval Benchmarking Suite
Measures p95/p99 latencies, asserts sub-50ms target (mocked — real Qdrant will vary)
"""

import pytest
import time
import statistics
from unittest.mock import MagicMock

from app.vector.search_service import VectorSearchService


@pytest.mark.asyncio
async def test_retrieval_latency_benchmark():
    """
    Execute standard operational queries against mocked vector collection,
    measure p95/p99, assert < 50ms target for mocked in-memory path.
    """
    svc = VectorSearchService.__new__(VectorSearchService)
    svc.client = MagicMock()
    svc.collection_name = "operational_knowledge_v4"
    svc.score_threshold = 0.70
    svc.default_top_k = 8

    # mock embedding fast
    import numpy as np
    emb = MagicMock()
    emb.model_name = "sentence-transformers/all-mpnet-base-v2"
    emb.encode_query.side_effect = lambda q: np.zeros(768, dtype=np.float32)
    svc.embedding = emb

    # mock search — instant
    class Pt:
        def __init__(self, i):
            self.id = f"p{i}"
            self.score = 0.88
            self.payload = {
                "chunk_id": f"chunk:{i}",
                "document_id": "doc1",
                "document_type": "SOP",
                "text": "mock result",
            }
    svc.client.search.return_value = [Pt(i) for i in range(8)]
    # need build_qdrant_filter method bound
    from app.vector.search_service import VectorSearchService as VSS
    svc.build_qdrant_filter = VSS.build_qdrant_filter.__get__(svc, VSS)

    queries = [
        "vibration spike turbine-01 bearing wear",
        "lubrication procedure bearing B1 SOP-MECH-042",
        "compressor surge failure modes C-204",
        "pump P-101A cavitation symptoms",
        "motor M-205 overheating root cause",
        "emergency shutdown procedure turbine",
        "preventive maintenance checklist pump",
        "alignment tolerance shaft coupling",
        "oil analysis report gearbox",
        "safety hazard lockout tagout",
    ]

    latencies = []
    for q in queries * 3:  # 30 runs
        t0 = time.perf_counter()
        resp = await svc.semantic_search(q, top_k=8)
        lat = (time.perf_counter() - t0) * 1000
        latencies.append(lat)
        assert resp.returned == 8

    latencies_sorted = sorted(latencies)
    n = len(latencies_sorted)
    p50 = latencies_sorted[int(n*0.5)]
    p95 = latencies_sorted[int(n*0.95)]
    p99 = latencies_sorted[int(n*0.99)] if n > 1 else latencies_sorted[-1]

    print(f"\nBenchmark (mocked): n={n} p50={p50:.2f}ms p95={p95:.2f}ms p99={p99:.2f}ms")

    # mocked path should be <50ms easily
    assert p95 < 50.0, f"p95 {p95:.2f}ms exceeds 50ms target"
    assert p99 < 100.0


def test_qdrant_payload_index_coverage():
    """Ensure payload indexes are defined for highly queried categorical metadata"""
    from app.vector.schema import PAYLOAD_INDEXED_FIELDS
    required = {"document_type", "asset_type", "chunk_id", "document_id"}
    assert required.issubset(set(PAYLOAD_INDEXED_FIELDS)), "Missing required payload indexes"
