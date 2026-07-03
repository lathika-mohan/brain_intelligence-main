"""
Phase 5 — Context Fusion Engine
================================
Implements Reciprocal Rank Fusion (RRF) and related cross-modal fusion
strategies that merge ranked lists from vector retrieval (Qdrant) and
graph traversal (Neo4j) into a unified, scored context surface for LLM
synthesis.

The fusion layer is deterministic, pure-Python, and fully unit-testable
without any database connections.
"""

from __future__ import annotations

import logging
from collections import defaultdict
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Sequence, Tuple

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Data structures
# ---------------------------------------------------------------------------

@dataclass
class FusionCandidate:
    """A single entity that can receive fused scores from multiple retrieval channels."""

    candidate_id: str
    label: str = ""
    source_type: str = ""          # "vector" | "graph" | "both"
    text: str = ""                 # raw text (for vector chunks) or serialised label (for graph nodes)
    score_vector: float = 0.0      # cosine similarity from Qdrant
    score_graph: float = 0.0       # traversal relevance from Neo4j
    rrf_score: float = 0.0         # fused RRF score
    metadata: Dict[str, Any] = field(default_factory=dict)

    # Provenance
    document_id: Optional[str] = None
    chunk_id: Optional[str] = None
    node_id: Optional[str] = None
    page_number: Optional[int] = None
    document_type: Optional[str] = None
    source_filename: Optional[str] = None

    @property
    def fused_source_type(self) -> str:
        if self.score_vector > 0 and self.score_graph > 0:
            return "both"
        if self.score_vector > 0:
            return "vector"
        return "graph"


@dataclass
class FusionResult:
    """Output of the fusion engine — a ranked list of fused candidates."""

    candidates: List[FusionCandidate]
    total_vector_candidates: int = 0
    total_graph_candidates: int = 0
    fusion_method: str = "rrf"
    k_param: int = 60  # RRF smoothing constant


# ---------------------------------------------------------------------------
# Default RRF constant (from Cormack et al. 2009)
# ---------------------------------------------------------------------------
DEFAULT_RRF_K = 60


# ---------------------------------------------------------------------------
# Reciprocal Rank Fusion
# ---------------------------------------------------------------------------
def reciprocal_rank_fusion(
    ranked_lists: Sequence[Sequence[Tuple[str, float]]],
    k: int = DEFAULT_RRF_K,
) -> Dict[str, float]:
    """
    Compute RRF scores for a set of ranked lists.

    Each ranked list is a sequence of (candidate_id, score) tuples in
    descending relevance order. The RRF score for each candidate is::

        RRF(d) = Σ 1 / (k + rank_i(d))

    where rank_i(d) is the 1-based position of *d* in list *i*.

    Parameters
    ----------
    ranked_lists:
        Sequence of ranked lists.  Each inner list is ``(id, score)`` pairs
        ordered from most to least relevant.
    k:
        Smoothing constant (default 60 per the original paper).

    Returns
    -------
    Dict mapping candidate_id → RRF score (un-normalised).
    """
    scores: Dict[str, float] = defaultdict(float)
    for ranked_list in ranked_lists:
        for rank_0based, (candidate_id, _score) in enumerate(ranked_list):
            rank = rank_0based + 1  # 1-based
            scores[candidate_id] += 1.0 / (k + rank)
    return dict(scores)


