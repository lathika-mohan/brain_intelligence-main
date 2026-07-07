# AI Platform Operations Manual

This document is the authoritative technical reference for the maintenance and observation of the AI Intelligence Platform (Phase 12). It provides the DevOps team with all necessary procedures for environment setup, model retraining, and index management.

## 1. Environment & Orchestration Setup

### Prerequisites
* Docker & Docker Compose (v2.x+)
* Python 3.10+
* 16GB+ RAM recommended for local model training and GraphRAG operations.

### Core Services Orchestration
The AI platform relies on two primary data backends: Neo4j (Graph Database) and Qdrant (Vector Database).

```bash
# Start the core dependencies
docker-compose up -d neo4j qdrant
```

### Environment Variables
Ensure the `.env` file is properly configured. Critical AI variables include:

* `NEO4J_URI`: Connection string for Neo4j (e.g., `bolt://localhost:7687`)
* `NEO4J_USER` / `NEO4J_PASSWORD`: Credentials for the graph database.
* `QDRANT_URL`: URL for the vector database (e.g., `http://localhost:6333`).
* `OPENAI_API_KEY` (or other LLM provider): Key for generating embeddings and multi-agent routing.
* `MODEL_REGISTRY_PATH`: Local or shared volume path (e.g., `./models/registry`) for serialized ML models.

---

## 2. Triggering Model Retraining Cycles

Predictive models (XGBoost for RUL, Isolation Forest for Anomalies) need periodic retraining as new telemetry data arrives or when **Data Drift** is detected.

### Step-by-Step Retraining Procedure

1. **Ensure Telemetry Data is Available:**
   The training pipeline expects historical telemetry data (via CSV or data warehouse connection configured in `app.predictive.feature_engineering`).

2. **Run the Training Module:**
   Execute the centralized training script from the project root:
   ```bash
   python -m app.predictive.train_predictive_models
   ```
   
3. **Verify Model Artifacts:**
   Check the `models/registry` directory (or your configured path). You should see updated timestamps for:
   * `xgboost_rul_v1.json`
   * `isolation_forest_v1.joblib`
   * `model_evaluation_report.json`
   * `baseline_stats.json` (used for data drift detection)

4. **Hot-Reload the AI Service:**
   The FastAPI application needs to reload the models into memory.
   If running in Kubernetes or Docker, perform a rolling restart:
   ```bash
   kubectl rollout restart deployment/ai-service
   ```
   Or via the `/api/v1/ai/reload-models` endpoint (if exposed).

---

## 3. Graph Index & Constraint Rebuilds

Over time, or after massive batch ingestions, Neo4j indexes may need to be verified or rebuilt to maintain query throughput for GraphRAG operations.

### Rebuilding Procedure

1. **Access the Neo4j Cypher Shell:**
   ```bash
   docker exec -it <neo4j_container_id> cypher-shell -u neo4j -p <password>
   ```

2. **Verify Existing Constraints/Indexes:**
   ```cypher
   SHOW CONSTRAINTS;
   SHOW INDEXES;
   ```

3. **Programmatic Rebuild via App Schema Migration:**
   The application contains a schema migration utility (Phase 2) to enforce the ontology constraints.
   Run the setup script:
   ```bash
   python -m app.graph.schema_migrations
   ```
   *This ensures uniqueness on Node IDs (e.g., Machine, Component, Sensor) and rebuilds text indexes for fast vector-graph hybrid search.*

---

## 4. Performance Monitoring & Data Drift

### Benchmarking
Run the Locust suite to verify API latencies under load:
```bash
locust -f benchmarks/locustfile.py --host=http://localhost:8000
```
Target Budgets:
* `/predict`: p95 < 100ms
* `/query` (GraphRAG): p95 < 2500ms

### Data Drift Observation
The platform logs semantic data drift warnings (e.g., `Data Drift Detected in 'vibration'...`) when live telemetry deviates significantly from the `baseline_stats.json` snapshot captured during training. Monitor the application logs for `WARNING` level events emitted by `DataDriftChecker`. If drift occurs frequently (e.g., sustained over 24 hours), trigger a model retraining cycle.
