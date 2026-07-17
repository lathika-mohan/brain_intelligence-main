# Phase 3 — Solo-Safe Worked Files · Install / Overlay Guide

Unzip into your project root, **preserving paths**. Paths mirror the repo
exactly (`brain_intelligence-main/`), so files land in the right place.

## Contents

| File | Type | Action on your repo |
|---|---|---|
| `.env.example` | **EDITED** | Overwrite — adds a comment-only demo-readiness note above `LLM_PROVIDER` (default value `mock` unchanged). |
| `PHASE7_WORKED_FILES_MANIFEST.md` | **NEW** | Add — backfills the missing Phase 7 (XAI) manifest. |
| `PHASE3_SOLO_SAFE_AUDIT.md` | **NEW** | Add — full audit report for all 4 checklist items. |

## Why only these files?

The Phase 3 Solo-Safe checklist is mostly **verification**, not construction:

- **Item 1 (Stage-4 cuts / frozen fields):** verified clean — editing would
  risk breaking a frozen field. No change made.
- **Item 4 (no auth middleware):** verified clean — adding auth would collide
  with Member 1's ownership. No change made.
- **Item 2 (missing manifest):** the only genuine gap → new file.
- **Item 3 (LLM default):** intentional → documented in `.env.example`.

No application/source code and no frozen Pydantic contract was modified, by
design. See `PHASE3_SOLO_SAFE_AUDIT.md` for the executed evidence and
reproducible verification commands.

## Apply

```bash
# from your project root (the folder that contains .env.example)
unzip phase3_solo_safe_worked_files.zip
# review the diff on .env.example (comment-only), commit all three files
git add .env.example PHASE7_WORKED_FILES_MANIFEST.md PHASE3_SOLO_SAFE_AUDIT.md
git commit -m "Phase 3 solo-safe: backfill Phase 7 manifest, note LLM mock default, audit report"
```
