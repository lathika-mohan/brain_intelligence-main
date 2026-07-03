# Phase 5 — GraphRAG Engine: Worked Files Manifest

## Summary
Phase 5 implements the complete hybrid intelligence platform that powers the
existing `GraphRagPanel.tsx` frontend. The engine coordinates parallel retrieval
from Qdrant (vector) and Neo4j (graph), fuses context via Reciprocal Rank Fusion
(RRF), builds grounded LLM prompts with citation enforcement, and returns
contract-compliant payloads.

## New Files Created

### Core Engine (`app/graphrag/`)
| File | Description |
|------|-------------|
| `app/graphrag/__init__.py` | Package init with public API exports |
| `app/graphrag/context_fusion.py` | RRF fusion algorithm + weighted linear combination |
| `app/graphrag/citation_engine.py` | Provenance tracking, citation tagging, extraction |
| `app/graphrag/prompt_templates.py` | Grounded system prompts with anti-hallucination constraints |
| `app/graphrag/retrieval.py` | Hybrid retrieval layer (Qdrant + Neo4j parallel fetch) |
| `app/graphrag/llm_client.py` | LLM provider interface (OpenAI, Anthropic, Mock) |
| `app/graphrag/graph_rag_service.py` | Main orchestrator tying all components together |

### API Layer
| File | Description |
|------|-------------|
| `app/api/v1/graphrag.py` | FastAPI router with /query, /health, /diagnose endpoints |

### Tests
| File | Description |
|------|-------------|
| `tests/test_phase5_graphrag.py` | 58 pytest tests covering all engine components |

## Modified Files

| File | Change |
|------|--------|
| `app/models/graphrag.py` | Added `Citation`, `GraphContextMap`, `GraphNode`, `GraphEdge` models |
| `app/api/v1/router.py` | Updated to wire Phase 5 graphrag router as primary endpoint |
| `app/core/config.py` | Added LLM provider settings + Phase 5 tuning parameters |
| `requirements.txt` | Added Phase 5 dependency notes |
| `.env.example` | Added LLM_PROVIDER, LLM_MODEL_NAME, RRF_K, etc. |

## Endpoints Registered

| Method | Path | Description |
|--------|------|-------------|
| POST | `/api/v1/graphrag/query` | Main GraphRAG hybrid query endpoint |
| GET | `/api/v1/graphrag/health` | Health check for all subsystems |
| POST | `/api/v1/graphrag/diagnose` | Diagnostic endpoint (retrieval without LLM) |

## Contract Compliance

- **Request**: `GraphRagQueryRequest` — Phase 0 frozen contract
- **Response**: `GraphRagQueryResponse` wrapped in `APIResponse[data]`
- **Frontend**: Zero modifications to `GraphRagPanel.tsx` — payload matches expected shape
- **Citations**: Every claim in the LLM answer must reference `[Source #N]` tags

## Test Results

```
58 passed, 0 failed (0.52s)
```

Test categories:
1. Context Fusion Engine (RRF, weighted, overlap) — 10 tests
2. Citation Engine (tagging, extraction, provenance) — 10 tests
3. Prompt Builder (system prompts, citation validation) — 7 tests
4. Hybrid Retriever (entity anchors, graph serialisation) — 6 tests
5. LLM Client (mock provider, factory) — 3 tests
6. GraphRAG Service (end-to-end pipeline) — 5 tests
7. API Router (endpoint contracts) — 8 tests
8. Phase 0 Model Integrity — 6 tests
9. Performance Benchmarks — 3 tests

## Architecture

```
User Query
    │
    ▼
┌─────────────────────────────────────┐
│         GraphRagService             │
│   (graph_rag_service.py)            │
├─────────────────────────────────────┤
│                                     │
│  ┌─────────────┐  ┌──────────────┐  │
│  │   Qdrant    │  │    Neo4j     │  │
│  │  (Vector)   │  │   (Graph)    │  │
│  └──────┬──────┘  └──────┬───────┘  │
│         │                │          │
│         ▼                ▼          │
│  ┌─────────────────────────────┐    │
│  │   ContextFusionEngine       │    │
│  │   (RRF / Weighted)          │    │
│  └─────────────┬───────────────┘    │
│                │                    │
│                ▼                    │
│  ┌─────────────────────────────┐    │
│  │    CitationEngine           │    │
│  │    (Provenance Tracking)    │    │
│  └─────────────┬───────────────┘    │
│                │                    │
│                ▼                    │
│  ┌─────────────────────────────┐    │
│  │    PromptBuilder            │    │
│  │    (Grounded System Prompt) │    │
│  └─────────────┬───────────────┘    │
│                │                    │
│                ▼                    │
│  ┌─────────────────────────────┐    │
│  │    LLMProvider              │    │
│  │    (OpenAI/Anthropic/Mock)  │    │
│  └─────────────┬───────────────┘    │
│                │                    │
│                ▼                    │
│     GraphRagQueryResponse           │
│     (Phase 0 Contract)              │
└─────────────────────────────────────┘
```

## Integration Notes

1. **No frontend changes required**: The `GraphRagPanel.tsx` component already
   expects the `GraphRagQueryResponse` shape. The Phase 5 engine produces this
   exactly.

2. **Graceful degradation**: If Neo4j is unavailable, the engine still returns
   vector-only results. If Qdrant is unavailable, it returns graph-only results.
   If both fail, it returns a helpful fallback message.

3. **LLM provider selection**: Set `LLM_PROVIDER=openai` and `OPENAI_API_KEY`
   for production. Default is `mock` for development/testing.

4. **Performance**: Full pipeline (retrieval → fusion → LLM) completes in
   < 500ms for typical queries when both databases are local.
