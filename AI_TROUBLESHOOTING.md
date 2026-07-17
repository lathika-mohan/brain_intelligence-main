# AI Platform Troubleshooting Runbook

This runbook maps specific failure modes in the AI Intelligence Platform to clear, actionable remediation steps for platform administrators.

---

## 1. Vector Database (Qdrant) Errors

### **Error:** `Qdrant Collection Mismatch` or `CollectionNotFound`
**Symptom:** GraphRAG or semantic search endpoints return 500 errors, or the ingestion pipeline fails when inserting embeddings.
**Root Cause:** The target Qdrant collection does not exist, or the vector dimension size does not match the embedding model output (e.g., 1536 for OpenAI `text-embedding-3-small`).
**Remediation:**
1. Check the configured embedding model in `.env`.
2. Run the initialization script to recreate the collection with the correct schema:
   ```bash
   python -m app.vector.init_collection
   ```
3. Re-ingest the knowledge base documents to populate the new collection.

---

## 2. Graph Database (Neo4j) Errors

### **Error:** `ConstraintValidationFailed`
**Symptom:** Ingestion of new structural data fails.
**Root Cause:** The system attempted to create a node (e.g., `Machine` or `Component`) with an ID that already exists, but the query did not use a `MERGE` statement, violating the unique ID constraint.
**Remediation:**
1. Verify the ingestion script payload. Ensure unique entities are ingested via `MERGE` rather than `CREATE`.
2. To manually inspect the duplicate, run in Cypher:
   ```cypher
   MATCH (n:Machine {id: '<problematic_id>'}) RETURN n;
   ```
3. Clean up orphaned or duplicate nodes if the constraint was temporarily disabled:
   ```cypher
   MATCH (n:Machine) WITH n.id AS id, collect(n) AS nodes WHERE size(nodes) > 1 
   FOREACH (n in tail(nodes) | DETACH DELETE n);
   ```

### **Error:** `TransactionTimeout` or `DeadlockDetected`
**Symptom:** GraphRAG recursive queries timeout or lock up.
**Root Cause:** A Cypher query traversing a deeply connected graph hit an infinite loop or excessive branch factor (super-nodes).
**Remediation:**
1. Limit traversal depth in the GraphRAG service (e.g., `*1..3` instead of unbounded `*`).
2. Identify super-nodes (nodes with >10,000 relationships) and exclude them from generic traversals.
3. Restart the Neo4j container to clear hanging transactions.

---

## 3. Large Language Model (LLM) Errors

### **Error:** `ContextLengthExceeded`
**Symptom:** LangGraph routing fails, or GraphRAG returns an OpenAI API error regarding token limits.
**Root Cause:** The retrieved context (combined graph paths + vector chunks) exceeds the token window of the selected model.
**Remediation:**
1. Decrease the `top_k` retrieval parameter in `app.graphrag.service`.
2. Switch to a model with a larger context window in `.env` (e.g., move from an 8k context model to a 128k context model like `gpt-4o`).
3. Ensure the prompt template aggressively truncates context blocks.

---

## 4. Multi-Agent (LangGraph) Orchestration Errors

### **Error:** `GraphRecursionError` or Routing Timeouts
**Symptom:** The multi-agent workflow spins indefinitely and the `/api/v1/ai/query` endpoint times out.
**Root Cause:** A conditional edge in LangGraph is repeatedly routing back to the same node (e.g., `router -> tool -> router -> tool`) without resolving the goal.
**Remediation:**
1. Review `app.orchestration.routing`. Ensure the routing logic has a strict fallback to the `__end__` state if a tool fails more than once.
2. Check the `recursion_limit` parameter in the compiled graph execution and reduce it to fail faster (e.g., `recursion_limit=10`).

---

## 5. Predictive ML Errors

### **Error:** `FileNotFoundError: RUL model artifact missing`
**Symptom:** The `/api/v1/ai/predict` endpoint returns 500.
**Root Cause:** The application is attempting to load models from `MODEL_REGISTRY_PATH` but the files do not exist.
**Remediation:**
1. Verify the persistent volume mount in Docker/K8s.
2. If models are truly missing, trigger a retraining cycle:
   ```bash
   python -m app.predictive.train_predictive_models
   ```

### **Error:** `Model returned NaN` or `TypeError` during prediction
**Symptom:** Predictions fail silently or crash the worker.
**Root Cause:** The incoming telemetry data contains extreme outliers or unexpected data types (e.g., string instead of float) that the XGBoost/Isolation Forest pipelines cannot handle.
**Remediation:**
1. Check the data validation layer (Pydantic schema).
2. Look for `Data Drift Detected` warnings in the logs indicating sensor failure.
3. Replace corrupted sensor streams or apply imputation rules in `app.predictive.feature_engineering`.
