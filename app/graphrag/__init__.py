"""
Phase 5 — GraphRAG Engine Package
==================================
Hybrid intelligence platform that combines:
  • Vector semantic search (Qdrant — Phase 4)
  • Structural knowledge traversal (Neo4j — Phase 2)
  • Reciprocal Rank Fusion context merging
  • Citation & provenance tracking
  • Grounded LLM synthesis with strict anti-hallucination prompting

Public surface:
  - GraphRagService        — main orchestrator
  - ContextFusionEngine    — RRF / cross-modal fusion
  - CitationEngine         — provenance + citation tagging
  - PromptBuilder          — system-prompt templating
"""

from app.graphrag.graph_rag_service import GraphRagService, get_graphrag_service
from app.graphrag.context_fusion import ContextFusionEngine
from app.graphrag.citation_engine import CitationEngine
from app.graphrag.prompt_templates import PromptBuilder
from app.graphrag.retrieval import HybridRetriever

__all__ = [
    "GraphRagService",
    "get_graphrag_service",
    "ContextFusionEngine",
    "CitationEngine",
    "PromptBuilder",
    "HybridRetriever",
]
