"""
Phase 5 — Citation & Provenance Engine
========================================
Maintains strict data lineage for every piece of context surfaced to the
LLM and ultimately to the end user.  Every vector chunk and graph node
pulled into the fused context is assigned a deterministic citation tag
(``[Source #1]``, ``[Source #2]``, …) that the LLM must reproduce verbatim
in its answer.

The engine is stateless per-query: a fresh ``CitationEngine.build(...)``
call creates a new provenance map for each GraphRAG invocation.
"""

from __future__ import annotations

import hashlib
import logging
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Sequence

from app.models.graphrag import Citation

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Provenance record — one per context element
# ---------------------------------------------------------------------------

@dataclass
class ProvenanceRecord:
    """Immutable record linking a citation tag to its source."""

    tag: str                     # e.g. "[Source #1]"
    index: int                   # 1-based citation index
    source_type: str             # "vector" | "graph" | "both"
    # vector provenance
    chunk_id: Optional[str] = None
    document_id: Optional[str] = None
    document_type: Optional[str] = None
    source_filename: Optional[str] = None
    page_number: Optional[int] = None
    score: float = 0.0
    text_snippet: str = ""
    # graph provenance
    node_id: Optional[str] = None
    node_label: Optional[str] = None
    node_properties: Dict[str, Any] = field(default_factory=dict)
    # unified
    url: Optional[str] = None

    def to_citation(self, claim_span: str = "") -> Citation:
        """Convert to the Phase 0 ``Citation`` contract model."""
        return Citation(
            citation_id=self.tag,
            claim_span=claim_span,
            source_document=self.source_filename or self.document_id or self.node_id,
            source_type=self.document_type or self.node_label,
            source_node_id=self.node_id,
            confidence_score=self.score,
            page_number=self.page_number,
            url=self.url,
        )


# ---------------------------------------------------------------------------
# Citation Engine
# ---------------------------------------------------------------------------

