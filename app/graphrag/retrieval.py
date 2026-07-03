"""
Phase 5 — Hybrid Retrieval Layer
==================================
Coordinates parallel retrieval from:
  • Qdrant vector search (Phase 4 search_service)
  • Neo4j graph traversal (Phase 2 graph_services)

The retriever runs both channels concurrently using ``asyncio.gather``,
extracts entity anchors from vector hits to seed graph traversal, and
serialises the Neo4j sub-graph into a structure compatible with the
frontend visualiser (``GraphRagPanel.tsx``).
"""

from __future__ import annotations

import asyncio
import logging
import re
import time
from typing import Any, Dict, List, Optional, Tuple

from app.core.config import get_settings
from app.graph.graph_repository import Neo4jGraphRepository
from app.graph.graph_services import GraphAPIService, GraphQueryService

logger = logging.getLogger(__name__)

# Relationship types to traverse during sub-graph expansion
TRAVERSAL_RELATIONSHIPS = (
    "COMPRISED_OF|MONITORED_BY|EXHIBITS_ANOMALY|"
    "MITIGATED_BY|TRIGGERED_BY|HAS_SYMPTOM|HAS_STEP|"
    "GROUNDS_ENTITY|MENTIONS"
)


# ---------------------------------------------------------------------------
# Entity anchor extraction — map vector hits to graph entities
# ---------------------------------------------------------------------------

# Patterns for extracting asset IDs from chunk text / metadata
_ASSET_ID_PATTERNS = [
    re.compile(r"(?:asset[_-]?id|asset_id)[\s:=]+([A-Za-z0-9:_\-]+)", re.IGNORECASE),
    re.compile(r"\b(Asset|asset)[:\-]\s*([A-Za-z0-9:_\-]+)"),
    re.compile(r"\b([A-Z][A-Z0-9]*-\d{2,4}[A-Z]?)\b"),  # e.g. G-101, C-204, P-101A
    re.compile(r"\b(Turbine|Compressor|Pump|Motor|Fan|Blower)[\s\-]?\d{1,4}\b", re.IGNORECASE),
]

# Node-label keyword mapping
_ENTITY_KEYWORDS: Dict[str, List[str]] = {
    "Asset": ["asset", "turbine", "compressor", "pump", "motor", "fan", "blower", "vessel", "tank"],
    "Component": ["bearing", "seal", "impeller", "shaft", "valve", "coupling", "gear"],
    "FailureMode": ["failure", "anomaly", "surge", "wear", "overheat", "vibration", "misalignment"],
    "SOP": ["SOP", "procedure", "standard operating"],
    "RootCause": ["root cause", "caused by", "triggered by"],
}


def extract_entity_anchors(hits: List[Dict[str, Any]]) -> List[str]:
    """
    Extract candidate entity identifiers from vector search hits.
    Used to seed the Neo4j traversal with relevant starting nodes.
    """
    anchors: set = set()
    for hit in hits:
        # Check metadata first
        for key in ("asset_id", "document_id", "entity_id"):
            val = hit.get(key)
            if val and isinstance(val, str) and len(val) < 100:
                anchors.add(val)
        # Check text content
        text = hit.get("text", "")
        if text:
            for pattern in _ASSET_ID_PATTERNS:
                for match in pattern.finditer(text[:2000]):  # limit scan range
                    groups = match.groups()
                    for g in groups:
                        if g and len(g) >= 3 and not g.lower().startswith("http"):
                            anchors.add(g)
    return list(anchors)[:20]  # cap to prevent fan-out explosion


def extract_entity_keywords(hits: List[Dict[str, Any]]) -> Dict[str, List[str]]:
    """
    Map vector hit content to known graph node labels for targeted lookups.
    """
    label_matches: Dict[str, List[str]] = {label: [] for label in _ENTITY_KEYWORDS}
    for hit in hits:
        text = (hit.get("text", "") or "").lower()
        for label, keywords in _ENTITY_KEYWORDS.items():
            for kw in keywords:
                if kw.lower() in text:
                    # Extract the surrounding phrase
                    idx = text.find(kw.lower())
                    snippet = text[max(0, idx - 20): idx + len(kw) + 30].strip()
                    label_matches[label].append(snippet)
    return {k: list(set(v))[:5] for k, v in label_matches.items() if v}