# ---------------------------------------------------------------------------
# Context Fusion Engine
# ---------------------------------------------------------------------------
class ContextFusionEngine:
    """
    Fuses vector retrieval results and graph traversal results into a single
    ranked context surface consumed by the LLM prompt builder.

    Supports:
    - Reciprocal Rank Fusion (RRF) — default, parameter-free
    - Weighted linear combination — when explicit weights are supplied
    - Deduplication by entity identity (chunk_id or node_id)
    """

    def __init__(self, rrf_k: int = DEFAULT_RRF_K) -> None:
        self.rrf_k = rrf_k

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------
    def fuse(
        self,
        vector_hits: List[Dict[str, Any]],
        graph_hits: List[Dict[str, Any]],
        *,
        method: str = "rrf",
        max_candidates: int = 20,
        vector_weight: float = 0.6,
        graph_weight: float = 0.4,
    ) -> FusionResult:
        """
        Fuse vector and graph retrieval results into a unified ranking.

        Parameters
        ----------
        vector_hits:
            List of dicts from Qdrant with at minimum ``chunk_id``, ``text``,
            ``score``, ``document_id``, ``document_type``.
        graph_hits:
            List of dicts from Neo4j traversal with at minimum ``node_id``,
            ``label``, ``properties``, ``relevance_score``.
        method:
            Fusion strategy — ``"rrf"`` or ``"weighted"``.
        max_candidates:
            Cap on returned candidates.
        vector_weight / graph_weight:
            Relative weights for the ``"weighted"`` method.

        Returns
        -------
        FusionResult with sorted FusionCandidate list.
        """
        # Build candidate map keyed by unified ID
        candidates: Dict[str, FusionCandidate] = {}

        # --- Vector channel ---
        for hit in vector_hits:
            cid = hit.get("chunk_id", "")
            if not cid:
                continue
            candidates[cid] = FusionCandidate(
                candidate_id=cid,
                label=hit.get("section_title", "") or hit.get("document_type", "chunk"),
                source_type="vector",
                text=hit.get("text", ""),
                score_vector=hit.get("score", 0.0),
                metadata=hit.get("payload", {}),
                document_id=hit.get("document_id"),
                chunk_id=cid,
                page_number=hit.get("page_start"),
                document_type=hit.get("document_type"),
                source_filename=hit.get("source_filename"),
            )

        # --- Graph channel ---
        for hit in graph_hits:
            nid = hit.get("node_id", "")
            if not nid:
                continue
            # Use node_id as key; if a vector chunk already occupies this ID,
            # we merge the scores (this handles the case where a chunk references
            # a node that was also retrieved from the graph).
            key = nid
            if key in candidates:
                # Cross-modal overlap: boost both scores
                candidates[key].score_graph = hit.get("relevance_score", 0.0)
                candidates[key].source_type = "both"
                candidates[key].node_id = nid
            else:
                candidates[key] = FusionCandidate(
                    candidate_id=key,
                    label=hit.get("label", "") or hit.get("display_name", ""),
                    source_type="graph",
                    text=hit.get("text", "") or hit.get("display_name", ""),
                    score_graph=hit.get("relevance_score", 0.0),
                    metadata=hit.get("properties", {}),
                    node_id=nid,
                    document_type=hit.get("document_type"),
                )

        # --- Apply fusion scoring ---
        if method == "rrf":
            self._apply_rrf(candidates, vector_hits, graph_hits)
        elif method == "weighted":
            self._apply_weighted(candidates, vector_weight, graph_weight)
        else:
            raise ValueError(f"Unknown fusion method: {method!r}")

        # --- Rank & truncate ---
        sorted_candidates = sorted(
            candidates.values(),
            key=lambda c: c.rrf_score if method == "rrf" else (c.score_vector + c.score_graph),
            reverse=True,
        )[:max_candidates]

        return FusionResult(
            candidates=sorted_candidates,
            total_vector_candidates=len(vector_hits),
            total_graph_candidates=len(graph_hits),
            fusion_method=method,
            k_param=self.rrf_k,
        )

    # ------------------------------------------------------------------
    # Internal scoring strategies
    # ------------------------------------------------------------------
    def _apply_rrf(
        self,
        candidates: Dict[str, FusionCandidate],
        vector_hits: List[Dict[str, Any]],
        graph_hits: List[Dict[str, Any]],
    ) -> None:
        """Apply Reciprocal Rank Fusion across both channels."""
        # Build ranked lists: (candidate_id, score) tuples in rank order
        vector_ranked = [
            (h.get("chunk_id", ""), h.get("score", 0.0))
            for h in vector_hits
            if h.get("chunk_id")
        ]
        graph_ranked = [
            (h.get("node_id", ""), h.get("relevance_score", 0.0))
            for h in graph_hits
            if h.get("node_id")
        ]

        rrf_scores = reciprocal_rank_fusion(
            [vector_ranked, graph_ranked], k=self.rrf_k
        )

        for cid, rrf in rrf_scores.items():
            if cid in candidates:
                candidates[cid].rrf_score = rrf

    @staticmethod
    def _apply_weighted(
        candidates: Dict[str, FusionCandidate],
        vector_weight: float,
        graph_weight: float,
    ) -> None:
        """Simple weighted linear combination."""
        total_w = vector_weight + graph_weight or 1.0
        vw = vector_weight / total_w
        gw = graph_weight / total_w
        for c in candidates.values():
            c.rrf_score = vw * c.score_vector + gw * c.score_graph

    # ------------------------------------------------------------------
    # Diagnostics
    # ------------------------------------------------------------------
    @staticmethod
    def compute_overlap(vector_hits: List[Dict], graph_hits: List[Dict]) -> Dict[str, Any]:
        """Measure cross-modal overlap — useful for benchmarking."""
        vector_ids = {h.get("chunk_id") for h in vector_hits}
        graph_ids = {h.get("node_id") for h in graph_hits}
        overlap = vector_ids & graph_ids
        return {
            "vector_count": len(vector_ids),
            "graph_count": len(graph_ids),
            "overlap_count": len(overlap),
            "overlap_ratio": len(overlap) / max(len(vector_ids | graph_ids), 1),
        }
