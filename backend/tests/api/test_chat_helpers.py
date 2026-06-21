import uuid
from datetime import datetime
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest

from api.routes.chat import (
    _build_message_sources,
    _corpus_catalog,
    _doc_type_filter,
    _document_outline,
    _format_transparency,
    _section_title,
    _write_citations,
)
from core.services.context import ContextChunk
from core.services.search import RetrievalFilters
from core.services.slot_retrieval import SlotContextPack, SlotFill


def _section(sid: str, title: str | None = None, status: str = "draft", heading: str | None = None):
    content = []
    if heading:
        content.append({"type": "heading", "content": [{"type": "text", "text": heading}]})
    attrs = {"sectionId": sid, "status": status}
    if title:
        attrs["title"] = title
    return {"type": "section", "attrs": attrs, "content": content}


def test_document_outline_lists_sections_with_ids():
    content = {"type": "doc", "content": [
        _section("sec_1", title="Introduzione", status="approved"),
        _section("sec_2", heading="Obblighi delle parti"),
    ]}
    outline = _document_outline(content)
    assert "[sec_1]" in outline
    assert "Introduzione" in outline
    assert "approved" in outline
    assert "[sec_2]" in outline
    assert "Obblighi delle parti" in outline  # title from heading fallback


def test_document_outline_empty_for_no_sections():
    assert _document_outline({"type": "doc", "content": []}) == ""
    assert _document_outline(None) == ""


def test_section_title_prefers_attrs_then_heading():
    assert _section_title(_section("s", title="T", heading="H")) == "T"
    assert _section_title(_section("s", heading="H")) == "H"
    assert _section_title(_section("s")) == "(senza titolo)"


@pytest.mark.asyncio
async def test_corpus_catalog_formats_sources():
    src = SimpleNamespace(
        filename="nda_acme.pdf", doc_type="contract", language="it",
        tags=["nda", "acme"], created_at=datetime(2026, 1, 15),
    )
    result = MagicMock()
    result.scalars.return_value.all.return_value = [src]
    session = AsyncMock()
    session.execute = AsyncMock(return_value=result)

    catalog = await _corpus_catalog(session)
    assert "nda_acme.pdf" in catalog
    assert "contract" in catalog
    assert "nda, acme" in catalog
    assert "2026-01-15" in catalog


@pytest.mark.asyncio
async def test_corpus_catalog_empty_when_no_sources():
    result = MagicMock()
    result.scalars.return_value.all.return_value = []
    session = AsyncMock()
    session.execute = AsyncMock(return_value=result)
    assert await _corpus_catalog(session) == ""


# --- Step 1: doc_type retrieval filter ---------------------------------------

class TestDocTypeFilter:
    def test_canonical_type_builds_filter(self):
        doc = SimpleNamespace(doc_type="contract")
        f = _doc_type_filter(doc)
        assert isinstance(f, RetrievalFilters)
        assert f.doc_type == ["contract"]

    def test_alias_normalized(self):
        f = _doc_type_filter(SimpleNamespace(doc_type="Contratto"))
        assert f.doc_type == ["contract"]

    def test_other_yields_no_filter(self):
        # Free-form/unknown types normalize to "other" -> search unfiltered.
        assert _doc_type_filter(SimpleNamespace(doc_type="report")) is None

    def test_empty_yields_no_filter(self):
        assert _doc_type_filter(SimpleNamespace(doc_type="")) is None
        assert _doc_type_filter(SimpleNamespace(doc_type=None)) is None

    def test_none_doc_yields_no_filter(self):
        assert _doc_type_filter(None) is None


# --- Step 1: build SourceRef list from collected chunks ----------------------

