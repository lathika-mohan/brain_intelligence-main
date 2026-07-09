# Phase 6 & 7 Demo Readiness — Worked Files Manifest

Generated for post-freeze stabilization, end-to-end demo validation, production graceful-degrade checks, and backup demo rehearsal.

## New files

| File | Purpose |
|---|---|
| `check_freeze.py` | Phase 6 post-freeze drift validator. Scans `ai_platform/`, current `app/`, and `iob-integration/gateway_app/` Python surfaces. |
| `phase7_demo_validator.py` | Phase 7 hard-gate runner: two sequential full user journeys, anti-stub checks, GraphRAG citation validation, alert resolve state machine, AI_UNAVAILABLE graceful-degrade checks, and production LLM env validation. |
| `docs/demo_rehearsal.md` | Backup demo video warm-up checklist with the four GraphRAG rehearsal prompts and expected hallucination-defense response. |
| `src/services/aiUnavailable.ts` | Shared frontend fallback envelope constant for AI outage messaging. |
| `PHASE6_7_DEMO_READINESS_WORKED_FILES_MANIFEST.md` | This manifest. |

## Modified files

| File | Change |
|---|---|
| `.env.example` | Phase 7 production rehearsal defaults now point to a live vendor provider (`openai`) while keeping API keys blank for local secret injection. |
| `iob-integration/docker-compose.yml` | AI platform receives vendor LLM environment variables from shell/`.env`; gateway defaults to strict `AI_UNAVAILABLE` degradation instead of silent AI stub fallback. |
| `iob-integration/gateway_app/main.py` | Added dashboard asset arrays, dynamic XAI feature generation, out-of-domain GraphRAG refusal, AI_UNAVAILABLE defensive envelope, chat proxy/fallback endpoints, and `/api/v1/alerts/resolve`. |
| `iob-integration/gateway_app/store.py` | Added resolved-alert state transition and active-alert filtering. |
| `app/api/v1/dashboard.py` | Standalone AI-service compatibility dashboard now exposes concrete asset arrays for Phase 7 validation. |
| `app/api/v1/alerts.py` | Added `/api/v1/alerts/resolve` and active-alert filtering for sequential demo loops. |
| `app/api/v1/graphrag.py` | Added deterministic out-of-domain refusal for recipe/non-industrial prompts. |
| `app/api/v1/predictive.py` | Replaced static fallback SHAP array with dynamic, timestamped feature impacts. |
| `src/services/chat.service.ts` | Chat catch-path now surfaces the same explicit AI_UNAVAILABLE message rather than a fabricated diagnostic answer. |

## Verification executed in this workspace

```bash
python -m py_compile check_freeze.py phase7_demo_validator.py \
  app/api/v1/dashboard.py app/api/v1/alerts.py app/api/v1/predictive.py app/api/v1/graphrag.py \
  iob-integration/gateway_app/main.py iob-integration/gateway_app/store.py

python check_freeze.py

# Local smoke run against gateway with production-key validation skipped only because this sandbox has no secrets:
python phase7_demo_validator.py --base-url http://127.0.0.1:8000 --no-strict-env --timeout 5 --short-timeout 1
```

Smoke result: two sequential loops passed; dynamic risk scores were `0.7336` then `0.7867`; graceful-degrade envelope check passed for predictive and chat endpoints.

> Production sign-off must run `python phase7_demo_validator.py --base-url http://localhost:8000` without `--no-strict-env`, with `LLM_PROVIDER=openai|anthropic` and a real runtime API key available.
