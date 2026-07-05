import uuid
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from api.routes.chat import (
    _build_message_sources,
    _document_outline,
    _format_grounding_block,
    _format_transparency,
    _section_title,
    _write_citations,
)
from core.services.context import ContextChunk
from core.services.drafting import build_section_paragraph as _section_paragraph
from core.services.slot_retrieval import SlotContextPack, SlotFill


class TestFormatGroundingBlock:
    def test_frames_sources_as_style_reference_not_to_describe(self):
        block = _format_grounding_block("CHUNK_TEXT")
        low = block.lower()
        # The source text is still fenced as untrusted data and embedded.
        assert "CHUNK_TEXT" in block
        # New framing: style-only reference, no copying, no describing, user data wins.
        assert "stile" in low
        assert "non copiar" in low
        assert "non descriver" in low
        assert "autoritativ" in low
        # Old describe-the-source framing must be gone.
        assert "fondare la risposta" not in low
        assert "non inventare informazioni assenti dalle fonti" not in low


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


# --- Step 1: build SourceRef list from collected chunks ----------------------

class TestGenerateChatReply:
    @pytest.mark.asyncio
    async def test_normalizes_non_dict_action_and_defaults_reply(self):
        # A weak local model under format:json may emit action as a STRING; if not
        # normalized, downstream action_data.get("type") raises AttributeError -> 500.
        from api.routes.chat import _generate_chat_reply

        provider = SimpleNamespace(
            generate_structured=AsyncMock(return_value={"action": "draft"})
        )
        out = await _generate_chat_reply(provider, "sys", "user")
        assert out["action"] is None
        assert isinstance(out["reply"], str) and out["reply"].strip()  # no blank bubble

    @pytest.mark.asyncio
    async def test_valid_dict_action_passes_through(self):
        from api.routes.chat import _generate_chat_reply

        provider = SimpleNamespace(
            generate_structured=AsyncMock(
                return_value={"reply": "ok", "action": {"type": "draft", "params": {}}}
            )
        )
        out = await _generate_chat_reply(provider, "sys", "user")
        assert out["action"]["type"] == "draft"
        assert out["reply"] == "ok"

    @pytest.mark.asyncio
    async def test_prose_response_used_as_reply_when_not_json(self):
        # Local models often answer in plain prose, not JSON. extract_json then
        # raises; instead of discarding the model's real answer behind a generic
        # error, fall back to the prose as the visible reply.
        from adapters.llm.utils import StructuredOutputError
        from api.routes.chat import _generate_chat_reply
        provider = SimpleNamespace(
            generate_structured=AsyncMock(
                side_effect=StructuredOutputError("Could not extract valid JSON from LLM response")
            ),
            generate=AsyncMock(return_value="Certo, ecco la mia risposta in prosa."),
        )
        out = await _generate_chat_reply(provider, "sys", "user")
        assert out["reply"] == "Certo, ecco la mia risposta in prosa."
        assert out["action"] is None
        # Must NOT be the generic "non ho capito" fallback.
        assert "non sono sicuro" not in out["reply"].lower()


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
        assert refs[0]["doc_id"] == str(sid1)
        assert refs[0]["title"] == "nda_acme.pdf"
        assert refs[0]["chunk_id"] == "c1"
        assert refs[0]["confidence"] == pytest.approx(0.9)
        assert "alpha" in refs[0]["snippet"]

    @pytest.mark.asyncio
    async def test_refs_validate_against_response_schema(self):
        # The stored message.sources JSON is validated against SourceCitationResponse
        # when ChatMessageResponse is built; mismatched keys (e.g. camelCase) raise a
        # 500. This guards the contract whenever retrieval actually returns sources.
        from api.schemas.chat import SourceCitationResponse

        sid = uuid.uuid4()
        chunks = [ContextChunk(chunk_id="c1", content="alpha", source_doc_id=str(sid), relevance_score=0.8)]
        result = MagicMock()
        result.scalars.return_value.all.return_value = []
        session = AsyncMock()
        session.execute = AsyncMock(return_value=result)

        refs = await _build_message_sources(session, chunks)
        for r in refs:
            SourceCitationResponse.model_validate(r)  # must not raise

    @pytest.mark.asyncio
    async def test_dedups_by_source_file(self):
        # Multiple chunks from the SAME source must collapse to ONE pill (the
        # highest-confidence one), not N identical pills.
        sid = uuid.uuid4()
        chunks = [
            ContextChunk(chunk_id="c1", content="a", source_doc_id=str(sid), relevance_score=0.4),
            ContextChunk(chunk_id="c2", content="b", source_doc_id=str(sid), relevance_score=0.9),
            ContextChunk(chunk_id="c3", content="c", source_doc_id=str(sid), relevance_score=0.6),
        ]
        src = SimpleNamespace(id=sid, filename="contract.pdf")
        result = MagicMock()
        result.scalars.return_value.all.return_value = [src]
        session = AsyncMock()
        session.execute = AsyncMock(return_value=result)

        refs = await _build_message_sources(session, chunks)
        assert len(refs) == 1
        assert refs[0]["confidence"] == pytest.approx(0.9)

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


