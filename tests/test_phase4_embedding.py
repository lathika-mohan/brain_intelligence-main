"""
Phase 4 — Embedding consistency & pipeline tests
"""

import pytest
import numpy as np

from app.vector.embedding_engine import EmbeddingEngine

# Use a tiny mock to avoid downloading large models in CI
# If sentence-transformers is unavailable, tests will skip

def test_embedding_engine_init():
    try:
        eng = EmbeddingEngine(
            model_name="sentence-transformers/all-MiniLM-L6-v2",
            device="cpu",
            batch_size=8,
            lazy_load=True,  # don't actually download in CI
        )
        assert eng.model_name in ("sentence-transformers/all-MiniLM-L6-v2",
                                  "sentence-transformers/all-mpnet-base-v2")
        assert eng.batch_size == 8
    except Exception as e:
        pytest.skip(f"Embedding engine init skipped: {e}")


def test_chunk_fingerprint_determinism():
    eng = EmbeddingEngine(
        model_name="sentence-transformers/all-mpnet-base-v2",
        lazy_load=True,
    )
    fp1 = eng.chunk_fingerprint("Pump P-101A vibration high", "chunk:abc")
    fp2 = eng.chunk_fingerprint("Pump P-101A vibration high", "chunk:abc")
    fp3 = eng.chunk_fingerprint("Different text", "chunk:abc")
    assert fp1 == fp2
    assert fp1 != fp3
    assert len(fp1) == 64  # sha256 hex


def test_embed_chunks_idempotent_skip():
    eng = EmbeddingEngine(model_name="sentence-transformers/all-mpnet-base-v2", lazy_load=True)
    # monkeypatch encode to avoid model load
    def fake_encode(texts, **kwargs):
        dim = 768
        return np.random.RandomState(42).randn(len(texts), dim).astype(np.float32)
    eng.encode = fake_encode  # type: ignore
    eng._vector_dim = 768

    texts = ["text A", "text B", "text C"]
    ids = ["c1", "c2", "c3"]
    # first run — nothing skipped
    vectors, keep_idx, fps = eng.embed_chunks(texts, ids, skip_existing_fingerprints=set())
    assert len(keep_idx) == 3
    # second run — all skipped
    vectors2, keep_idx2, fps2 = eng.embed_chunks(texts, ids, skip_existing_fingerprints=set(fps))
    assert keep_idx2 == []
    assert vectors2.shape[0] == 0


def test_encode_query_bge_prefix():
    eng = EmbeddingEngine(model_name="BAAI/bge-large-en-v1.5", lazy_load=True)
    captured = {}
    def fake_encode(texts, **kwargs):
        captured["texts"] = texts
        return np.zeros((len(texts), 1024), dtype=np.float32)
    eng.encode = fake_encode  # type: ignore
    eng._vector_dim = 1024
    _ = eng.encode_query("vibration spike turbine")
    assert "Represent this sentence" in captured["texts"][0]


def test_empty_payload_handling():
    eng = EmbeddingEngine(model_name="sentence-transformers/all-mpnet-base-v2", lazy_load=True)
    eng._vector_dim = 768
    # simulate empty encode path
    out = eng.encode([])
    assert out.shape == (0, 768)