# ---------------------------------------------------------------------------
# Graph serialisation for frontend visualiser
# ---------------------------------------------------------------------------

# Map Neo4j labels to frontend GraphRagPanel node types
_LABEL_TO_FRONTEND_TYPE = {
    "Asset": "asset",
    "Component": "component",
    "FailureMode": "anomaly",
    "Sensor": "component",
    "SOP": "procedure",
    "SOPStep": "procedure",
    "RootCause": "anomaly",
    "MaintenanceTask": "record",
    "Location": "asset",
    "TextChunk": "record",
    "SourceDocument": "record",
}


def serialise_graph_for_frontend(
    nodes: List[Dict[str, Any]],
    edges: List[Dict[str, Any]],
) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
    """
    Convert raw Neo4j sub-graph records into the node/edge format
    expected by ``GraphRagPanel.tsx`` and the Phase 0 response contract.
    """
    frontend_nodes = []
    for n in nodes:
        props = n.get("props", n)
        labels = n.get("labels", [props.get("label", "Node")])
        primary_label = labels[0] if labels else "Node"
        node_type = _LABEL_TO_FRONTEND_TYPE.get(primary_label, "record")
        frontend_nodes.append({
            "id": props.get("id", n.get("element_id", "")),
            "label": props.get("display_name", "") or primary_label,
            "type": node_type,
            "properties": {k: v for k, v in props.items()
                          if k not in ("created_at", "updated_at")},
        })

    frontend_edges = []
    for e in edges:
        frontend_edges.append({
            "source": e.get("source_id", e.get("start_id", "")),
            "target": e.get("target_id", e.get("end_id", "")),
            "relationship": e.get("type", e.get("relationship", "")),
            "weight": e.get("props", {}).get("confidence_weight", 1.0),
        })

    return frontend_nodes, frontend_edges


# ---------------------------------------------------------------------------
# Hybrid Retriever
# ---------------------------------------------------------------------------

