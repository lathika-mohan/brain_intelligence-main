"""
Explainable AI (XAI) Contract Conformance & Boundary Validation Suite.
"""
from __future__ import annotations

import time
import pytest
from app.models.xai import (
    ExplanationRequest,
    ExplanationResponse,
    ExplanationMethod,
    ExplanationScope,
)
from app.predictive.xai_service import XaiService
from app.predictive.telemetry_simulator import generate_episode

@pytest.mark.asyncio
async def test_xai_local_explanation_contract_and_latency():
    """Verify calculating local explanations for an inference vector takes < 200ms and matches contract schemas."""
    service = XaiService()
    
    # Generate 24 chronological time-series frames to satisfy rolling-window offsets
    episode = generate_episode(asset_id="turbine-01")
    history = episode.frames[:24]
    
    request = ExplanationRequest(
        asset_id="turbine-01",
        method=ExplanationMethod.SHAP,
        scope=ExplanationScope.LOCAL
    )
    
    # Performance boundary validation (< 200ms)
    # Warm-up call to eliminate import/compilation/cold-start latency artifacts
    await service.explain(request, history)

    start_time = time.perf_counter()
    response = await service.explain(request, history)
    end_time = time.perf_counter()
    
    latency_ms = (end_time - start_time) * 1000.0
    print(f"XAI Inference & Explanation latency: {latency_ms:.2f}ms")
    
    assert latency_ms < 200.0, f"XAI explanation took {latency_ms:.2f}ms which exceeds the 200ms limit."
    
    # Contract validation of response layout completely satisfying frontend ShapExplainability.tsx requirements
    assert isinstance(response, ExplanationResponse)
    assert response.asset_id == "turbine-01"
    assert response.method == ExplanationMethod.SHAP
    assert response.scope == ExplanationScope.LOCAL
    
    # Local feature rankings
    assert len(response.local_feature_importance) > 0
    # Ensure ordered rankings starting with 1
    assert response.local_feature_importance[0].rank == 1
    
    # Natural language synthesis
    assert response.root_cause.headline is not None
    assert response.root_cause.narrative is not None
    assert len(response.root_cause.contributing_failure_modes) > 0
    
    # Metadata required to render force or waterfall charts
    assert isinstance(response.base_value, float)
    assert isinstance(response.predicted_value, float)
    assert len(response.confidence_matrix) > 0
