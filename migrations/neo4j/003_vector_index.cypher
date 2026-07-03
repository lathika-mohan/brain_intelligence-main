// ===========================================================================
// Phase 2 — Native VECTOR indexes for hybrid semantic traversal
// ---------------------------------------------------------------------------
// Community 5.11+ / Enterprise safe. Indexes are created before `embedding` is populated.
// Generated from app/graph/schema_migrations.py — edit the registry, not here.
// ===========================================================================

CREATE VECTOR INDEX vector_FailureMode_embedding IF NOT EXISTS FOR (n:`FailureMode`) ON (n.embedding) OPTIONS {indexConfig: {`vector.dimensions`: 384, `vector.similarity_function`: 'cosine'}};

CREATE VECTOR INDEX vector_SOPStep_embedding IF NOT EXISTS FOR (n:`SOPStep`) ON (n.embedding) OPTIONS {indexConfig: {`vector.dimensions`: 384, `vector.similarity_function`: 'cosine'}};
