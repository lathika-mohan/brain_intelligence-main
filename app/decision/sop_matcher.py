"""
Phase 8 — Dynamic SOP Matching & Recommendation Synthesis.

Connects Phase 7 XAI root-cause entities directly to the Phase 2 Neo4j
knowledge graph to retrieve the precise Standard Operating Procedure
(:SOP) nodes that mitigate a given (:FailureMode), per the ontology edge
catalogue documented in ``docs/industrial_knowledge_ontology.md`` §4:

    (:FailureMode)-[:MITIGATED_BY]->(:SOP)
    (:SOP)-[:HAS_STEP]->(:SOPStep)
    (:SOP)-[:REQUIRES_TOOL]->(:Tooling)
    (:SOPStep)-[:HAS_HAZARD]->(:SafetyHazard)

Two execution modes:

  * **Graph-backed** — when a live Neo4j driver is available, runs a single
    targeted Cypher traversal per failure mode and maps the raw records into
    :class:`~app.models.decision.SOPStepDetail` / ``SOPLinkage`` payloads.
  * **Offline fallback catalogue** — a small deterministic, hand-authored
    SOP library keyed by failure-mode id, used when Neo4j is unreachable
    (e.g. isolated unit tests, or a genuinely degraded database) so the
    Decision Engine always returns *some* actionable, safety-complete
    guidance rather than an empty recommendation.

Query builders are pure functions (unit-testable without a database); only
:meth:`SopMatcher.find_sops_for_failure_mode` performs I/O.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

from app.models.decision import SOPLinkage, SOPStepDetail

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Pure Cypher query builder (unit-testable without a database)
# ---------------------------------------------------------------------------
def build_sop_lookup_query(failure_mode_id: str, max_sops: int = 3) -> Tuple[str, Dict[str, Any]]:
    """Build the read-only traversal from a FailureMode to its mitigating SOPs.

    Returns one row per (SOP, SOPStep) pair, ordered by
    ``MITIGATED_BY.effectiveness`` (descending) then ``HAS_STEP.sequence_number``
    (ascending), plus the tools/hazards attached at the SOP/step level.
    """
    cypher = (
        "MATCH (fm:FailureMode {id: $failure_mode_id})-[m:MITIGATED_BY]->(sop:SOP) "
        "OPTIONAL MATCH (sop)-[:HAS_STEP]->(step:SOPStep) "
        "OPTIONAL MATCH (sop)-[:REQUIRES_TOOL]->(tool:Tooling) "
        "OPTIONAL MATCH (step)-[:HAS_HAZARD]->(hazard:SafetyHazard) "
        "WITH sop, m, step, "
        "     collect(DISTINCT tool.display_name) AS tools, "
        "     collect(DISTINCT hazard.hazard_statement) AS hazards, "
        "     collect(DISTINCT hazard.required_ppe) AS ppe_lists "
        "RETURN sop {.*} AS sop, m {.*} AS mitigation, step {.*} AS step, "
        "       tools, hazards, ppe_lists "
        "ORDER BY coalesce(m.effectiveness, 0.5) DESC, coalesce(step.sequence_number, 0) ASC "
        "LIMIT $limit"
    )
    return cypher, {"failure_mode_id": failure_mode_id, "limit": max_sops * 25}


def _flatten_ppe(ppe_lists: List[Any]) -> List[str]:
    flat: List[str] = []
    for entry in ppe_lists or []:
        if isinstance(entry, list):
            flat.extend(str(x) for x in entry)
        elif entry:
            flat.append(str(entry))
    return sorted(set(flat))


def records_to_sop_bundle(
    records: List[Dict[str, Any]], max_sops: int = 3
) -> Tuple[List[SOPLinkage], List[SOPStepDetail]]:
    """Pure mapper: raw Cypher records -> (SOPLinkage[], SOPStepDetail[]).

    Groups rows by SOP id, preserves the effectiveness-descending ordering
    already applied server-side, and caps the number of distinct SOPs
    returned at ``max_sops`` (the "sort recommendations by economic and
    operational efficiency" rule from the Phase 8 brief §3 — SOPs with
    higher recorded ``effectiveness`` sort first).
    """
    linkages: Dict[str, SOPLinkage] = {}
    linkage_order: List[str] = []
    steps: List[SOPStepDetail] = []

    for row in records:
        sop = row.get("sop") or {}
        sop_id = sop.get("id")
        if not sop_id:
            continue
        if sop_id not in linkages:
            if len(linkages) >= max_sops:
                continue
            mitigation = row.get("mitigation") or {}
            linkages[sop_id] = SOPLinkage(
                sop_id=sop_id,
                title=sop.get("title") or sop.get("display_name") or sop_id,
                document_url=sop.get("document_url"),
                revision=sop.get("revision"),
                effectiveness=float(mitigation.get("effectiveness", 0.75) or 0.75),
            )
            linkage_order.append(sop_id)
        if sop_id not in linkage_order[:max_sops]:
            continue

        step = row.get("step")
        if not step:
            continue
        tools = [t for t in (row.get("tools") or []) if t]
        hazards = [h for h in (row.get("hazards") or []) if h]
        ppe = _flatten_ppe(row.get("ppe_lists") or [])
        steps.append(
            SOPStepDetail(
                sop_id=sop_id,
                sop_title=linkages[sop_id].title,
                sequence_number=int(step.get("sequence_number", len(steps) + 1)),
                instruction=step.get("instruction", "Refer to full SOP documentation."),
                expected_outcome=step.get("expected_outcome"),
                step_type=str(step.get("step_type", "EXECUTION")),
                hold_point=bool(step.get("hold_point", False)),
                tooling_required=tools,
                hazards=hazards,
                required_ppe=ppe,
            )
        )

    ordered_linkages = [linkages[sid] for sid in linkage_order if sid in linkages]
    ordered_linkages.sort(key=lambda l: l.effectiveness, reverse=True)

    # Order steps by their parent SOP's effectiveness rank (so the most
    # economically/operationally efficient procedure's steps sort first),
    # then by in-procedure sequence number.
    sop_rank = {l.sop_id: idx for idx, l in enumerate(ordered_linkages)}
    steps.sort(key=lambda s: (sop_rank.get(s.sop_id, len(sop_rank)), s.sequence_number))
    return ordered_linkages, steps


# ---------------------------------------------------------------------------
# Offline fallback catalogue — used when Neo4j is unreachable
# ---------------------------------------------------------------------------
_FALLBACK_CATALOG: Dict[str, Dict[str, Any]] = {
    "failuremode-bearing-overheat": {
        "sop": SOPLinkage(
            sop_id="sop:SOP-114:REV-C",
            title="SOP-114: Bearing Lubrication & Thermal Overload Response",
            document_url="https://docs.internal/sop/SOP-114",
            revision="Rev. C",
            effectiveness=0.82,
        ),
        "steps": [
            {
                "sequence_number": 1,
                "instruction": "Isolate and lockout/tagout the asset drive motor per LOTO procedure.",
                "expected_outcome": "Asset confirmed de-energised and mechanically isolated.",
                "step_type": "SAFETY_CHECK",
                "hold_point": True,
                "tooling_required": ["Lockout/Tagout Kit"],
                "hazards": ["Rotating shaft entrapment", "Residual thermal energy (hot surfaces)"],
                "required_ppe": ["Heat-resistant gloves", "Safety glasses"],
            },
            {
                "sequence_number": 2,
                "instruction": "Inspect bearing housing for discoloration, and measure vibration RMS with a handheld analyzer.",
                "expected_outcome": "Vibration RMS reading recorded and compared against baseline.",
                "step_type": "INSPECTION",
                "hold_point": False,
                "tooling_required": ["Vibration Analyzer"],
                "hazards": [],
                "required_ppe": ["Safety glasses"],
            },
            {
                "sequence_number": 3,
                "instruction": "Re-lubricate bearing per OEM grease specification; reduce lubrication interval to 14 days.",
                "expected_outcome": "Bearing temperature trends back toward baseline within 4 operating hours.",
                "step_type": "EXECUTION",
                "hold_point": False,
                "tooling_required": ["Grease Gun", "OEM Lubricant"],
                "hazards": [],
                "required_ppe": ["Nitrile gloves"],
            },
            {
                "sequence_number": 4,
                "instruction": "Return asset to service and verify bearing temperature stabilises below warning threshold.",
                "expected_outcome": "Bearing temperature < 75C sustained for 30 minutes.",
                "step_type": "VERIFICATION",
                "hold_point": True,
                "tooling_required": ["Infrared Thermometer"],
                "hazards": ["Rotating shaft entrapment"],
                "required_ppe": ["Safety glasses"],
            },
        ],
    },
    "failuremode-general": {
        "sop": SOPLinkage(
            sop_id="sop:SOP-200:REV-A",
            title="SOP-200: General Sensor Degradation Diagnostic & Inspection",
            document_url="https://docs.internal/sop/SOP-200",
            revision="Rev. A",
            effectiveness=0.65,
        ),
        "steps": [
            {
                "sequence_number": 1,
                "instruction": "Cross-check the flagged sensor(s) against redundant instrumentation where available.",
                "expected_outcome": "Sensor reading corroborated or identified as faulty instrumentation.",
                "step_type": "INSPECTION",
                "hold_point": False,
                "tooling_required": ["Handheld Multimeter"],
                "hazards": [],
                "required_ppe": ["Safety glasses"],
            },
            {
                "sequence_number": 2,
                "instruction": "Schedule a diagnostic inspection within the recommended monitoring window.",
                "expected_outcome": "Work order created and assigned to a Level 2 maintenance technician.",
                "step_type": "DOCUMENTATION",
                "hold_point": False,
                "tooling_required": [],
                "hazards": [],
                "required_ppe": [],
            },
        ],
    },
}


def _fallback_bundle(failure_mode_id: Optional[str]) -> Tuple[List[SOPLinkage], List[SOPStepDetail]]:
    entry = _FALLBACK_CATALOG.get(failure_mode_id or "", _FALLBACK_CATALOG["failuremode-general"])
    linkage: SOPLinkage = entry["sop"]
    steps = [
        SOPStepDetail(
            sop_id=linkage.sop_id,
            sop_title=linkage.title,
            **{k: v for k, v in raw_step.items()},
        )
        for raw_step in entry["steps"]
    ]
    return [linkage], steps


# ---------------------------------------------------------------------------
# Public facade
# ---------------------------------------------------------------------------
@dataclass
class SopMatcher:
    """Graph-driven SOP retrieval with a deterministic offline fallback."""

    max_sops: int = 3
    _graph_service: Any = field(default=None, repr=False)

    async def _get_graph_service(self):
        """Best-effort, non-blocking Neo4j service acquisition.

        Mirrors the fast-bypass pattern already used by
        ``app.predictive.xai_service.XaiService.explain`` — only attempts a
        connection when a driver is *already* initialised, so unit tests and
        offline environments never pay a multi-second connection-retry
        penalty just to hit the fallback path.
        """
        if self._graph_service is not None:
            return self._graph_service
        try:
            from app.graph.client import GraphDriverManager

            if not (hasattr(GraphDriverManager, "_driver") and GraphDriverManager._driver is not None):
                return None
            from app.graph.graph_services import GraphAPIService

            self._graph_service = await GraphAPIService.connect()
            return self._graph_service
        except Exception as exc:  # noqa: BLE001 - degrade gracefully
            logger.debug("SOP matcher graph lookup fast bypass: %s", exc)
            return None

    async def find_sops_for_failure_mode(
        self, failure_mode_id: Optional[str]
    ) -> Tuple[List[SOPLinkage], List[SOPStepDetail], bool]:
        """Return (sop_linkages, sop_steps, used_graph) for a failure mode.

        ``used_graph`` is surfaced for the decision-log audit trail so it is
        always clear whether a recommendation was backed by live graph
        knowledge or the offline fallback catalogue.
        """
        if not failure_mode_id:
            linkages, steps = _fallback_bundle(None)
            return linkages, steps, False

        graph_service = await self._get_graph_service()
        if graph_service is None:
            linkages, steps = _fallback_bundle(failure_mode_id)
            return linkages, steps, False

        try:
            cypher, params = build_sop_lookup_query(failure_mode_id, self.max_sops)
            records = await graph_service.repository._read(cypher, params)  # noqa: SLF001
            if not records:
                linkages, steps = _fallback_bundle(failure_mode_id)
                return linkages, steps, False
            linkages, steps = records_to_sop_bundle(records, self.max_sops)
            if not linkages:
                linkages, steps = _fallback_bundle(failure_mode_id)
                return linkages, steps, False
            return linkages, steps, True
        except Exception as exc:  # noqa: BLE001 - never fail the decision pipeline
            logger.warning("SOP graph lookup failed for %s: %s", failure_mode_id, exc)
            linkages, steps = _fallback_bundle(failure_mode_id)
            return linkages, steps, False
