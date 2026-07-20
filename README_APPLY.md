# How to apply this Phase 1 delivery to your `brain_intelligence-main` clone

1. Unzip this archive **at the root of your repo** (so `app/...` and
   `tests/...` land in the right place):

   ```bash
   cd /path/to/brain_intelligence-main
   unzip phase1_common_infrastructure_worked_files.zip -d .
   ```

   This will:
   - **Add** `app/ai_service/common/__init__.py`, `schemas.py`,
     `responses.py`, `middleware.py` (new package).
   - **Overwrite** `app/ai_service/integration/ui_router.py` (worked file —
     wired against the new common package; see the manifest for the
     exact diff summary).
   - **Add** `tests/test_phase1_common_infrastructure.py` (new test suite
     for the common package).

2. Install the (already-pinned) dependencies if you don't already have a
   working venv for this repo:

   ```bash
   python -m venv .venv && . .venv/bin/activate
   pip install fastapi==0.115.0 "uvicorn[standard]==0.32.0" pydantic==2.9.2 \
               pydantic-settings==2.5.2 httpx==0.27.2 orjson==3.10.7 \
               python-dotenv==1.0.1 pytest==8.3.3 pytest-asyncio==0.24.0 \
               numpy==1.26.4 pandas==2.2.3
   ```

3. Run the target contract test (must stay green — zero regressions):

   ```bash
   pytest tests/test_phase11_ui_router_contract.py -v
   # expect: 24 passed
   ```

4. Run the new Phase 1 unit/e2e suite:

   ```bash
   pytest tests/test_phase1_common_infrastructure.py -v
   # expect: 20 passed
   ```

5. (Optional) Full sibling regression check:

   ```bash
   pytest tests/ -q --ignore=tests/test_phase12_ml_models.py \
                     --ignore=tests/test_phase5_e2e.py \
                     --ignore=tests/test_phase6_predictive.py \
                     --ignore=tests/test_phase7_xai.py \
                     --ignore=tests/test_phase8_decision.py
   # expect: 152 passed (the 5 ignored modules need joblib/shap/xgboost
   # extras from requirements.txt that are unrelated to this change)
   ```

See `PHASE1_WORKED_FILES_MANIFEST_COMMON_INFRA.md` for the full
before/after breakdown, integration notes, and design rationale. Raw
pytest logs from this exact run are included under `evidence/`.
