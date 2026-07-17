# Phase 0 Execution Package — README

**For:** Lathika Member 3 AI/ML Knowledge Engineer  
**Duration:** 30-60 min non-coding

## What's Inside This Zip

```
Phase0_Lathika_Execution_Package.zip
├── PHASE0_ENGINEERING_EXECUTION_GUIDE.md (MAIN — the master guide)
├── artifacts/
│   ├── AI_SERVICE_INVENTORY.md
│   ├── CONTRACT_FREEZE_API_V1.yaml
│   ├── CONTRACT_FREEZE_PAYLOADS.json
│   ├── DUPLICATE_SCAFFOLD_AUDIT_REPORT.md
│   └── REPOSITORY_LAYOUT_AUDIT.md (manual + auto)
├── integration/
│   ├── gateway_relay_template.yaml (for Member 2)
│   └── gateway_to_ai_contract.md
└── fixed_wiring/
    ├── app/main.py (hardened internal-only + CORS locked)
    ├── app/api/v1/router.py (frozen, shim-flagged with PHASE0 warnings)
    ├── app/api/middleware/internal_only_guard.py (NEW — enforces internal token)
    ├── app/core/phase0_contracts.py (NEW — frozen Pydantic schemas)
    ├── scripts/phase0_audit.py (NEW — audit scanner)
    └── docs/PHASE0_CONTRACT_FREEZE.md
```

## How to Execute in 30-60 min

**Step 1 (5 min):** Extract zip into your brain_intelligence-main repo root, overwriting allowed paths. Keep existing model files untouched.

```bash
unzip Phase0_Lathika_Execution_Package.zip -d /tmp/phase0
cp -r /tmp/phase0/phase0-deliverables/* .   # or manually copy
```

**Step 2 (10 min):** Run audit tool

```bash
python scripts/phase0_audit.py --root . --out ./artifacts/
cat artifacts/REPOSITORY_LAYOUT_AUDIT_AUTO.md
```

**Step 3 (15 min):** Fill checklist Section 3 from main guide — verify tree, classification.

**Step 4 (10 min):** Duplicate scaffold audit — confirm src/ and public/ exist, fill DUPLICATE_SCAFFOLD_AUDIT_REPORT.md, copy team message template to Slack.

**Step 5 (15 min):** Freeze contracts — copy full JSON payloads from guide Section 4 into docs/PHASE0_CONTRACT_FREEZE.md (already provided in fixed_wiring). Share YAML + JSON with Member 2.

**Step 6 (5 min):** Exit criteria checklist — tick all boxes in guide Section 5.

## Integration with Existing Wiring

- **Existing `app/main.py` preserved** but hardened: added InternalOnlyGuardMiddleware, CORS lock logic, prod docs disabled. Backward compatible because in dev it bypasses with warning.
- **Existing `app/api/v1/router.py` preserved** but added explicit PHASE0 FLAGGED comments for shims. No route removed yet, to keep standalone tests passing in Phase 0.
- **New middleware** `internal_only_guard.py` validates `X-Internal-Service-Token` == `SERVICE_API_KEY`. Gateway must set this env same in both services.
- **New `phase0_contracts.py`** provides frozen Pydantic for cross-team import, matches existing `app/models/*`.
- **No model, embedding, vector code touched** — strictly contract layer.

## After Phase 0

- Commit: `docs/phase0/` folder with all artifacts
- Share: `CONTRACT_FREEZE_API_V1.yaml` to Member 2
- Phase 0.5: Remove shims, archive src/public to archive branch after approval.

## Exit

When all checkboxes PASS, run:

```bash
echo "Phase 0 Complete — $(date)" > docs/phase0/PHASE0_COMPLETION.txt
```

Then proceed to Phase 1.
