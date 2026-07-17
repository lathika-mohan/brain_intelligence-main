# Drop-in Fixed Wiring — Phase 0

This folder mirrors your repo structure. Copy into brain_intelligence-main root:

```bash
cp app/main.py /path/to/brain_intelligence-main/app/main.py
cp app/api/v1/router.py /path/to/brain_intelligence-main/app/api/v1/router.py
cp app/api/middleware/internal_only_guard.py /path/to/brain_intelligence-main/app/api/middleware/internal_only_guard.py
cp app/core/phase0_contracts.py /path/to/brain_intelligence-main/app/core/phase0_contracts.py
cp scripts/phase0_audit.py /path/to/brain_intelligence-main/scripts/phase0_audit.py
cp docs/PHASE0_CONTRACT_FREEZE.md /path/to/brain_intelligence-main/docs/
# etc for docs/phase0 and integration
```

All files are backward compatible with existing wiring observed in https://github.com/lathika-mohan/brain_intelligence-main (main.py, router.py, predictive, graphrag).

Embedding lock: 768d all-mpnet-base-v2 enforced.
Single Gateway: Frontend -> Gateway -> brain_intelligence internal-only.
