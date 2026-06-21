"""Step 5 — per-slot targeted retrieval (TDD)."""

from unittest.mock import AsyncMock

import pytest

from core.services.context import ContextChunk, ContextPack, ContextSource
from core.services.slot_retrieval import SlotContextPack, SlotFill, SlotRetrievalService


def _pack(chunks: list[ContextChunk]) -> ContextPack:
    sources: list[ContextSource] = []
    if chunks:
        # group naively by source_doc_id
        by_doc: dict[str, list[ContextChunk]] = {}
        for c in chunks:
            by_doc.setdefault(c.source_doc_id, []).append(c)
        sources = [ContextSource(doc_id=d, chunks=cs) for d, cs in by_doc.items()]
    return ContextPack(sources=sources, total_tokens=sum(len(c.content) // 4 for c in chunks))


def _ctx_returning(mapping: dict[str, ContextPack]):
    """Fake ContextPackService keyed by the query (section_title)."""
    ctx = AsyncMock()

    async def _build(**kwargs):
        return mapping.get(kwargs.get("section_title", ""), ContextPack())

    ctx.build_section_context = AsyncMock(side_effect=_build)
    return ctx


class TestSlotRetrievalHappy:
    @pytest.mark.asyncio
    async def test_filled_missing_split(self):
        # contract has known slot ids: parties, object, term_duration, ...
        mapping = {
            # parties hint -> strong result
            "parti, denominazione, ragione sociale, sede legale, codice fiscale": _pack([
                ContextChunk(chunk_id="c1", content="Acme S.p.A. e Beta Srl", source_doc_id="s1", relevance_score=1.0),
            ]),
        }
        ctx = _ctx_returning(mapping)
        svc = SlotRetrievalService(context_service=ctx)
        pack = await svc.build_slot_context("contract")

        assert isinstance(pack, SlotContextPack)
        assert pack.doc_type == "contract"
        by_id = {s.slot_id: s for s in pack.slots}
        assert by_id["parties"].status == "filled"
        assert by_id["parties"].confidence_bucket == "high"
        assert by_id["parties"].chunks
        # a slot with no results is missing
        assert by_id["object"].status == "missing"
        assert by_id["object"].chunks == []

    @pytest.mark.asyncio
    async def test_searches_whole_corpus_unfiltered(self):
        ctx = _ctx_returning({})
        svc = SlotRetrievalService(context_service=ctx)
        await svc.build_slot_context("nda")
        # evidence for a slot may live in any source type -> no doc_type scoping
        assert ctx.build_section_context.await_args_list
        for call in ctx.build_section_context.await_args_list:
            assert call.kwargs.get("filters") is None


class TestSlotRetrievalEdge:
    @pytest.mark.asyncio
    async def test_unknown_doc_type_empty_pack(self):
        ctx = _ctx_returning({})
        svc = SlotRetrievalService(context_service=ctx)
        pack = await svc.build_slot_context("banana")
        assert pack.slots == []

    @pytest.mark.asyncio
    async def test_required_missing_slots_reported(self):
        ctx = _ctx_returning({})  # nothing found for any slot
        svc = SlotRetrievalService(context_service=ctx)
        pack = await svc.build_slot_context("contract")
        assert pack.slots  # all slots present
        assert all(s.status == "missing" for s in pack.slots)

    @pytest.mark.asyncio
    async def test_budget_truncates_without_error(self):
        big = "x" * 20000
        mapping = {
            "parti, denominazione, ragione sociale, sede legale, codice fiscale": _pack([
                ContextChunk(chunk_id="c1", content=big, source_doc_id="s1", relevance_score=1.0),
            ]),
            "oggetto del contratto, prestazioni, scopo, ambito": _pack([
                ContextChunk(chunk_id="c2", content=big, source_doc_id="s1", relevance_score=1.0),
            ]),
        }
        ctx = _ctx_returning(mapping)
        svc = SlotRetrievalService(context_service=ctx)
        pack = await svc.build_slot_context("contract")
        assert pack.total_tokens <= SlotRetrievalService.MAX_TOKENS


class TestSlotRetrievalError:
    @pytest.mark.asyncio
    async def test_search_error_for_one_slot_isolated(self):
        ctx = AsyncMock()
        calls = {"n": 0}

        async def _build(**kwargs):
            calls["n"] += 1
            if calls["n"] == 1:
                raise RuntimeError("search down")
            return ContextPack()

        ctx.build_section_context = AsyncMock(side_effect=_build)
        svc = SlotRetrievalService(context_service=ctx)
        pack = await svc.build_slot_context("contract")
        # first slot degraded to missing, others still processed
        assert pack.slots[0].status == "missing"
        assert len(pack.slots) > 1

    def test_slotfill_defaults(self):
        f = SlotFill(slot_id="x", label="X", status="missing")
        assert f.chunks == []
        assert f.confidence_bucket == "low"
        assert f.best_confidence == 0.0
