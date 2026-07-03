"""
Phase 3 — Entity Resolution & Standardization

Normalizes extracted entities, mapping variant surface forms to canonical Phase 1 IDs.
"""

from __future__ import annotations

import re
from typing import Dict, List
from collections import defaultdict

from .schemas import ExtractedEntity


# Canonical alias map — industrial shorthand -> Phase 1 ID
# Keys MUST be normalized (lowercase, spaces, no punctuation) to match normalize_surface_form()
CANONICAL_ALIAS_MAP: Dict[str, str] = {
    # Pumps
    "centrifugal pump a": "asset:SRP:P-101A",
    "pump a": "asset:SRP:P-101A",
    "cp a": "asset:SRP:P-101A",
    "p 101a": "asset:SRP:P-101A",
    "p101a": "asset:SRP:P-101A",
    # legacy hyphenated keys (resolver will also try hyphen->space fallback)
    "pump-a": "asset:SRP:P-101A",
    "cp-a": "asset:SRP:P-101A",
    "p-101a": "asset:SRP:P-101A",
    # Components
    "drive end bearing": "component:P-101A:BEARING:DE",
    "de bearing": "component:P-101A:BEARING:DE",
    "bearing de": "component:P-101A:BEARING:DE",
    "drive end bearing de": "component:P-101A:BEARING:DE",
    # Sensors
    "te 101a de": "sensor:SRP:TE-101A-DE",
    "te-101a-de": "sensor:SRP:TE-101A-DE",
    "bearing temp sensor": "sensor:SRP:TE-101A-DE",
    "rtd de": "sensor:SRP:TE-101A-DE",
    "bearing temperature sensor": "sensor:SRP:TE-101A-DE",
    # Failure modes
    "bearing overheat": "failuremode:ROTARY_EQUIPMENT:BEARING:overheat",
    "overheating": "failuremode:ROTARY_EQUIPMENT:BEARING:overheat",
    "high bearing temp": "failuremode:ROTARY_EQUIPMENT:BEARING:overheat",
    # Root causes
    "under lubrication": "rootcause:MAINTENANCE:under_lubrication",
    "lack of grease": "rootcause:MAINTENANCE:under_lubrication",
    "under lubrication": "rootcause:MAINTENANCE:under_lubrication",
}

# reverse map for display_name canonicalization
ID_TO_DISPLAY = {
    "asset:SRP:P-101A": "Pump P-101A",
    "component:P-101A:BEARING:DE": "Drive-end bearing",
    "sensor:SRP:TE-101A-DE": "Drive-end bearing RTD",
    "failuremode:ROTARY_EQUIPMENT:BEARING:overheat": "Bearing overheat",
    "rootcause:MAINTENANCE:under_lubrication": "Under-lubrication",
    "sop:SOP-114:REV-C": "SOP-114 Bearing Lubrication",
    "tooling:TORQUE-WRENCH-50NM": "50 Nm torque wrench",
}


def normalize_surface_form(s: str) -> str:
    return re.sub(r"[^a-z0-9]+", " ", s.lower()).strip()


def resolve_entity_id(display_name: str, label: str, fallback_id: str | None = None) -> str:
    """
    Map variant text to canonical Phase 1 ID.
    1. Exact tag match
    2. Alias map lookup
    3. Construct ID heuristically if fallback provided
    """
    key = normalize_surface_form(display_name)
    # try normalized key
    if key in CANONICAL_ALIAS_MAP:
        return CANONICAL_ALIAS_MAP[key]
    # try raw lowercased (preserves hyphens)
    raw_key = display_name.lower().strip()
    if raw_key in CANONICAL_ALIAS_MAP:
        return CANONICAL_ALIAS_MAP[raw_key]
    # try hyphenated version of normalized key
    hyphen_key = key.replace(" ", "-")
    if hyphen_key in CANONICAL_ALIAS_MAP:
        return CANONICAL_ALIAS_MAP[hyphen_key]
    # tag-like pattern e.g. P-101A, TE-101A-DE, CP-A
    tag_match = re.search(r"\b([A-Z]{1,3}[-_ ]?\d{0,4}[A-Z]?(?:[-_][A-Z]{1,3})?)\b", display_name.upper())
    if tag_match:
        tag = tag_match.group(1).replace(" ", "-").replace("_", "-")
        if label == "Asset" and (tag.startswith("P-") or tag in ("CP-A", "PUMP-A", "PUMP-A")):
            # canonicalize CP-A / Pump-A to P-101A
            return "asset:SRP:P-101A"
        if label == "Sensor" and tag.startswith("TE-"):
            return f"sensor:SRP:{tag}"
    # Special case: CP-A / Pump-A
    if label == "Asset" and key in ("cp a", "pump a", "centrifugal pump a", "cp-a", "pump-a"):
        return "asset:SRP:P-101A"
    return fallback_id or f"{label.lower()}:SRP:{key.replace(' ', '_')}"


def deduplicate_entities(entities: List[ExtractedEntity]) -> List[ExtractedEntity]:
    """
    Merge duplicate entities by canonical entity_id.
    Combines aliases, properties (first-wins), keeps max confidence.
    """
    merged: Dict[str, ExtractedEntity] = {}
    for e in entities:
        # resolve ID
        canonical_id = CANONICAL_ALIAS_MAP.get(normalize_surface_form(e.display_name), e.entity_id)
        # also resolve via alias list
        for alias in e.aliases:
            alias_key = normalize_surface_form(alias)
            if alias_key in CANONICAL_ALIAS_MAP:
                canonical_id = CANONICAL_ALIAS_MAP[alias_key]
                break

        # enforce display_name canonicalization
        display_name = ID_TO_DISPLAY.get(canonical_id, e.display_name)

        # If not yet seen, store (with corrected id)
        if canonical_id not in merged:
            # copy with corrected ID
            new_e = e.model_copy(update={"entity_id": canonical_id, "display_name": display_name})
            # ensure alias list includes original surface form
            aliases = set(new_e.aliases or [])
            aliases.add(e.display_name)
            if e.entity_id != canonical_id:
                aliases.add(e.entity_id)
            new_e.aliases = sorted(aliases)
            merged[canonical_id] = new_e
        else:
            existing = merged[canonical_id]
            # merge aliases
            alias_set = set(existing.aliases or []) | set(e.aliases or []) | {e.display_name}
            existing.aliases = sorted(alias_set)
            # max confidence
            if e.confidence > existing.confidence:
                existing.confidence = e.confidence
                # update properties conservatively (keep existing keys, add missing)
                for k, v in e.properties.items():
                    if k not in existing.properties or existing.properties[k] in (None, "", [], {}):
                        existing.properties[k] = v
            # merge properties missing
            for k, v in e.properties.items():
                existing.properties.setdefault(k, v)
    return list(merged.values())


def build_alias_registry(entities: List[ExtractedEntity]) -> Dict[str, List[str]]:
    """Return {canonical_id: [aliases]} for audit."""
    reg: Dict[str, List[str]] = {}
    for e in entities:
        reg[e.entity_id] = sorted(set((e.aliases or []) + [e.display_name]))
    return reg
