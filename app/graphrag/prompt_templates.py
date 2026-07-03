"""
Phase 5 — Prompt Templates & Grounded System Prompting
========================================================
Produces boundary-constrained system prompts for the synthesis LLM.

Design principles:
  1. The LLM must answer **only** from the provided context — no hallucination.
  2. Every factual claim must carry an inline citation tag (``[Source #N]``).
  3. Tone is industrial / technical / objective — never conversational.
  4. If the context is insufficient the model must say so explicitly.
"""

from __future__ import annotations

import logging
from typing import List, Optional

from app.graphrag.citation_engine import CitationEngine, ProvenanceRecord

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# System prompt templates
# ---------------------------------------------------------------------------

SYSTEM_PROMPT_TEMPLATE = """\
You are an expert industrial operations analyst embedded in an AI-powered \
Knowledge Retrieval system for an enterprise asset-management platform.

## ROLE
You receive structured context retrieved from two knowledge sources:
  • Vector-searched text chunks from technical documentation, SOPs, and \
    maintenance logs.
  • Graph-traversed structural data from the enterprise knowledge graph \
    (assets, components, failure modes, procedures).

## STRICT CONSTRAINTS
1. **GROUNDING**: You MUST answer the user's query using ONLY the provided \
   context below. Do NOT fabricate facts, invent data, or reference documents \
   not present in the context.
2. **CITATIONS**: Every factual claim in your answer MUST include an inline \
   citation tag in the format [Source #N] where N is the citation index from \
   the context. Multiple citations are allowed: [Source #1] [Source #3].
3. **TONE**: Use a clear, objective, industrial-technical tone. Avoid \
   conversational filler, hedging language, or marketing speak.
4. **COMPLETENESS**: If the provided context does not contain sufficient \
   information to fully answer the query, explicitly state what is missing \
   rather than guessing.
5. **STRUCTURE**: Begin with a direct answer, then provide supporting \
   technical details. Use numbered lists for procedural steps.
6. **SAFETY**: If the context reveals safety-critical information (hazards, \
   lockout procedures, PPE requirements), always surface these prominently.

## CONTEXT
{context_block}

## USER QUERY
{user_query}

## INSTRUCTIONS
Provide a comprehensive, citation-backed technical answer to the user's query. \
Reference the context above using [Source #N] tags for every claim. If the \
context is insufficient, state: "The available context does not fully address \
this query. Additional information needed: [specify what is missing]."

Respond now:
"""

USER_QUERY_TEMPLATE = """\
Based on the retrieved context, answer the following operational query:

{query}

Remember: cite every claim with [Source #N] tags. Be technical, precise, \
and objective. If context is insufficient, state what is missing.
"""

FALLBACK_NO_CONTEXT = """\
The retrieval pipeline returned no relevant context for this query. \
This may indicate:
  • The query references assets or procedures not yet ingested into the \
    knowledge base.
  • The semantic similarity threshold was too strict.
  • The asset identifier in the query does not match any indexed entity.

Recommendation: Verify the asset identifier and broaden the search filters.
"""

# ---------------------------------------------------------------------------
# Prompt builder
# ---------------------------------------------------------------------------

class PromptBuilder:
    """
    Constructs grounded system prompts from provenance records and user queries.

    The builder is intentionally stateless — each call to ``build_system_prompt``
    produces a fresh prompt string from the current provenance map.
    """

    def __init__(
        self,
        max_context_chars: int = 12_000,
        citation_engine: Optional[CitationEngine] = None,
    ) -> None:
        self.max_context_chars = max_context_chars
        self._citation_engine = citation_engine or CitationEngine()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def build_system_prompt(
        self,
        user_query: str,
        provenance: List[ProvenanceRecord],
        *,
        asset_id: Optional[str] = None,
    ) -> str:
        """
        Build the full system prompt string with embedded context and citations.

        Parameters
        ----------
        user_query:
            The operator's natural-language question.
        provenance:
            Ordered provenance records from the CitationEngine.
        asset_id:
            Optional asset context to prepend.
        """
        # Render context block
        context_block = CitationEngine.render_full_context(provenance)

        # Truncate if too long
        if len(context_block) > self.max_context_chars:
            context_block = context_block[: self.max_context_chars]
            context_block += "\n\n[... context truncated due to length ...]"

        # Prepend asset context if available
        if asset_id:
            context_block = f"[Asset Context: {asset_id}]\n\n{context_block}"

        return SYSTEM_PROMPT_TEMPLATE.format(
            context_block=context_block,
            user_query=user_query,
        )

    def build_user_message(
        self,
        user_query: str,
        *,
        additional_instructions: Optional[str] = None,
    ) -> str:
        """Build the user-side message for the LLM conversation."""
        msg = USER_QUERY_TEMPLATE.format(query=user_query)
        if additional_instructions:
            msg += f"\n\nAdditional instructions: {additional_instructions}"
        return msg

    @staticmethod
    def build_no_context_response() -> str:
        """Return the fallback response when retrieval yields zero context."""
        return FALLBACK_NO_CONTEXT

    # ------------------------------------------------------------------
    # LLM response post-processing
    # ------------------------------------------------------------------

    @staticmethod
    def validate_citations_in_response(
        llm_output: str,
        provenance: List[ProvenanceRecord],
    ) -> dict:
        """
        Audit the LLM output for citation compliance.

        Returns a dict with:
          - found_tags: list of citation tags found in the output
          - valid_tags: tags that map to actual provenance records
          - hallucinated_tags: tags that don't map to any source
          - missing_tags: provenance records not cited
          - compliance_ratio: fraction of found tags that are valid
        """
        found_tags = CitationEngine.extract_citation_tags(llm_output)
        valid_tag_set = {p.tag for p in provenance}

        valid_tags = [t for t in found_tags if t in valid_tag_set]
        hallucinated_tags = [t for t in found_tags if t not in valid_tag_set]
        cited_indices = {int(t.split("#")[1].rstrip("]")) for t in valid_tags}
        missing_tags = [
            p.tag for p in provenance if p.index not in cited_indices
        ]

        compliance = len(valid_tags) / max(len(found_tags), 1)

        return {
            "found_tags": found_tags,
            "valid_tags": valid_tags,
            "hallucinated_tags": hallucinated_tags,
            "missing_tags": missing_tags,
            "compliance_ratio": round(compliance, 3),
        }
