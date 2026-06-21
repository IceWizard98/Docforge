"""Slot-schema registry.

Per-doc-type "information slot" schemas, loaded from data files
(``core/slot_schemas/*.yaml``). A slot describes a piece of information a
document type needs; downstream services use the slots to drive targeted
retrieval and to flag missing/ambiguous information.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path

import yaml

logger = logging.getLogger(__name__)

_SCHEMA_DIR = Path(__file__).resolve().parent.parent / "slot_schemas"


class SlotSchemaError(Exception):
    """Raised when a slot-schema file is malformed or invalid."""


@dataclass(frozen=True)
class Slot:
    id: str
    label: str
    description: str = ""
    required: bool = False
    retrieval_query_hint: str = ""


@dataclass(frozen=True)
class SlotSchema:
    doc_type: str
    label: str
    aliases: list[str] = field(default_factory=list)
    slots: list[Slot] = field(default_factory=list)


class SlotSchemaService:
    """Loads and serves slot schemas from the data directory."""

    def __init__(self, schema_dir: Path | None = None):
        self._dir = schema_dir or _SCHEMA_DIR
        self._schemas: dict[str, SlotSchema] = {}
        self._alias_index: dict[str, str] = {}
        self._load_all()

    def _load_all(self) -> None:
        if not self._dir.is_dir():
            logger.warning("Slot-schema directory not found: %s", self._dir)
            return
        for path in sorted(self._dir.glob("*.yaml")):
            try:
                schema = self.load_file(path)
            except SlotSchemaError:
                logger.exception("Skipping invalid slot schema %s", path)
                continue
            self._register(schema)

    def _register(self, schema: SlotSchema) -> None:
        self._schemas[schema.doc_type] = schema
        self._alias_index[schema.doc_type.lower()] = schema.doc_type
        if schema.label:
            self._alias_index[schema.label.lower()] = schema.doc_type
        for alias in schema.aliases:
            self._alias_index[alias.lower()] = schema.doc_type

    def load_file(self, path: Path) -> SlotSchema:
        """Parse and validate a single slot-schema file.

        Raises :class:`SlotSchemaError` on malformed YAML or missing required keys.
        """
        try:
            raw = yaml.safe_load(path.read_text(encoding="utf-8"))
        except yaml.YAMLError as e:
            raise SlotSchemaError(f"Malformed YAML in {path}: {e}") from e
        if not isinstance(raw, dict):
            raise SlotSchemaError(f"Slot schema {path} must be a mapping")
        doc_type = raw.get("doc_type")
        if not doc_type or not isinstance(doc_type, str):
            raise SlotSchemaError(f"Slot schema {path} missing 'doc_type'")

        slots: list[Slot] = []
        for entry in raw.get("slots") or []:
            if not isinstance(entry, dict):
                raise SlotSchemaError(f"Slot in {path} must be a mapping")
            slot_id = entry.get("id")
            if not slot_id or not isinstance(slot_id, str):
                raise SlotSchemaError(f"Slot in {path} missing 'id'")
            slots.append(Slot(
                id=slot_id,
                label=str(entry.get("label", slot_id)),
                description=str(entry.get("description", "")),
                required=bool(entry.get("required", False)),
                retrieval_query_hint=str(entry.get("retrieval_query_hint", "")),
            ))

        return SlotSchema(
            doc_type=doc_type,
            label=str(raw.get("label", doc_type)),
            aliases=[str(a) for a in (raw.get("aliases") or [])],
            slots=slots,
        )

    def get(self, doc_type: str) -> SlotSchema | None:
        """Return the schema for a canonical doc_type, or None if none exists."""
        return self._schemas.get(doc_type)

    def list_doc_types(self) -> list[str]:
        """Canonical doc_types that have a slot schema."""
        return list(self._schemas.keys())

    def match_alias(self, text: str) -> str | None:
        """Resolve free-form text to a known doc_type via aliases, else None."""
        if not isinstance(text, str):
            return None
        return self._alias_index.get(text.strip().lower())

    def alias_pairs(self) -> list[tuple[str, str]]:
        """(alias, doc_type) pairs, longest alias first (for substring matching).

        Single source of truth for type synonyms — consumed by both intent
        inference and doc_type normalization so they can never drift.
        """
        return sorted(self._alias_index.items(), key=lambda p: len(p[0]), reverse=True)


@lru_cache(maxsize=1)
def get_slot_schema_service() -> SlotSchemaService:
    """Process-wide singleton: slot schemas are static data, parse them once."""
    return SlotSchemaService()
