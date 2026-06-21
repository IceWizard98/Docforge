"""Step 3 — slot-schema loader (TDD)."""

import pytest

from core.doc_types import CANONICAL_DOC_TYPES
from core.services.slot_schema import SlotSchema, SlotSchemaError, SlotSchemaService


@pytest.fixture
def service():
    return SlotSchemaService()


class TestLoadHappy:
    def test_get_contract_has_required_slots(self, service):
        schema = service.get("contract")
        assert isinstance(schema, SlotSchema)
        assert schema.doc_type == "contract"
        assert any(s.required for s in schema.slots)
        # every slot has a non-empty id
        assert all(s.id for s in schema.slots)

    def test_all_seeded_types_load(self, service):
        for dt in ["contract", "nda", "company_profile", "service_sheet", "technical_doc"]:
            schema = service.get(dt)
            assert schema is not None, dt
            assert schema.slots, f"{dt} has no slots"

    def test_list_doc_types_subset_of_canonical(self, service):
        types = service.list_doc_types()
        assert set(types).issubset(set(CANONICAL_DOC_TYPES))
        assert "contract" in types

    def test_slot_has_retrieval_hint(self, service):
        schema = service.get("contract")
        assert any(s.retrieval_query_hint for s in schema.slots)


class TestEdge:
    def test_alias_resolution(self, service):
        assert service.match_alias("contratto") == "contract"
        assert service.match_alias("agreement") == "contract"
        assert service.match_alias("profilo aziendale") == "company_profile"

    def test_match_alias_case_insensitive(self, service):
        assert service.match_alias("Contratto") == "contract"

    def test_unknown_doc_type_returns_none(self, service):
        assert service.get("banana") is None
        assert service.get("other") is None  # "other" has no slot schema

    def test_unknown_alias_returns_none(self, service):
        assert service.match_alias("qualcosa di strano") is None


class TestError:
    def test_malformed_yaml_raises(self, tmp_path, service):
        bad = tmp_path / "broken.yaml"
        bad.write_text("doc_type: contract\nslots: [unclosed", encoding="utf-8")
        with pytest.raises(SlotSchemaError):
            service.load_file(bad)

    def test_missing_slot_id_rejected(self, tmp_path, service):
        bad = tmp_path / "noid.yaml"
        bad.write_text(
            "doc_type: x\nlabel: X\naliases: []\nslots:\n  - label: NoId\n",
            encoding="utf-8",
        )
        with pytest.raises(SlotSchemaError):
            service.load_file(bad)

    def test_missing_doc_type_rejected(self, tmp_path, service):
        bad = tmp_path / "nodt.yaml"
        bad.write_text("label: X\nslots: []\n", encoding="utf-8")
        with pytest.raises(SlotSchemaError):
            service.load_file(bad)
