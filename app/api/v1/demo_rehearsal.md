# Phase 7 Demo Rehearsal Checklist

Use this checklist immediately before recording `docs/fallback_demo.mp4`.

## 1) Production readiness hard gates

```bash
# From repo root
python check_freeze.py
python phase7_demo_validator.py --base-url http://localhost:8000
```

The validator must complete **two full loops** back-to-back without restarting containers.
For local smoke testing only, you may skip production key validation:

```bash
python phase7_demo_validator.py --base-url http://localhost:8000 --no-strict-env
```

Do **not** use `--no-strict-env` for sign-off or fallback-video recording.

## 2) Warm the production GraphRAG / LLM path

Authenticate and export the token:

```bash
TOKEN=$(curl -s -X POST http://localhost:8000/api/v1/auth/login \
  -H "Content-Type: application/json" \
  -d '{"username":"demo_operator","password":"secure_password_2026"}' \
  | python -c 'import json,sys; d=json.load(sys.stdin); print(d.get("access_token") or d.get("data",{}).get("access_token"))')
```

Run the four rehearsal prompts below to clear cold-start latency and verify citation integrity.

### Rehearsed Question 1 — Operational Baseline

```bash
curl -X POST http://localhost:8000/api/v1/graphrag/query \
  -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" \
  -d '{"message": "What is the certified operational vibration threshold for machine07?"}'
```

### Rehearsed Question 2 — Maintenance History Context

```bash
curl -X POST http://localhost:8000/api/v1/graphrag/query \
  -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" \
  -d '{"message": "List all maintenance actions logged for machine07 during the Q1 shutdown."}'
```

### Rehearsed Question 3 — Component Failure Modes

```bash
curl -X POST http://localhost:8000/api/v1/graphrag/query \
  -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" \
  -d '{"message": "What are the secondary failure effects when a bearing seal leaks on centrifuge-02?"}'
```

### Critical Hallucination Defense Test — Out-of-Domain Prompt

```bash
curl -X POST http://localhost:8000/api/v1/graphrag/query \
  -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" \
  -d '{"message": "Give me a recipe for chocolate chip cookies."}'
```

Expected out-of-domain response:

> I do not possess domain information regarding recipes or non-industrial processes in my knowledge base.

## 3) OBS / Zoom recording sequence

1. Start containers from `iob-integration/`.
2. Confirm `LLM_PROVIDER` is `openai` or `anthropic` and production API quota is available.
3. Run `phase7_demo_validator.py` on-screen and let the success banner remain visible.
4. Demonstrate the four GraphRAG prompts above.
5. Demonstrate the graceful-degrade banner by forcing the frontend/gateway unavailable path:

```bash
curl -X POST http://localhost:8000/api/v1/chat \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -H "X-Force-AI-Unavailable: true" \
  -d '{"prompt":"What should I inspect first?","history":[]}'
```

The response must include:

```json
{
  "status": "AI_UNAVAILABLE",
  "ui_message": "Advanced analytics and AI chat are temporarily offline. Local rule-based telemetry monitoring remains operational."
}
```

6. Save the reviewed recording as `docs/fallback_demo.mp4`.

## Exit criteria

- [ ] `phase7_demo_validator.py` completes two sequential loops.
- [ ] AI responses have fresh timestamps, non-static risk scores, and non-placeholder XAI arrays.
- [ ] GraphRAG citations include valid source node/document links.
- [ ] Out-of-domain prompt refuses non-industrial content.
- [ ] Graceful-degrade envelope appears without raw 5xx/network errors.
- [ ] Fallback demo video is rendered and saved to `docs/fallback_demo.mp4`.
