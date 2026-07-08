"""
Phase 1 — Qdrant Vector Init Smoke Test
Verifies that collections are generated using the correct 768d mpnet dimensions.

Usage:
  docker run -d -p 6333:6333 -p 6334:6334 qdrant/qdrant
  python test_vector_init.py
"""
import os
import sys

# Load Phase 1 config (validates dimension mismatch on import)
try:
    from config import EMBEDDING_MODEL_NAME, VECTOR_DIMENSION, QDRANT_URL
    print(f"Phase 1 Config — Model: {EMBEDDING_MODEL_NAME} | Dim: {VECTOR_DIMENSION}")
except Exception as e:
    print(f"❌ Config validation failed: {e}")
    sys.exit(1)

# Try to use app.core.config if available
try:
    from app.core.config import get_settings
    settings = get_settings()
    print(f"App Settings — embedding_model_name={settings.embedding_model_name}, qdrant_vector_size={settings.qdrant_vector_size}")
    dim = settings.qdrant_vector_size
    qdrant_url = settings.qdrant_url
except Exception:
    # Fallback to env / config.py
    dim = VECTOR_DIMENSION
    qdrant_url = QDRANT_URL

from qdrant_client import QdrantClient
from qdrant_client.models import Distance, VectorParams

# Parse host/port from QDRANT_URL
# qdrant_url like http://localhost:6333
if "://" in qdrant_url:
    host_port = qdrant_url.split("://", 1)[1]
else:
    host_port = qdrant_url

if ":" in host_port:
    host, port_str = host_port.split(":", 1)
    port = int(port_str.strip("/"))
else:
    host = host_port
    port = 6333

client = QdrantClient(host=host, port=port)
collection_name = "telemetry_knowledge_test"

print(f"Connecting to Qdrant at {host}:{port} ...")
print(f"Emulating Phase 1 variables — dim={dim}")

try:
    client.recreate_collection(
        collection_name=collection_name,
        vectors_config=VectorParams(size=dim, distance=Distance.COSINE),
    )
    info = client.get_collection(collection_name=collection_name)
    vector_size = info.config.params.vectors.size
    print(f"✅ Success! Created collection '{collection_name}' with vector size: {vector_size}")
    
    if vector_size == 768:
        print("✅ Phase 1 Embedding Lock VERIFIED — 768d mpnet")
    else:
        print(f"⚠️  Unexpected vector size: {vector_size} (expected 768)")
    
    # cleanup
    client.delete_collection(collection_name=collection_name)
    print("Test collection cleaned up.")
    
except Exception as e:
    print(f"❌ Qdrant initialization failed: {e}")
    sys.exit(1)
