# PHASE 5 — Byte-Identical Relay Fix — Worked Files Manifest

**Goal:** Repair the byte-identical relay verification failure in isolation
(unrelated to the UI-router / contracts work in Phase 4).

## Files in this delivery

| File | Type | Purpose |
|------|------|---------|
| `iob-integration/gateway_app/payload_compare.py` | **new** | Dependency-free `compare_payloads()` + `assert_byte_identical()` — the relay verification primitive. |
| `iob-integration/gateway_app/_transparent_proxy_snippet.py` | **reference** | Exactly how to restore/expose `compare_payloads` from `transparent_proxy.py`, or when to delete the obsolete test. |
| `tests/test_phase5_byte_identical_relay.py` | **new** | Self-contained tests proving comparison behavior (identical, byte-flip, length, str/utf-8, headers, hop-by-hop, assert). |
| `docs/phase5_byte_identical_relay.md` | **new** | Integration + decision notes. |

## Verification (already run offline)

All 7 comparison cases pass — identical payloads, single-byte flip (offset
reported), length mismatch, str/utf-8 equivalence, header value diff, hop-by-hop
header tolerance, and the assert helper's failure reason. Body byte-equality is
checked first because that is the core relay guarantee.

## Task-by-task mapping

- **Inspect `transparent_proxy.py`** → I could not retrieve your nested source
  from outside GitHub (tree pages block automated access; the repo isn't indexed
  at file level), so this step needs your file. See "What I need" below.
- **Implement or restore `compare_payloads()`** → provided as a clean,
  dependency-free implementation with a precise failure report.
- **Otherwise remove the obsolete test** → covered as CASE C in the snippet, with
  the guard "only if the guarantee is truly proven elsewhere."
- **Verify relay comparison behavior** → the test suite + the offline run above.

## Decision: fix or delete?

I could not make this call for you without seeing `transparent_proxy.py` and
`tests/test_phase3_byte_identical_relay.py`. Default recommendation: **restore**
the function (CASE A/B) rather than delete the test — a transparent relay should
keep a live byte-identity check. Delete only if a checksum/probe in the relay
path already enforces it.

## What I need to turn this into an exact fix

Paste (or upload) these two files and I'll match the import path, signature, and
decide fix-vs-delete against your real code:

```bash
git show main:iob-integration/gateway_app/transparent_proxy.py
git show main:tests/test_phase3_byte_identical_relay.py
```
