"""Two-phase drafting — extraction phase (style/structure notes from the corpus).

extract_notes distils reference notes from retrieved chunks WITHOUT ever letting
the corpus block drafting: an empty/unusable pack, a refusal or an LLM error all
return "" (the caller then drafts brief-only). It also must never leak the raw
source entities — the prompt carries an explicit no-copy rule.
"""

from unittest.mock import AsyncMock

import pytest

from core.services.context import ContextChunk, ContextPack, ContextSource
from core.services.extraction import ExtractionService


def _pack(texts: list[str]) -> ContextPack:
    chunks = [ContextChunk(chunk_id=f"c{i}", content=t) for i, t in enumerate(texts)]
    if not chunks:
        return ContextPack()
    return ContextPack(sources=[ContextSource(doc_id="d1", chunks=chunks)])


class TestExtractNotes:
    @pytest.mark.asyncio
    async def test_prompt_contains_chunk_brief_and_title(self):
        # Echo the prompt back as the reply to assert what the model receives.
        llm = AsyncMock()
        llm.generate.side_effect = lambda prompt, *a, **k: prompt
        pack = _pack(["CLAUSOLA DI RISERVATEZZA tipica del settore"])
        out = await ExtractionService().extract_notes(
            section_title="Riservatezza",
            brief="Contratto tra Luis e Athenor Srl",
            context_pack=pack,
            llm=llm,
        )
        assert "CLAUSOLA DI RISERVATEZZA tipica del settore" in out
        assert "Contratto tra Luis e Athenor Srl" in out
        assert "Riservatezza" in out

    @pytest.mark.asyncio
    async def test_prompt_forbids_copying_source_entities(self):
        llm = AsyncMock()
        llm.generate.side_effect = lambda prompt, *a, **k: prompt
        out = await ExtractionService().extract_notes(
            section_title="Parti", brief="b", context_pack=_pack(["x"]), llm=llm
        )
        assert "NON riportare nomi" in out

    @pytest.mark.asyncio
    async def test_empty_pack_returns_empty_no_llm_call(self):
        llm = AsyncMock()
        out = await ExtractionService().extract_notes(
            section_title="T", brief="b", context_pack=ContextPack(), llm=llm
        )
        assert out == ""
        llm.generate.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_no_llm_returns_empty(self):
        out = await ExtractionService().extract_notes(
            section_title="T", brief="b", context_pack=_pack(["x"]), llm=None
        )
        assert out == ""

    @pytest.mark.asyncio
    async def test_refusal_returns_empty(self):
        llm = AsyncMock()
        llm.generate.return_value = "Non posso accedere ai file sorgente forniti."
        out = await ExtractionService().extract_notes(
            section_title="T", brief="b", context_pack=_pack(["x"]), llm=llm
        )
        assert out == ""

    @pytest.mark.asyncio
    async def test_llm_exception_returns_empty(self):
        llm = AsyncMock()
        llm.generate.side_effect = RuntimeError("boom")
        out = await ExtractionService().extract_notes(
            section_title="T", brief="b", context_pack=_pack(["x"]), llm=llm
        )
        assert out == ""

    @pytest.mark.asyncio
    async def test_output_truncated(self):
        llm = AsyncMock()
        llm.generate.return_value = "- " + "a" * 5000
        out = await ExtractionService().extract_notes(
            section_title="T", brief="b", context_pack=_pack(["x"]), llm=llm
        )
        assert len(out) <= 1200

    @pytest.mark.asyncio
    async def test_chunks_capped(self):
        # The material block is capped so a huge corpus chunk can't blow the prompt.
        llm = AsyncMock()
        llm.generate.side_effect = lambda prompt, *a, **k: prompt
        out = await ExtractionService().extract_notes(
            section_title="T", brief="b", context_pack=_pack(["Z" * 10000]), llm=llm
        )
        assert "Z" * 4000 not in out
