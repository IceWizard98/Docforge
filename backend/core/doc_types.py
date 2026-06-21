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

# Alias -> canonical type. Keys are matched case-insensitively against the raw
# value (exact, then substring). Keep canonical identities implicit (each type
# maps to itself) so we only list real synonyms here.
_ALIASES: dict[str, str] = {
    # contract
    "contratto": "contract",
    "agreement": "contract",
    "accordo": "contract",
    # nda
    "non-disclosure": "nda",
    "non disclosure": "nda",
    "non-disclosure agreement": "nda",
    "accordo di riservatezza": "nda",
    "riservatezza": "nda",
    "confidentiality": "nda",
    "confidentiality agreement": "nda",
    # company profile
    "company profile": "company_profile",
    "profilo aziendale": "company_profile",
    "company-profile": "company_profile",
    # service sheet
    "service sheet": "service_sheet",
    "scheda servizi": "service_sheet",
    "scheda servizio": "service_sheet",
    "service-sheet": "service_sheet",
    # technical documentation
    "technical": "technical_doc",
    "technical documentation": "technical_doc",
    "documentazione tecnica": "technical_doc",
    "manual": "technical_doc",
    "manuale": "technical_doc",
}


def normalize(raw: object) -> str:
    """Map a raw/free-form doc_type to a canonical type, defaulting to ``other``.

    Robust to ``None``, non-string input, casing, surrounding whitespace and a
    set of multilingual aliases.
    """
    if not isinstance(raw, str):
        return "other"
    value = raw.strip().lower()
    if not value:
        return "other"
    if value in CANONICAL_DOC_TYPES:
        return value
    if value in _ALIASES:
        return _ALIASES[value]
    # Substring match: e.g. "mutual non-disclosure agreement" -> nda. Canonical
    # names act as their own aliases (excluding the "other" catch-all).
    candidates = {**_ALIASES, **{c: c for c in CANONICAL_DOC_TYPES if c != "other"}}
    for alias, canonical in candidates.items():
        if alias in value:
            return canonical
    return "other"
