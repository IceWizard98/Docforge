"""Step 4 — intent inference (TDD)."""

from unittest.mock import AsyncMock

import pytest

from core.services.intent import DraftIntent, IntentInferenceService, SlotState


def _msgs(*texts: str) -> list[dict]:
    return [{"role": "user", "content": t} for t in texts]


class TestInferHappy:
    @pytest.mark.asyncio
    async def test_llm_doc_type_and_slot_states(self):
        llm = AsyncMock()
        llm.generate_structured = AsyncMock(return_value={
            "doc_type": "nda",
            "doc_type_confidence": 0.9,
            "title_guess": "NDA Acme-Beta",
            "slots": [
                {"slot_id": "parties", "status": "known", "value_summary": "Acme, Beta"},
                {"slot_id": "governing_law", "status": "missing"},
            ],
        })
        svc = IntentInferenceService(llm=llm)
        intent = await svc.infer(_msgs("Scrivimi un NDA tra Acme e Beta"))

        assert isinstance(intent, DraftIntent)
        assert intent.doc_type == "nda"
        assert intent.doc_type_confidence == pytest.approx(0.9)
        states = {s.slot_id: s for s in intent.slots}
        assert states["parties"].status == "known"
        assert states["governing_law"].status == "missing"
        # required slots not returned by the LLM default to missing
        assert "confidential_info" in states
        assert states["confidential_info"].status == "missing"

    @pytest.mark.asyncio
    async def test_deterministic_alias_without_llm(self):
        svc = IntentInferenceService(llm=None)
        intent = await svc.infer(_msgs("Prepariamo un contratto di fornitura"))
        assert intent.doc_type == "contract"
        # all schema slots present and missing (no LLM to fill them)
        assert intent.slots
        assert all(s.status == "missing" for s in intent.slots)


class TestInferEdge:
    @pytest.mark.asyncio
    async def test_llm_doc_type_not_in_registry_falls_back(self):
        llm = AsyncMock()
        llm.generate_structured = AsyncMock(return_value={"doc_type": "poem", "slots": []})
        svc = IntentInferenceService(llm=llm)
        intent = await svc.infer(_msgs("scrivi qualcosa"))
        assert intent.doc_type is None
        assert intent.slots == []

    @pytest.mark.asyncio
    async def test_ambiguous_returns_none_doc_type(self):
        llm = AsyncMock()
        llm.generate_structured = AsyncMock(return_value={"doc_type": None, "slots": []})
        svc = IntentInferenceService(llm=llm)
        intent = await svc.infer(_msgs("ciao come va"))
        assert intent.doc_type is None

    @pytest.mark.asyncio
    async def test_empty_messages_no_doc_type(self):
        svc = IntentInferenceService(llm=None)
        intent = await svc.infer([])
        assert intent.doc_type is None
        assert intent.slots == []


class TestInferError:
    @pytest.mark.asyncio
    async def test_llm_raises_falls_back_to_deterministic(self):
        llm = AsyncMock()
        llm.generate_structured = AsyncMock(side_effect=ValueError("bad json"))
        svc = IntentInferenceService(llm=llm)
        # deterministic alias still recovers the type
        intent = await svc.infer(_msgs("Redigi un contratto"))
        assert intent.doc_type == "contract"
        assert all(s.status == "missing" for s in intent.slots)

    @pytest.mark.asyncio
    async def test_llm_raises_no_alias_returns_none(self):
        llm = AsyncMock()
        llm.generate_structured = AsyncMock(side_effect=ValueError("boom"))
        svc = IntentInferenceService(llm=llm)
        intent = await svc.infer(_msgs("aiutami con una cosa"))
        assert intent.doc_type is None

    @pytest.mark.asyncio
    async def test_slot_state_dataclass_defaults(self):
        s = SlotState(slot_id="x", status="missing")
        assert s.value_summary == ""
        assert s.source == "none"
