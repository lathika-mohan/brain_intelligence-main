# Phase 3 — Solo-Safe Consistency Audit (Member 3, AI Platform)

**Scope:** Internal consistency + demo-representativeness of *this* repo only.
No cross-member contract surface was touched. No frozen field was changed.

**Date:** 2026-07-08
**Repo:** `brain_intelligence-main` (AI Intelligence Platform, `app/`)
**Exit criteria:** Repo is internally consistent and demo-representative,
independent of everyone else. → **MET.**

---

## Executive summary

| # | Checklist item | Result | Action taken |
|---|---|---|---|
| 1 | Part 6 Stage-4 cuts (orchestration / decision depth / counterfactual) correctly scoped for demo; no frozen field silently changed | ✅ PASS | Verification only — none needed |
| 2 | Missing `PHASE7_WORKED_FILES_MANIFEST.md` | ✅ FIXED | Created (backfill, code unchanged) |
| 3 | `.env.example` `LLM_PROVIDER` default (mock vs real key) intentional | ✅ CONFIRMED | Added explicit demo-readiness note |
| 4 | AI service correctly has **no** auth middleware (Member 1 owns auth) | ✅ PASS | Verification only — none needed |

Only two files were written: `PHASE7_WORKED_FILES_MANIFEST.md` (new) and
`.env.example` (comment-only addition). Everything else was verified, not
modified — deliberately, because editing items 1 and 4 would *create* the very
problems this phase guards against (breaking a frozen field / building
something Member 1 owns).

---

## Item 1 — Part 6 Stage-4 cuts: scope + frozen-field integrity

**What "Stage-4 cuts" means here:** the demo scope for multi-agent
orchestration, decision-engine depth, and counterfactual/root-cause analysis.
The concern is *not* that these are under-built (they exceed demo scope) — it
is that later depth work must not have silently mutated a Phase 0 frozen field.

**Modules reviewed:**
- Orchestration: `app/orchestration/` (`service.py`, `agent_nodes.py`,
  `topology.py`, `routing.py`, `state.py`, `tools.py`, `utils.py`) — LangGraph
  multi-agent state graph, mounted under `/api/v1/ai/*`.
- Decision engine: `app/decision/` (`decision_service.py`, `rule_engine.py`,
  `risk_scorer.py`, `sop_matcher.py`).
