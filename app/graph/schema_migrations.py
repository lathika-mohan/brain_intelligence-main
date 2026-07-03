"""
Phase 2 Neo4j schema migration registry — the SINGLE SOURCE OF TRUTH for all
database constraints, indexes, and the native vector index.

This module is intentionally Cypher-aware but database-*driver*-free at import
time (it only builds statement strings). The async :func:`apply_migrations`
runner is the only place that touches a live driver.

It expands the Phase 0 ``docs/neo4j_schema.md`` (5 labels) to the full
16-label Phase 1 industrial ontology in ``app.models.ontology`` and adds:

* **Uniqueness constraints** (``IS UNIQUE``) on ``id`` for all 16 node labels.
* **IS NOT NULL property-existence constraints** on critical operational
  fields — *Enterprise Edition only* (Community does not enforce them); the
  runner applies these conditionally and documents the intent in the
  generated ``.cypher`` artifacts either way.
* **RANGE** + **TEXT** indexes on frequently queried/filtered fields to keep
  future GraphRAG lookups fast.
* **Native VECTOR** indexes on embedding-bearing description fields
  (``FailureMode.embedding``, ``SOPStep.embedding``) so Phase 3 can blend
  structural traversal with semantic similarity without a second round-trip.

All generated statements are idempotent (``IF NOT EXISTS``) so re-running the
bootstrap is safe.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Optional

logger = logging.getLogger(__name__)

# --------------------------------------------------------------------------- #
# Catalogue
# --------------------------------------------------------------------------- #
# The 16 canonical Phase 1 node labels (PascalCase), in dependency-light order.
NODE_LABELS: tuple[str, ...] = (
    "Location",
    "Asset",
    "Component",
    "Sensor",
    "TelemetryStream",
    "FailureMode",
    "RootCause",
    "FailureSymptom",
    "MaintenanceTask",
    "SOP",
    "SOPStep",
    "SafetyHazard",
    "Tooling",
    "OperatorRole",
    "SourceDocument",
    "TextChunk",
)

# Critical non-nullable fields per label (Enterprise-only existence constraints).
EXISTENCE_FIELDS: dict[str, tuple[str, ...]] = {
    "Location": ("display_name", "location_type", "site_code"),
    "Asset": (
        "display_name",
        "asset_type",
        "equipment_class",
        "tag",
        "status",
        "criticality",
        "location_id",
        "process_function",
    ),
    "Component": ("display_name", "asset_id", "component_type", "criticality"),
    "Sensor": (
        "display_name",
        "sensor_category",
        "metric",
        "unit",
        "asset_id",
        "tag",
        "sampling_method",
        "sampling_frequency_hz",
    ),
    "TelemetryStream": ("display_name", "sensor_id", "asset_id", "metric", "unit"),
    "FailureMode": (
        "display_name",
        "equipment_class",
        "severity_tier",
        "mechanisms",
    ),
    "RootCause": ("display_name", "category", "causal_statement"),
    "FailureSymptom": ("display_name", "observed_signal"),
    "MaintenanceTask": ("display_name", "task_type", "asset_id", "priority"),
    "SOP": ("display_name", "sop_number", "title", "revision", "status"),
    "SOPStep": ("display_name", "sop_id", "sequence_number", "step_type", "instruction"),
    "SafetyHazard": ("display_name", "category", "risk_level", "hazard_statement"),
    "Tooling": ("display_name", "tool_type", "calibrated"),
    "OperatorRole": ("display_name", "role_code", "permissions"),
    "SourceDocument": ("display_name", "source_type", "source_document"),
    "TextChunk": (
        "display_name",
        "chunk_id",
        "source_document_id",
        "source_document",
        "source_type",
        "text",
    ),
}

# RANGE indexes (equality / numeric-range / sorting). (label, property)
RANGE_INDEX_FIELDS: tuple[tuple[str, str], ...] = (
    ("Asset", "status"),
    ("Asset", "criticality"),
    ("Asset", "location_id"),
    ("Asset", "asset_type"),
    ("Asset", "equipment_class"),
    ("Component", "asset_id"),
    ("Component", "component_type"),
    ("Component", "maintainable"),
    ("Sensor", "asset_id"),
    ("Sensor", "component_id"),
    ("Sensor", "sensor_category"),
    ("Sensor", "sampling_frequency_hz"),
    ("TelemetryStream", "sensor_id"),
    ("FailureMode", "equipment_class"),
    ("FailureMode", "component_type"),
    ("FailureMode", "severity_tier"),
    ("MaintenanceTask", "asset_id"),
    ("MaintenanceTask", "component_id"),
    ("MaintenanceTask", "priority"),
    ("SOP", "status"),
    ("SOP", "safety_critical"),
    ("RootCause", "category"),
    ("SafetyHazard", "risk_level"),
    ("OperatorRole", "role_code"),
    ("TextChunk", "source_document_id"),
    ("TextChunk", "source_type"),
)

# TEXT indexes (substring / prefix search). (label, property)
TEXT_INDEX_FIELDS: tuple[tuple[str, str], ...] = (
    ("Location", "display_name"),
    ("Location", "site_code"),
    ("Asset", "display_name"),
    ("Asset", "tag"),
    ("Asset", "process_function"),
    ("Component", "display_name"),
    ("Component", "component_position"),
    ("Sensor", "display_name"),
    ("Sensor", "tag"),
    ("Sensor", "metric"),
    ("FailureMode", "display_name"),
    ("FailureMode", "failure_effect"),
    ("FailureMode", "iso_14224_code"),
    ("RootCause", "causal_statement"),
    ("FailureSymptom", "observed_signal"),
    ("SOP", "title"),
    ("SOP", "sop_number"),
    ("SOPStep", "instruction"),
    ("SafetyHazard", "hazard_statement"),
    ("Tooling", "tool_type"),
    ("OperatorRole", "role_code"),
    ("SourceDocument", "source_document"),
    ("TextChunk", "text"),
)

# Native VECTOR indexes for hybrid structural+semantic GraphRAG traversal.
# These reference an ``embedding`` property that Phase 3 (embeddings) will
# populate; the index can be created ahead of population.
DEFAULT_VECTOR_DIMENSIONS = 384  # mirrors settings.qdrant_vector_size
DEFAULT_VECTOR_SIMILARITY = "cosine"

VECTOR_INDEXES: tuple[tuple[str, str], ...] = (
    ("FailureMode", "embedding"),
    ("SOPStep", "embedding"),
)


# --------------------------------------------------------------------------- #
# Statement builders (pure)
# --------------------------------------------------------------------------- #
def uniqueness_statements() -> list[str]:
    out = []
    for label in NODE_LABELS:
        name = f"un_{label}_id"
        out.append(
            f"CREATE CONSTRAINT {name} IF NOT EXISTS "
            f"FOR (n:`{label}`) REQUIRE n.id IS UNIQUE;"
        )
    return out


def existence_statements() -> list[str]:
    out = []
    for label, fields in EXISTENCE_FIELDS.items():
        for prop in fields:
            name = f"exists_{label}_{prop}"
            out.append(
                f"CREATE CONSTRAINT {name} IF NOT EXISTS "
                f"FOR (n:`{label}`) REQUIRE n.{prop} IS NOT NULL;"
            )
    return out


def range_index_statements() -> list[str]:
    out = []
    for label, prop in RANGE_INDEX_FIELDS:
        name = f"range_{label}_{prop}"
        out.append(
            f"CREATE RANGE INDEX {name} IF NOT EXISTS FOR (n:`{label}`) ON (n.{prop});"
        )
    return out


def text_index_statements() -> list[str]:
    out = []
    for label, prop in TEXT_INDEX_FIELDS:
        name = f"text_{label}_{prop}"
        out.append(
            f"CREATE TEXT INDEX {name} IF NOT EXISTS FOR (n:`{label}`) ON (n.{prop});"
        )
    return out


def vector_index_statements(
    *,
    dimensions: int = DEFAULT_VECTOR_DIMENSIONS,
    similarity: str = DEFAULT_VECTOR_SIMILARITY,
) -> list[str]:
    out = []
    for label, prop in VECTOR_INDEXES:
        name = f"vector_{label}_{prop}"
        out.append(
            "CREATE VECTOR INDEX "
            f"{name} IF NOT EXISTS "
            f"FOR (n:`{label}`) ON (n.{prop}) "
            "OPTIONS {indexConfig: {"
            f"`vector.dimensions`: {dimensions}, "
            f"`vector.similarity_function`: '{similarity}'"
            "}};"
        )
    return out


# --------------------------------------------------------------------------- #
# File rendering (drives the deliverable .cypher artifacts)
# --------------------------------------------------------------------------- #
@dataclass
class Section:
    filename: str
    title: str
    note: str
    statements: list[str]


def _render_section(section: Section) -> str:
    lines = [
        "// ===========================================================================",
        f"// {section.title}",
        "// ---------------------------------------------------------------------------",
        f"// {section.note}",
        "// Generated from app/graph/schema_migrations.py — edit the registry, not here.",
        "// ===========================================================================",
        "",
    ]
    for stmt in section.statements:
        lines.append(stmt)
        lines.append("")
    return "\n".join(lines)


def render_migration_files(
    *,
    dimensions: int = DEFAULT_VECTOR_DIMENSIONS,
    similarity: str = DEFAULT_VECTOR_SIMILARITY,
) -> dict[str, str]:
    """Render the idempotent ``.cypher`` migration artifacts as a name->content map."""
    sections = [
        Section(
            filename="001_constraints.cypher",
            title="Phase 2 — Uniqueness constraints (all 16 Phase 1 node labels)",
            note="Community + Enterprise safe. Enforces the canonical graph key `id`.",
            statements=uniqueness_statements(),
        ),
        Section(
            filename="002_indexes.cypher",
            title="Phase 2 — RANGE + TEXT indexes for fast GraphRAG retrieval",
            note="Community + Enterprise safe. Backs filters, sorting, and substring search.",
            statements=range_index_statements() + text_index_statements(),
        ),
        Section(
            filename="003_vector_index.cypher",
            title="Phase 2 — Native VECTOR indexes for hybrid semantic traversal",
            note="Community 5.11+ / Enterprise safe. Indexes are created before `embedding` is populated.",
            statements=vector_index_statements(dimensions=dimensions, similarity=similarity),
        ),
        Section(
            filename="004_existence_constraints_enterprise.cypher",
            title="Phase 2 — IS NOT NULL property-existence constraints",
            note=(
                "ENTERPRISE EDITION ONLY. Community silently ignores these. The Python "
                "runner (apply_migrations) applies them conditionally based on dbms edition."
            ),
            statements=existence_statements(),
        ),
    ]
    return {section.filename: _render_section(section) for section in sections}


# --------------------------------------------------------------------------- #
# Async runner
# --------------------------------------------------------------------------- #
@dataclass
class MigrationReport:
    """Outcome of a schema migration run."""

    applied: list[str] = field(default_factory=list)
    skipped: list[str] = field(default_factory=list)
    edition: Optional[str] = None
    errors: list[str] = field(default_factory=list)


async def _detect_edition(driver, database: Optional[str]) -> Optional[str]:
    """Introspect the *given* driver for its edition (enterprise/community)."""
    try:
        async with driver.session(database=database) as session:
            result = await session.run(
                "CALL dbms.components() YIELD edition RETURN toLower(edition) AS edition"
            )
            record = await result.single()
            return record["edition"] if record is not None else None
    except Exception:  # noqa: BLE001 - edition is best-effort
        return None


async def apply_migrations(
    driver,
    *,
    apply_existence: Optional[bool] = None,
    database: Optional[str] = None,
) -> MigrationReport:
    """Idempotently apply the full Phase 2 schema to a live Neo4j driver.

    Parameters
    ----------
    driver:
        An async :class:`neo4j.AsyncDriver` (e.g. from
        :func:`app.graph.client.get_async_driver`). Edition detection is
        performed against this driver, so it works regardless of environment
        wiring.
    apply_existence:
        Force whether IS NOT NULL constraints are applied. When ``None`` they
        are only applied on detected Enterprise Edition (Community cannot
        enforce property-existence constraints).
    database:
        Target database name; defaults to the driver session default.
    """
    report = MigrationReport(edition=await _detect_edition(driver, database))
    if apply_existence is None:
        apply_existence = report.edition == "enterprise"

    community_statements = [
        *uniqueness_statements(),
        *range_index_statements(),
        *text_index_statements(),
        *vector_index_statements(),
    ]
    existence_statements_list = existence_statements()

    async def _run_all(statements: list[str], sink: list[str]) -> None:
        async with driver.session(database=database) as session:
            for stmt in statements:
                try:
                    await (await session.run(stmt)).consume()
                    sink.append(stmt)
                except Exception as exc:  # noqa: BLE001 - record then continue
                    report.errors.append(f"{type(exc).__name__}: {stmt} -> {exc}")

    await _run_all(community_statements, report.applied)
    if apply_existence:
        await _run_all(existence_statements_list, report.applied)
    else:
        report.skipped.extend(existence_statements_list)
        if existence_statements_list:
            logger.info(
                "Skipped %d IS NOT NULL (Enterprise-only) constraints — "
                "edition=%s. Apply on Enterprise or pass apply_existence=True.",
                len(existence_statements_list),
                report.edition,
            )

    logger.info(
        "Neo4j migrations applied: %d statements (%d skipped existence, %d errors).",
        len(report.applied),
        len(report.skipped),
        len(report.errors),
    )
    return report