# --- Task: section paragraph with per-span marks -----------------------------

class TestSectionParagraph:
    def test_plain_content_no_marks(self):
        node = _section_paragraph({"content": "Testo semplice"})
        assert node["type"] == "paragraph"
        assert node["content"][0]["text"] == "Testo semplice"
        assert "marks" not in node["content"][0]

    def test_empty_content_yields_empty_paragraph(self):
        node = _section_paragraph({"content": ""})
        assert node["content"] == []

    def test_runs_apply_provenance_mark(self):
        sec = {"content": "x", "runs": [
            {"text": "Le parti.", "provenance": {"source_doc_id": "d1", "chunk_id": "c1", "confidence": 0.9}, "placeholder": None},
        ]}
        node = _section_paragraph(sec)
        text = node["content"][0]
        assert text["text"] == "Le parti."
        assert text["marks"][0]["type"] == "provenance"
        assert text["marks"][0]["attrs"]["sourceDocId"] == "d1"
        assert text["marks"][0]["attrs"]["chunkId"] == "c1"

    def test_runs_apply_placeholder_mark(self):
        sec = {"runs": [
            {"text": "[foro]", "provenance": None, "placeholder": {"slot_id": "law", "reason": "manca"}},
        ]}
        node = _section_paragraph(sec)
        text = node["content"][0]
        assert text["marks"][0]["type"] == "placeholderMark"
        assert text["marks"][0]["attrs"]["slotId"] == "law"

    def test_runs_skip_empty_text(self):
        sec = {"runs": [{"text": "", "provenance": None, "placeholder": None}]}
        node = _section_paragraph(sec)
        assert node["content"] == []


class TestExcludedSourceIds:
    @pytest.mark.asyncio
    async def test_returns_empty_when_no_document(self):
        from api.routes.chat import _excluded_source_ids

        session = AsyncMock()
        session.execute = AsyncMock()
        assert await _excluded_source_ids(session, None) == []
        session.execute.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_returns_string_ids_for_document(self):
        from api.routes.chat import _excluded_source_ids

        sid1, sid2 = uuid.uuid4(), uuid.uuid4()
        result = MagicMock()
        result.scalars.return_value.all.return_value = [sid1, sid2]
        session = AsyncMock()
        session.execute = AsyncMock(return_value=result)

        out = await _excluded_source_ids(session, uuid.uuid4())
        assert out == [str(sid1), str(sid2)]

    @pytest.mark.asyncio
    async def test_exclusions_land_on_retrieval_filters(self):
        # The retrieval helper must carry exclusions (and owner_id) into the
        # RetrievalFilters it hands to the context service.
        import api.routes.chat as chat_mod

        captured = {}

        class _FakePack:
            sources = []

        class _FakeContextSvc:
            def __init__(self, *a, **k):
                pass

            async def build_section_context(self, section_title, filters=None):
                captured["filters"] = filters
                return _FakePack()

        session = AsyncMock()
        with (
            patch.object(chat_mod, "PgvectorAdapter", lambda s: MagicMock()),
            patch.object(chat_mod, "ContextPackService", _FakeContextSvc),
        ):
            await chat_mod._retrieve_source_context(
                session, "query", owner_id="owner-1",
                excluded_source_ids=["ex-1", "ex-2"],
            )
        assert captured["filters"].owner_id == "owner-1"
        assert captured["filters"].excluded_source_ids == ["ex-1", "ex-2"]