- Counterfactual / root-cause depth: `app/predictive/xai_service.py`,
  `shap_engine.py`, `lime_engine.py` (SHAP/LIME attribution + root-cause
  synthesis — the repo's counterfactual-style "what drove this" analysis).

**Frozen-field check (executed):** compared live Pydantic model fields against
the frozen `docs/api_contracts.md` §1–§4 wire shapes.

```
RecommendationResponse: OK  missing_frozen=None  additive_extras=['decision_log','sop_steps']
InferenceResponse:      OK  missing_frozen=None  additive_extras=['anomalous_sensors']
ExplanationResponse:    OK  missing_frozen=None  additive_extras=None
GraphRagQueryResponse:  OK  (answer / citations / overall_confidence / latency_ms present)
```

**Finding:** ✅ Every frozen field is still present with its original name and
type. The only deltas are **additive, backward-compatible** fields
(`sop_steps`, `decision_log`, `anomalous_sensors`) that carry safe defaults and
do not alter the frozen envelope — consistent with the documented layering
pattern (Phase 6/7/8 adding on top of Phase 0 stubs). Response models declare
`extra="forbid"`, so no undeclared field can leak onto the wire.

**Conclusion:** Orchestration / decision / counterfactual depth is
appropriately scoped and demo-representative, and **nothing silently changed a
frozen field.** No code change made (making one would risk the freeze).

---

## Item 2 — Missing `PHASE7_WORKED_FILES_MANIFEST.md`

**Finding:** All other phases (1,2,3,4,5,6,8,9,10,11,12) ship a
`PHASE*_WORKED_FILES_MANIFEST.md`; Phase 7 (XAI) was the lone gap — even though
the XAI code (`app/predictive/xai_service.py`, `shap_engine.py`,
`lime_engine.py`, `app/api/v1/xai.py`, `tests/test_phase7_xai.py`) and its
Phase 8 downstream wiring were already present.

**Action:** Created `PHASE7_WORKED_FILES_MANIFEST.md` documenting the XAI
worked files exactly as they exist. **No source file was modified** to produce
it — this is documentation backfill only.

---

## Item 3 — `.env.example` `LLM_PROVIDER` default

**Finding:** `LLM_PROVIDER=mock` with `LLM_API_KEY=` empty. Verified at runtime:

```
llm_provider = 'mock'   llm_model_name = 'mock-llm-v1'   llm_api_key set? False
```

This is **intentional and correct for demo/CI**: the mock provider makes the
GraphRAG synthesis path fully deterministic and runnable with zero API keys and
zero network egress. No secret is present or committed. The switch to a real
provider is a pure runtime env change (`LLM_PROVIDER=openai|anthropic` +
`OPENAI_API_KEY`/`ANTHROPIC_API_KEY` in a local `.env`), read by
`app/graphrag/llm_client.py::get_llm_provider()`.

**Action:** Added an explicit demo-readiness note above the `LLM_PROVIDER` line
in `.env.example` (comment only — no default value changed) and flagged it for
the Phase 7 (Demo Readiness) checklist below.

---

## Item 4 — Auth-awareness: AI service must have NO auth middleware

Per `docs/team_coordination.md`, **Member 1 owns all auth**; the AI service is
proxied behind the enterprise gateway and must not implement its own auth.
`SERVICE_API_KEY` in `.env.example` is *reserved* for future gateway-issued
service-to-service auth — enforcement is explicitly out of scope here.

**Checks executed:**

1. No security imports anywhere in `app/`:
   `HTTPBearer / HTTPBasic / OAuth2 / APIKeyHeader / jwt / verify_token /
   get_current_user / require_auth / Security(...)` → **none found.**
2. Middleware stack at app boot → **`['CORSMiddleware']` only.**
3. No `401 / 403 / UNAUTHORIZED / FORBIDDEN` emitted by the AI service.
4. Every router `Depends(...)` resolves a **service/engine** (e.g.
   `get_xai_service`, `get_graphrag_engine`, `get_decision_engine`) — never an
   auth dependency.

**Finding:** ✅ The AI service correctly has **no auth middleware**. This
matches the plan; **no code was added** — building auth here would duplicate /
collide with Member 1's ownership, which is exactly what this check prevents.

---

## Verification commands (reproducible)

```bash
python -m venv .venv && . .venv/bin/activate
pip install pydantic==2.9.2 pydantic-settings==2.5.2 fastapi==0.115.0

# Config + LLM default
python -c "from app.core.config import get_settings as g; s=g(); \
print(s.llm_provider, s.llm_model_name, bool(s.llm_api_key))"

# Middleware stack (auth-awareness)
python -c "from app.main import app; \
print([m.cls.__name__ for m in app.user_middleware])"   # -> ['CORSMiddleware']

# Auth-import scan
grep -rEn "HTTPBearer|OAuth2|APIKeyHeader|verify_token|get_current_user|Security\(" app/ \
  || echo "NO AUTH IN AI SERVICE (correct)"
```

> Note: `numpy/qdrant/shap/torch`-dependent routers log benign
> `... router not mounted: No module named 'numpy'` warnings when only the
> lightweight audit deps are installed. This is the router aggregator's
> try/except guard working as designed — not a code fault. Install the full
> `requirements.txt` to mount every route.

---

## Files changed by this audit

| File | Change |
|---|---|
| `PHASE7_WORKED_FILES_MANIFEST.md` | **New** — backfilled missing manifest (documentation only). |
| `.env.example` | **Comment-only** — demo-readiness note above `LLM_PROVIDER` (default value unchanged). |
| `PHASE3_SOLO_SAFE_AUDIT.md` | **New** — this report. |

**No application/source code, no frozen Pydantic model, and no contract file
was modified.**
