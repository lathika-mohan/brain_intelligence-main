# Phase 3 — Gateway Transparent-Relay Audit (Root Cause & Fix)

**Scope:** Member 2 (Gateway) relay behaviour that violates the Phase 3
byte-identical contract. Member 3 (Lathika) owns the *detection* of this; the
one-line fix is Member 2's to apply via the included env-gated patch.

**Date:** 2026-07-17
**Finding class:** LATENT PAYLOAD MUTATION (masked by coincident heuristics)

---

## 1. The defect

`iob-integration/gateway_app/main.py::predictive_infer` is a **mutating**
relay. On a successful upstream call it overwrites the AI service's
authoritative fields with gateway-local heuristics:

```python
# CURRENT behaviour (gateway_app/main.py):
if proxy_result and isinstance(proxy_result, dict):
    data = proxy_result.get("data")
    ...
    if "data" in proxy_result:
        if isinstance(proxy_result["data"], dict):
            proxy_result["data"]["risk_score"] = risk_score   # ❌ WARP (heuristic)
        proxy_result["risk_score"] = risk_score               # ❌ WARP (heuristic)
        return proxy_result
```

This means the gateway is **not** a transparent proxy: it fabricates
`risk_score` / `failure_probability` from its own `_compute_risk_score()` and
stamps them over the AI service's values, then returns the payload as if it
were the AI's.

## 2. Why it is masked today (and therefore dangerous)

The gateway's `_compute_risk_score()` and the AI service's
`_compute_risk_from_features()` are **byte-for-byte the same heuristic**:

```python
# identical in BOTH services:
vib_norm  = min(1.0, max(0.0, (vib - 1.0) / 7.0))
temp_norm = min(1.0, max(0.0, (temp - 60.0) / 60.0))
risk = vib_norm * 0.55 + temp_norm * 0.45
if vib > 4.0 and temp > 85: risk = min(0.97, risk + 0.25)
```

So for the same features both sides produce the same number, and a naive
byte-comparison of `risk_score` **passes**. The mutation only becomes visible
once the AI service returns a real model-derived score that differs from the
heuristic — at which point the gateway would silently overwrite it. A gate that
passes today can fail in production. Phase 3 exists to make this falsifiable.

## 3. The fix (additive, env-gated, Member 2 applies)

### 3.1 `iob-integration/gateway_app/transparent_proxy.py` (NEW)

A non-mutating relay and the single shared `compare_payloads` comparator used
across the whole stack (gateway self-test + Phase 3 matrix + unit tests). On a
successful upstream call it returns the JSON body **unchanged** — no
`setdefault`, no overwrite, no merge.

### 3.2 `iob-integration/gateway_app_patch/phase3_main_patch.diff` (NEW)

A surgical patch that gates the transparent relay behind
`PHASE3_TRANSPARENT_RELAY`. Production behaviour is **unchanged** when the flag
is off. When on (as set in `docker-compose.phase3.yml`), the predictive relay
returns the upstream payload verbatim:

```python
# AFTER patch (gateway_app/main.py):
from .transparent_proxy import transparent_relay_enabled, relay_passthrough

async def _try_proxy_ai(method, path, json_body=None, timeout=4.0):
    if transparent_relay_enabled():
        return await relay_passthrough(method, path, json_body, timeout)
    ...  # legacy mutating path unchanged

# in predictive_infer:
if transparent_relay_enabled() and proxy_result and isinstance(proxy_result, dict):
    return proxy_result   # byte-for-byte upstream payload, no risk_score overwrite
```

## 4. Detection evidence (Phase 3 Task 5–7)

`phase3_byte_identical_relay.py` fires the identical deterministic request at
both transports in parallel and grades every property on value + type +
presence. With the legacy gateway it would emit:

| Property | Direct | Gateway | Byte-Identical | Reason |
|---|---|---|---|---|
| `data.risk_score` | `0.8543` (model) | `0.5` (heuristic) | ❌ NO | VALUE_MISMATCH |
| `risk_score` (top) | `0.8543` | `0.5` | ❌ NO | VALUE_MISMATCH |

With the transparent relay armed, both columns are identical and the gate is
green. Either way the audit is **honest** — the gate does not pass on luck.

## 5. Unit-test coverage

`tests/test_phase3_byte_identical_relay.py` (7 tests, pure/no-network) proves
the comparator detects: value warp, type-cast drift, field addition, field
drop, numeric-precision rounding, and that volatile keys may drift in value but
not in type.

```bash
PYTHONPATH=iob-integration python -m pytest tests/test_phase3_byte_identical_relay.py -q
# .......  7 passed
```

## 6. Conclusion

The gateway's current relay is a latent contract violator masked by coincident
heuristics. Phase 3 makes it falsifiable and provides the additive,
env-gated, reversible fix. **No AI-engine source (`app/`) is modified.**