class TestBuildMessageSources:
    @pytest.mark.asyncio
    async def test_builds_refs_with_titles(self):
        sid1 = uuid.uuid4()
        chunks = [
            ContextChunk(chunk_id="c1", content="alpha text", source_doc_id=str(sid1), relevance_score=0.9),
        ]
        src = SimpleNamespace(id=sid1, filename="nda_acme.pdf")
        result = MagicMock()
        result.scalars.return_value.all.return_value = [src]
        session = AsyncMock()
        session.execute = AsyncMock(return_value=result)

        refs = await _build_message_sources(session, chunks)
        assert len(refs) == 1
        assert refs[0]["sourceDocId"] == str(sid1)
        assert refs[0]["title"] == "nda_acme.pdf"
        assert refs[0]["chunkId"] == "c1"
        assert refs[0]["confidence"] == pytest.approx(0.9)
        assert "alpha" in refs[0]["snippet"]

    @pytest.mark.asyncio
    async def test_dedups_by_chunk_id(self):
        sid = uuid.uuid4()
        chunks = [
            ContextChunk(chunk_id="c1", content="a", source_doc_id=str(sid), relevance_score=0.9),
            ContextChunk(chunk_id="c1", content="a", source_doc_id=str(sid), relevance_score=0.5),
        ]
        src = SimpleNamespace(id=sid, filename="f.pdf")
        result = MagicMock()
        result.scalars.return_value.all.return_value = [src]
        session = AsyncMock()
        session.execute = AsyncMock(return_value=result)

        refs = await _build_message_sources(session, chunks)
        assert len(refs) == 1

    @pytest.mark.asyncio
    async def test_empty_chunks_no_query(self):
        session = AsyncMock()
        session.execute = AsyncMock()
        refs = await _build_message_sources(session, [])
        assert refs == []
        session.execute.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_missing_title_falls_back_to_id(self):
        sid = uuid.uuid4()
        chunks = [ContextChunk(chunk_id="c1", content="a", source_doc_id=str(sid), relevance_score=0.3)]
        result = MagicMock()
        result.scalars.return_value.all.return_value = []  # no source row found
        session = AsyncMock()
        session.execute = AsyncMock(return_value=result)
        refs = await _build_message_sources(session, chunks)
        assert refs[0]["title"] == str(sid)


# --- Step 2: persist citations ------------------------------------------------

class TestWriteCitations:
    @pytest.mark.asyncio
    async def test_writes_one_per_unique_chunk(self):
        sid = uuid.uuid4()
        msg_id = uuid.uuid4()
        chunks = [
            ContextChunk(chunk_id="c1", content="a", source_doc_id=str(sid), relevance_score=0.9),
            ContextChunk(chunk_id="c2", content="b", source_doc_id=str(sid), relevance_score=0.8),
            ContextChunk(chunk_id="c1", content="a", source_doc_id=str(sid), relevance_score=0.7),
        ]
        session = MagicMock()
        session.begin_nested = MagicMock(return_value=AsyncMock())
        session.add = MagicMock()

        await _write_citations(session, msg_id, chunks)
        assert session.add.call_count == 2  # c1, c2 (deduped)

    @pytest.mark.asyncio
    async def test_no_chunks_no_writes(self):
        session = MagicMock()
        session.begin_nested = MagicMock(return_value=AsyncMock())
        session.add = MagicMock()
        await _write_citations(session, uuid.uuid4(), [])
        session.add.assert_not_called()

    @pytest.mark.asyncio
    async def test_invalid_source_doc_id_skipped_gracefully(self):
        chunks = [ContextChunk(chunk_id="c1", content="a", source_doc_id="not-a-uuid", relevance_score=0.5)]
        session = MagicMock()
        session.begin_nested = MagicMock(return_value=AsyncMock())
        session.add = MagicMock()
        # Should not raise; citation written with source_doc_id=None.
        await _write_citations(session, uuid.uuid4(), chunks)
        assert session.add.call_count == 1


# --- Step 6: transparency formatting ------------------------------------------

class TestFormatTransparency:
    def _pack(self):
        return SlotContextPack(doc_type="contract", slots=[
            SlotFill(slot_id="parties", label="Parti", status="filled"),
            SlotFill(slot_id="object", label="Oggetto", status="missing"),
            SlotFill(slot_id="governing_law", label="Legge", status="ambiguous"),
        ])

    def test_summary_mentions_label_and_sources(self):
        summary, slot_status = _format_transparency(
            "Contratto", self._pack(), ["nda_acme.pdf", "profilo.pdf"]
        )
        assert "Contratto" in summary
        assert "nda_acme.pdf" in summary

    def test_summary_without_sources(self):
        summary, _ = _format_transparency("Contratto", self._pack(), [])
        assert "Contratto" in summary
        assert "nessuna fonte" in summary.lower()

    def test_slot_status_shape(self):
        _, slot_status = _format_transparency("Contratto", self._pack(), [])
        by_id = {s["slot_id"]: s for s in slot_status}
        assert by_id["parties"]["status"] == "filled"
        assert by_id["object"]["status"] == "missing"
        assert by_id["governing_law"]["status"] == "ambiguous"
        assert by_id["parties"]["label"] == "Parti"

    def test_empty_pack_yields_empty_status(self):
        summary, slot_status = _format_transparency(
            "Contratto", SlotContextPack(doc_type="contract", slots=[]), []
        )
        assert slot_status == []
