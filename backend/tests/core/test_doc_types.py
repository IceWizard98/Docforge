"""Step 0 — canonical doc_type taxonomy (TDD)."""

from core.doc_types import CANONICAL_DOC_TYPES, normalize


class TestCanonicalList:
    def test_contains_expected_types(self):
        assert "contract" in CANONICAL_DOC_TYPES
        assert "nda" in CANONICAL_DOC_TYPES
        assert "company_profile" in CANONICAL_DOC_TYPES
        assert "service_sheet" in CANONICAL_DOC_TYPES
        assert "technical_doc" in CANONICAL_DOC_TYPES
        assert "other" in CANONICAL_DOC_TYPES

    def test_other_is_fallback_member(self):
        # "other" must be a real member so filters/schemas can rely on it.
        assert CANONICAL_DOC_TYPES[-1] == "other"


class TestNormalizeHappy:
    def test_identity_for_canonical(self):
        for t in CANONICAL_DOC_TYPES:
            assert normalize(t) == t

    def test_case_insensitive(self):
        assert normalize("Contract") == "contract"
        assert normalize("CONTRACT") == "contract"

    def test_italian_alias(self):
        assert normalize("Contratto") == "contract"
        assert normalize("contratto") == "contract"

    def test_english_alias(self):
        assert normalize("agreement") == "contract"
        assert normalize("non-disclosure agreement") == "nda"

    def test_company_profile_alias(self):
        assert normalize("profilo aziendale") == "company_profile"

    def test_service_sheet_alias(self):
        assert normalize("scheda servizi") == "service_sheet"

    def test_technical_doc_alias(self):
        assert normalize("documentazione tecnica") == "technical_doc"

    def test_whitespace_stripped(self):
        assert normalize("  contract  ") == "contract"


class TestNormalizeEdge:
    def test_unknown_falls_back_to_other(self):
        assert normalize("report") == "other"
        assert normalize("memo") == "other"
        assert normalize("banana") == "other"

    def test_none_falls_back_to_other(self):
        assert normalize(None) == "other"

    def test_empty_falls_back_to_other(self):
        assert normalize("") == "other"
        assert normalize("   ") == "other"

    def test_legacy_unknown_value(self):
        # Older rows stored "unknown" before the canonical taxonomy existed.
        assert normalize("unknown") == "other"


class TestNormalizeError:
    def test_non_string_falls_back_to_other(self):
        assert normalize(123) == "other"  # type: ignore[arg-type]
        assert normalize(["contract"]) == "other"  # type: ignore[arg-type]


class TestSingleAliasSource:
    """normalize and SlotSchemaService.match_alias share one alias table."""

    def test_resolvers_agree_on_every_alias(self):
        from core.services.slot_schema import get_slot_schema_service

        svc = get_slot_schema_service()
        for alias, doc_type in svc.alias_pairs():
            assert normalize(alias) == doc_type, alias
            assert svc.match_alias(alias) == doc_type, alias
