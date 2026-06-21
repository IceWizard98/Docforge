"""Canonical document-type taxonomy.

Single source of truth shared by the classification worker, slot schemas and
retrieval filters. The classifier is constrained to emit one of these values;
legacy / free-form values are mapped here via :func:`normalize`.
"""

CANONICAL_DOC_TYPES: list[str] = [
    "contract",
    "nda",
    "company_profile",
    "service_sheet",
    "technical_doc",
    "other",
]


def _alias_pairs() -> list[tuple[str, str]]:
    """(alias, canonical) pairs from the slot-schema registry, longest first.

    Single source of truth: type synonyms live only in the slot-schema YAML
    files. Canonical names are added as their own aliases so a bare type string
    still matches even if it has no schema.
    """
    # Imported lazily to keep core/doc_types import-light and avoid cycles.
    from core.services.slot_schema import get_slot_schema_service

    pairs = list(get_slot_schema_service().alias_pairs())
    pairs.extend((c, c) for c in CANONICAL_DOC_TYPES if c != "other")
    pairs.sort(key=lambda p: len(p[0]), reverse=True)
    return pairs


def normalize(raw: object) -> str:
    """Map a raw/free-form doc_type to a canonical type, defaulting to ``other``.

    Robust to ``None``, non-string input, casing, surrounding whitespace and the
    multilingual aliases declared in the slot-schema files.
    """
    if not isinstance(raw, str):
        return "other"
    value = raw.strip().lower()
    if not value:
        return "other"
    if value in CANONICAL_DOC_TYPES:
        return value
    pairs = _alias_pairs()
    # Exact alias first, then substring (e.g. "mutual non-disclosure agreement").
    for alias, canonical in pairs:
        if alias == value:
            return canonical
    for alias, canonical in pairs:
        if alias in value:
            return canonical
    return "other"