class HybridRetriever:
    """
    Orchestrates parallel retrieval from Qdrant and Neo4j.

    The retrieval strategy:
      1. Run vector search against Qdrant (Phase 4 service).
      2. Extract entity anchors from the top vector hits.
      3. Run targeted graph traversal from those anchors in Neo4j.
      4. If an explicit ``asset_id`` is provided, also run a full sub-graph
         expansion from that asset.
      5. Return both channels' results for the fusion engine.
    """

    def __init__(
        self,
        vector_search_service=None,
        graph_query_service: Optional[GraphQueryService] = None,
        graph_repository: Optional[Neo4jGraphRepository] = None,
    ) -> None:
        self._vector_svc = vector_search_service
        self._graph_query = graph_query_service
        self._graph_repo = graph_repository
        self.settings = get_settings()

    # ------------------------------------------------------------------
    # Lazy initialisation
    # ------------------------------------------------------------------

    def _get_vector_service(self):
        if self._vector_svc is None:
            from app.vector.search_service import get_search_service
            self._vector_svc = get_search_service()
        return self._vector_svc

    def _get_graph_repo(self) -> Neo4jGraphRepository:
        if self._graph_repo is None:
            raise RuntimeError(
                "GraphRepository not initialised. "
                "Ensure Neo4j is running and the graph service is connected."
            )
        return self._graph_repo

    def _get_graph_query(self) -> GraphQueryService:
        if self._graph_query is None:
            repo = self._get_graph_repo()
            self._graph_query = GraphQueryService(repo)
        return self._graph_query

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    async def retrieve(
        self,
        query_text: str,
        *,
        top_k: int = 8,
        min_score: float = 0.55,
        max_graph_hops: int = 2,
        asset_id: Optional[str] = None,
        filters: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Execute parallel vector + graph retrieval.

        Returns a dict with:
          - vector_hits: list of Qdrant search results
          - graph_hits: list of Neo4j traversal results (flat nodes + edges)
          - graph_nodes_raw: raw Neo4j node dicts
          - graph_edges_raw: raw Neo4j edge dicts
          - timing: dict of per-channel latencies
        """
        t0 = time.perf_counter()

        # ---- Parallel retrieval ----
        vector_task = self._retrieve_vector(
            query_text, top_k=top_k, min_score=min_score, filters=filters
        )
        graph_task = self._retrieve_graph(
            query_text, asset_id=asset_id, max_hops=max_graph_hops
        )

        vector_result, graph_result = await asyncio.gather(
            vector_task, graph_task, return_exceptions=True
        )

        # Handle errors gracefully — one channel failing shouldn't kill the other
        vector_hits: List[Dict[str, Any]] = []
        vector_latency = 0.0
        if isinstance(vector_result, Exception):
            logger.error("Vector retrieval failed: %s", vector_result)
        else:
            vector_hits = vector_result.get("hits", [])
            vector_latency = vector_result.get("latency_ms", 0.0)

        graph_hits: List[Dict[str, Any]] = []
        graph_nodes_raw: List[Dict[str, Any]] = []
        graph_edges_raw: List[Dict[str, Any]] = []
        graph_latency = 0.0
        if isinstance(graph_result, Exception):
            logger.error("Graph retrieval failed: %s", graph_result)
        else:
            graph_hits = graph_result.get("hits", [])
            graph_nodes_raw = graph_result.get("nodes_raw", [])
            graph_edges_raw = graph_result.get("edges_raw", [])
            graph_latency = graph_result.get("latency_ms", 0.0)

        total_latency = (time.perf_counter() - t0) * 1000.0

        return {
            "vector_hits": vector_hits,
            "graph_hits": graph_hits,
            "graph_nodes_raw": graph_nodes_raw,
            "graph_edges_raw": graph_edges_raw,
            "timing": {
                "vector_ms": round(vector_latency, 2),
                "graph_ms": round(graph_latency, 2),
                "total_ms": round(total_latency, 2),
            },
        }

    # ------------------------------------------------------------------
    # Vector channel
    # ------------------------------------------------------------------

    async def _retrieve_vector(
        self,
        query_text: str,
        *,
        top_k: int,
        min_score: float,
        filters: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Run semantic search against Qdrant."""
        t0 = time.perf_counter()
        svc = self._get_vector_service()

        # Build SearchFilters from the generic dict
        from app.vector.models import SearchFilters

        filt = None
        if filters:
            try:
                filt = SearchFilters(**filters)
            except Exception:
                filt = None

        response = await svc.semantic_search(
            query_text=query_text,
            top_k=top_k,
            filters=filt,
            score_threshold=min_score,
        )

        # Convert to flat dicts for the fusion engine
        hits = []
        for r in response.results:
            hits.append({
                "chunk_id": r.chunk_id,
                "text": r.text,
                "score": r.score,
                "document_id": r.document_id,
                "document_type": r.document_type,
                "asset_type": r.asset_type,
                "source_filename": r.source_filename,
                "section_title": r.section_title,
                "page_start": r.payload.get("page_start") if r.payload else None,
                "payload": r.payload or {},
            })

        latency = (time.perf_counter() - t0) * 1000.0
        return {"hits": hits, "latency_ms": latency, "embedding_model": response.embedding_model}

    # ------------------------------------------------------------------
    # Graph channel
    # ------------------------------------------------------------------

    async def _retrieve_graph(
        self,
        query_text: str,
        *,
        asset_id: Optional[str],
        max_hops: int,
    ) -> Dict[str, Any]:
        """
        Run graph traversal against Neo4j.

        Strategy:
          1. If asset_id is provided, do full sub-graph expansion.
          2. Also search for nodes matching query keywords.
          3. Expand from those nodes up to max_hops.
        """
        t0 = time.perf_counter()
        all_nodes: Dict[str, Dict[str, Any]] = {}
        all_edges: Dict[Tuple[str, str, str], Dict[str, Any]] = {}
        hits: List[Dict[str, Any]] = []

        try:
            repo = self._get_graph_repo()
        except RuntimeError:
            # Neo4j not available — return empty graph results
            return {
                "hits": [],
                "nodes_raw": [],
                "edges_raw": [],
                "latency_ms": (time.perf_counter() - t0) * 1000.0,
            }

        # --- Asset sub-graph expansion ---
        if asset_id:
            try:
                subgraph = await self._expand_asset_subgraph(repo, asset_id, max_hops)
                for n in subgraph["nodes"]:
                    nid = n.get("id", "")
                    if nid:
                        all_nodes[nid] = n
                for e in subgraph["edges"]:
                    key = (e["source_id"], e["relationship"], e["target_id"])
                    all_edges[key] = e
            except Exception as e:
                logger.warning("Asset sub-graph expansion failed for %s: %s", asset_id, e)

        # --- Keyword-based node search ---
        try:
            keyword_nodes = await self._search_by_keywords(repo, query_text)
            for n in keyword_nodes:
                nid = n.get("id", "")
                if nid and nid not in all_nodes:
                    all_nodes[nid] = n
            # Expand from keyword matches
            for n in keyword_nodes[:5]:
                nid = n.get("id", "")
                if nid:
                    label = n.get("label", "Node")
                    try:
                        expanded = await self._expand_from_node(repo, label, nid, max_hops=1)
                        for en in expanded["nodes"]:
                            eid = en.get("id", "")
                            if eid:
                                all_nodes[eid] = en
                        for ee in expanded["edges"]:
                            ekey = (ee["source_id"], ee["relationship"], ee["target_id"])
                            all_edges[ekey] = ee
                    except Exception as e2:
                        logger.debug("Expansion from %s failed: %s", nid, e2)
        except Exception as e:
            logger.warning("Keyword graph search failed: %s", e)

        # Build hits list for fusion
        for nid, node in all_nodes.items():
            hits.append({
                "node_id": nid,
                "label": node.get("label", ""),
                "display_name": node.get("display_name", nid),
                "relevance_score": 0.8,  # uniform score; RRF will differentiate
                "properties": node.get("properties", {}),
                "document_type": node.get("label", ""),
                "text": node.get("display_name", "") or nid,
            })

        latency = (time.perf_counter() - t0) * 1000.0
        return {
            "hits": hits,
            "nodes_raw": list(all_nodes.values()),
            "edges_raw": list(all_edges.values()),
            "latency_ms": latency,
        }

    # ------------------------------------------------------------------
    # Graph traversal helpers
    # ------------------------------------------------------------------

    async def _expand_asset_subgraph(
        self,
        repo: Neo4jGraphRepository,
        asset_id: str,
        max_hops: int,
    ) -> Dict[str, Any]:
        """Expand the full sub-graph rooted at an Asset node."""
        hops = max(1, min(max_hops, 5))
        cypher = (
            f"MATCH (root:Asset {{id:$asset_id}}) "
            f"OPTIONAL MATCH path=(root)-[rels:{TRAVERSAL_RELATIONSHIPS}*1..{hops}]->(leaf) "
            "RETURN root, path"
        )
        records = await repo._read(cypher, {"asset_id": asset_id})

        nodes: Dict[str, Dict[str, Any]] = {}
        edges: Dict[Tuple[str, str, str], Dict[str, Any]] = {}

        for record in records:
            root = record.get("root")
            if root:
                self._extract_node(root, nodes)

            path = record.get("path")
            if path is None:
                continue
            # Extract nodes and edges from the path
            path_nodes = getattr(path, "nodes", lambda: [])()
            path_rels = getattr(path, "relationships", lambda: [])()
            for pn in path_nodes:
                self._extract_node(pn, nodes)
            for pr in path_rels:
                self._extract_edge(pr, edges, nodes)

        return {"nodes": list(nodes.values()), "edges": list(edges.values())}

    async def _search_by_keywords(
        self,
        repo: Neo4jGraphRepository,
        query_text: str,
        limit: int = 5,
    ) -> List[Dict[str, Any]]:
        """Search for graph nodes matching query keywords."""
        # Extract key terms (simple word extraction)
        words = re.findall(r"\b[A-Za-z][\w\-]{2,}\b", query_text)
        # Filter out common stop words
        stop_words = {
            "the", "and", "for", "why", "did", "what", "how", "list",
            "explain", "this", "that", "with", "from", "are", "was",
        }
        terms = [w for w in words if w.lower() not in stop_words][:5]

        if not terms:
            return []

        nodes: Dict[str, Dict[str, Any]] = {}
        # Search across multiple labels
        for label in ["Asset", "Component", "FailureMode", "SOP"]:
            for term in terms:
                try:
                    cypher = (
                        f"MATCH (n:`{label}`) "
                        "WHERE toLower(n.display_name) CONTAINS toLower($term) "
                        "   OR toLower(n.id) CONTAINS toLower($term) "
                        "RETURN n LIMIT $limit"
                    )
                    records = await repo._read(cypher, {"term": term, "limit": limit})
                    for r in records:
                        n = r.get("n", {})
                        nid = n.get("id", "")
                        if nid:
                            nodes[nid] = {
                                "id": nid,
                                "label": label,
                                "display_name": n.get("display_name", nid),
                                "properties": {k: v for k, v in n.items()
                                              if k not in ("created_at", "updated_at")},
                            }
                except Exception as e:
                    logger.debug("Keyword search on %s for '%s' failed: %s", label, term, e)

        return list(nodes.values())[:10]

    async def _expand_from_node(
        self,
        repo: Neo4jGraphRepository,
        label: str,
        node_id: str,
        max_hops: int = 1,
    ) -> Dict[str, Any]:
        """Expand sub-graph from any node by label and id."""
        hops = max(1, min(max_hops, 3))
        cypher = (
            f"MATCH (root:`{label}` {{id:$node_id}}) "
            f"OPTIONAL MATCH path=(root)-[rels:{TRAVERSAL_RELATIONSHIPS}*1..{hops}]->(leaf) "
            "RETURN root, path"
        )
        records = await repo._read(cypher, {"node_id": node_id})

        nodes: Dict[str, Dict[str, Any]] = {}
        edges: Dict[Tuple[str, str, str], Dict[str, Any]] = {}

        for record in records:
            root = record.get("root")
            if root:
                self._extract_node(root, nodes)
            path = record.get("path")
            if path is None:
                continue
            path_nodes = getattr(path, "nodes", lambda: [])()
            path_rels = getattr(path, "relationships", lambda: [])()
            for pn in path_nodes:
                self._extract_node(pn, nodes)
            for pr in path_rels:
                self._extract_edge(pr, edges, nodes)

        return {"nodes": list(nodes.values()), "edges": list(edges.values())}

    @staticmethod
    def _extract_node(node_obj: Any, out: Dict[str, Dict[str, Any]]) -> None:
        """Extract a Neo4j node into our flat dict format."""
        try:
            props = dict(node_obj)
            labels = list(getattr(node_obj, "labels", set()))
            nid = props.get("id", "")
            if nid and nid not in out:
                out[nid] = {
                    "id": nid,
                    "label": labels[0] if labels else "Node",
                    "display_name": props.get("display_name", nid),
                    "properties": {k: v for k, v in props.items()
                                  if k not in ("created_at", "updated_at")},
                }
        except Exception as e:
            logger.debug("Node extraction failed: %s", e)

    @staticmethod
    def _extract_edge(
        rel_obj: Any,
        out: Dict[Tuple[str, str, str], Dict[str, Any]],
        nodes: Dict[str, Dict[str, Any]],
    ) -> None:
        """Extract a Neo4j relationship into our flat dict format."""
        try:
            rel_props = dict(rel_obj)
            rel_type = str(rel_obj.type)
            start_node = rel_obj.start_node
            end_node = rel_obj.end_node
            source_id = dict(start_node).get("id", "")
            target_id = dict(end_node).get("id", "")
            if source_id and target_id:
                key = (source_id, rel_type, target_id)
                if key not in out:
                    out[key] = {
                        "source_id": source_id,
                        "target_id": target_id,
                        "relationship": rel_type,
                        "properties": {k: v for k, v in rel_props.items()
                                      if k not in ("created_at", "updated_at")},
                    }
        except Exception as e:
            logger.debug("Edge extraction failed: %s", e)