class CitationEngine:
    """
    Assigns deterministic citation tags to fused context candidates and
    produces the provenance lookup table consumed by the prompt builder
    and the final API response.

    Usage::

        engine = CitationEngine()
        prov_map = engine.build(fusion_result.candidates)
        system_prompt = prompt_builder.build(prov_map, ...)
        # After LLM returns:
        citations = engine.extract_citations(llm_output)
    """

    TAG_PREFIX = "[Source #"
    TAG_SUFFIX = "]"

    def __init__(self, max_snippet_chars: int = 200) -> None:
        self.max_snippet_chars = max_snippet_chars

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def build(
        self,
        candidates: Sequence[Any],
    ) -> List[ProvenanceRecord]:
        """
        Assign citation tags to an ordered sequence of FusionCandidates.

        Parameters
        ----------
        candidates:
            Ordered list (highest-score-first) of ``FusionCandidate`` objects
            from the ``ContextFusionEngine``.

        Returns
        -------
        Ordered list of ``ProvenanceRecord`` — the citation lookup table.
        """
        records: List[ProvenanceRecord] = []
        for idx, cand in enumerate(candidates, start=1):
            tag = self._make_tag(idx)
            snippet = self._truncate(getattr(cand, "text", "") or "")

            record = ProvenanceRecord(
                tag=tag,
                index=idx,
                source_type=getattr(cand, "fused_source_type", "unknown"),
                chunk_id=getattr(cand, "chunk_id", None),
                document_id=getattr(cand, "document_id", None),
                document_type=getattr(cand, "document_type", None),
                source_filename=getattr(cand, "source_filename", None),
                page_number=getattr(cand, "page_number", None),
                score=max(getattr(cand, "score_vector", 0.0), getattr(cand, "score_graph", 0.0)),
                text_snippet=snippet,
                node_id=getattr(cand, "node_id", None),
                node_label=getattr(cand, "label", None),
                node_properties=getattr(cand, "metadata", {}),
            )
            records.append(record)
        return records

    def build_from_raw(
        self,
        vector_chunks: List[Dict[str, Any]],
        graph_nodes: List[Dict[str, Any]],
    ) -> List[ProvenanceRecord]:
        """
        Build provenance directly from raw retrieval hits (without going
        through the fusion engine).  Useful for tests and diagnostics.
        """
        records: List[ProvenanceRecord] = []
        idx = 1
        for chunk in vector_chunks:
            tag = self._make_tag(idx)
            records.append(ProvenanceRecord(
                tag=tag,
                index=idx,
                source_type="vector",
                chunk_id=chunk.get("chunk_id"),
                document_id=chunk.get("document_id"),
                document_type=chunk.get("document_type"),
                source_filename=chunk.get("source_filename"),
                page_number=chunk.get("page_start"),
                score=chunk.get("score", 0.0),
                text_snippet=self._truncate(chunk.get("text", "")),
            ))
            idx += 1
        for node in graph_nodes:
            tag = self._make_tag(idx)
            records.append(ProvenanceRecord(
                tag=tag,
                index=idx,
                source_type="graph",
                node_id=node.get("node_id"),
                node_label=node.get("label"),
                node_properties=node.get("properties", {}),
                score=node.get("relevance_score", 0.0),
                text_snippet=self._truncate(node.get("display_name", "")),
            ))
            idx += 1
        return records

    # ------------------------------------------------------------------
    # Tag formatting
    # ------------------------------------------------------------------

    def _make_tag(self, index: int) -> str:
        return f"{self.TAG_PREFIX}{index}{self.TAG_SUFFIX}"

    @staticmethod
    def _truncate(text: str, max_chars: int = 200) -> str:
        text = (text or "").strip().replace("\n", " ")
        if len(text) <= max_chars:
            return text
        return text[: max_chars - 3].rstrip() + "..."

    # ------------------------------------------------------------------
    # Citation extraction from LLM output
    # ------------------------------------------------------------------

    @staticmethod
    def extract_citation_tags(text: str) -> List[str]:
        """
        Parse citation tags from an LLM-generated answer string.

        Looks for patterns like ``[Source #1]``, ``[Source #2]``, etc.
        Returns deduplicated list of matched tags in order of first appearance.
        """
        import re

        pattern = r"\[Source #(\d+)\]"
        matches = re.findall(pattern, text)
        seen: set = set()
        result: List[str] = []
        for m in matches:
            tag = f"[Source #{m}]"
            if tag not in seen:
                seen.add(tag)
                result.append(tag)
        return result

    @staticmethod
    def resolve_citations(
        llm_output: str,
        provenance: List[ProvenanceRecord],
    ) -> List[Citation]:
        """
        Map citation tags found in LLM output to their provenance records,
        producing Phase 0 ``Citation`` objects.
        """
        tags = CitationEngine.extract_citation_tags(llm_output)
        prov_by_tag = {p.tag: p for p in provenance}
        citations: List[Citation] = []
        for tag in tags:
            if tag in prov_by_tag:
                citations.append(prov_by_tag[tag].to_citation())
        return citations

    # ------------------------------------------------------------------
    # Context rendering for prompts
    # ------------------------------------------------------------------

    @staticmethod
    def render_context_block(record: ProvenanceRecord) -> str:
        """Render a single provenance record as a prompt-friendly text block."""
        parts = [f"{record.tag}"]
        if record.source_type == "vector":
            parts.append(f"  Source: {record.source_filename or record.document_id or 'unknown'}")
            if record.page_number:
                parts.append(f"  Page: {record.page_number}")
            parts.append(f"  Type: {record.document_type or 'unknown'}")
            parts.append(f"  Score: {record.score:.3f}")
            parts.append(f"  Content: {record.text_snippet}")
        elif record.source_type == "graph":
            parts.append(f"  Node: {record.node_id or 'unknown'}")
            parts.append(f"  Label: {record.node_label or 'unknown'}")
            if record.node_properties:
                props_str = ", ".join(
                    f"{k}={v}" for k, v in list(record.node_properties.items())[:5]
                )
                parts.append(f"  Properties: {props_str}")
        else:
            # "both" or unknown — combine
            parts.append(f"  Chunk: {record.chunk_id} | Node: {record.node_id}")
            parts.append(f"  Score: {record.score:.3f}")
            parts.append(f"  Content: {record.text_snippet}")
        return "\n".join(parts)

    @staticmethod
    def render_full_context(provenance: List[ProvenanceRecord]) -> str:
        """Render the entire provenance map as a context block for the system prompt."""
        if not provenance:
            return "(No context retrieved)"
        blocks = [CitationEngine.render_context_block(r) for r in provenance]
        return "\n\n".join(blocks)

    # ------------------------------------------------------------------
    # Hashing for determinism
    # ------------------------------------------------------------------

    @staticmethod
    def compute_provenance_hash(provenance: List[ProvenanceRecord]) -> str:
        """Deterministic hash of the provenance map (for audit logging)."""
        h = hashlib.sha256()
        for r in provenance:
            h.update(r.tag.encode())
            h.update((r.chunk_id or "").encode())
            h.update((r.node_id or "").encode())
            h.update(str(r.score).encode())
        return h.hexdigest()[:16]
