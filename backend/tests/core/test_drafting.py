from unittest.mock import AsyncMock

import pytest

from core.services.context import ContextChunk, ContextPack, ContextPackService, ContextSource
from core.services.drafting import (
    DraftService,
    _looks_like_refusal,
    _normalize_sections,
    assemble_draft_content,
    build_section_node,
    build_section_paragraph,
    spec_sections_with_provenance,
)


class TestNormalizeSections:
    def test_coerces_strings_dicts_and_drops_junk(self):
        out = _normalize_sections([
            "Premesse",
            {"title": "Oggetto", "section_id": "s1"},
            {"title": "   "},   # empty title -> dropped
            42,                  # junk -> dropped
            {"foo": "bar"},     # no title -> dropped
        ])
        assert [s["title"] for s in out] == ["Premesse", "Oggetto"]
        assert all(s["section_id"] for s in out)
        assert out[1]["section_id"] == "s1"

    def test_non_list_returns_empty(self):
        assert _normalize_sections(None) == []
        assert _normalize_sections("nope") == []
        assert _normalize_sections({}) == []


class TestRefusalDetection:
    def test_detects_italian_and_english_refusals(self):
        assert _looks_like_refusal(
            "Non posso accedere al contenuto dei file sorgente forniti"
        )
        assert _looks_like_refusal("I cannot generate that content")
        assert _looks_like_refusal("Mi dispiace, non sono in grado di farlo")

    def test_real_prose_is_not_a_refusal(self):
        assert not _looks_like_refusal(
            "Il presente contratto disciplina la consulenza tra le parti."
        )


class TestDraftAssembly:
    def test_build_section_paragraph_plain(self):
        node = build_section_paragraph({"content": "Ciao"})
        assert node["type"] == "paragraph"
        assert node["content"][0]["text"] == "Ciao"
        assert "marks" not in node["content"][0]

    def test_build_section_paragraph_runs_marks(self):
        node = build_section_paragraph({"runs": [
            {"text": "A",
             "provenance": {"source_doc_id": "d1", "chunk_id": "c1"}, "placeholder": None},
            {"text": "B", "provenance": None, "placeholder": {"slot_id": "s", "reason": "r"}},
        ]})
        assert node["content"][0]["marks"][0]["type"] == "provenance"
        assert node["content"][1]["marks"][0]["type"] == "placeholderMark"

    def test_build_section_node_attrs(self):
        node = build_section_node({"section_id": "sec_x", "title": "T", "content": "c"}, 0)
        assert node["type"] == "section"
        assert node["attrs"]["sectionId"] == "sec_x"
        assert node["attrs"]["number"] == 1

    def test_build_section_node_status_default(self):
        node = build_section_node({"section_id": "sec_x", "title": "T", "content": "c"}, 0)
        assert node["attrs"]["status"] == "draft"

    def test_build_section_node_status_override(self):
        node = build_section_node({"section_id": "s", "status": "final"}, 0)
        assert node["attrs"]["status"] == "final"

    def test_assemble_draft_content(self):
        doc = assemble_draft_content([
            {"section_id": "s1", "title": "A", "content": "x"},
            {"section_id": "s2", "title": "B", "content": "y"},
        ])
        assert doc["type"] == "doc"
        assert len(doc["content"]) == 2
        assert doc["content"][1]["attrs"]["sectionId"] == "s2"

    def test_spec_sections_with_provenance(self):
        out = spec_sections_with_provenance([
            {"section_id": "s1", "title": "A", "provenance": [{"chunk_id": "c1"}]},
        ])
        assert out[0]["section_id"] == "s1"
        assert out[0]["provenance"][0]["chunk_id"] == "c1"


class TestDraftService:
    def setup_method(self):
        self.service = DraftService()

    @pytest.mark.asyncio
    async def test_generate_spec_returns_dict(self):
        messages = [{"role": "user", "content": "Create a contract"}]
        spec = await self.service.generate_spec("chat_123", messages)
        assert "draft_id" in spec
        assert "chat_session_id" in spec
        assert spec["chat_session_id"] == "chat_123"

    @pytest.mark.asyncio
    async def test_generate_spec_with_empty_messages(self):
        spec = await self.service.generate_spec("chat_456", [])
        # niente brief -> titolo italiano di default, non slug tecnici
        assert spec["title"] == "Nuova bozza"

    @pytest.mark.asyncio
    async def test_generate_spec_fallback_title_from_brief(self):
        messages = [{"role": "user", "content": "Analisi funzionale per il progetto Zeta di Athenor"}]
        spec = await self.service.generate_spec("chat_789", messages)
        # fallback (nessun LLM): il titolo deriva dal brief, leggibile dall'utente
        assert spec["title"].startswith("Bozza: Analisi funzionale per il progetto Zeta")
        assert "chat_789" not in spec["title"]

    def _make_context(self, chunks_data: list[dict]) -> ContextPack:
        chunks = [
            ContextChunk(
                chunk_id=c.get("id", c.get("chunk_id", "")),
                content=c.get("text", c.get("content", "")),
                source_doc_id=c.get("document_id", c.get("source_doc_id", "doc_1")),
            )
            for c in chunks_data
        ]
        sources = [ContextSource(doc_id="doc_1", chunks=chunks)] if chunks else []
        return ContextPack(sources=sources, total_tokens=len(chunks_data))

    @pytest.mark.asyncio
    async def test_generate_section_returns_dict(self):
        spec = {"title": "Test"}
        section = {"section_id": "sec_1", "title": "Premesse"}
        context = self._make_context([{"document_id": "doc_1", "text": "some text"}])
        result = await self.service.generate_section(spec, section, context)
        assert result["section_id"] == "sec_1"
        assert result["title"] == "Premesse"

    @pytest.mark.asyncio
    async def test_generate_section_with_empty_context(self):
        spec = {"title": "Test"}
        section = {"section_id": "sec_2", "title": "Oggetto"}
        context = ContextPack()
        result = await self.service.generate_section(spec, section, context)
        assert result["section_id"] == "sec_2"
        assert result["status"] == "draft"

    @pytest.mark.asyncio
    async def test_compose_context_pack(self):
        chunks = [{"id": "chk_1", "text": "hello"}]
        pack = await self.service.compose_context_pack("doc_1", "sec_1", chunks)
        assert len(pack.sources) == 1
        assert len(pack.sources[0].chunks) == 1
        assert pack.sources[0].chunks[0].chunk_id == "chk_1"
        assert pack.sources[0].chunks[0].content == "hello"

    @pytest.mark.asyncio
    async def test_compose_context_pack_empty(self):
        pack = await self.service.compose_context_pack("doc_1", "sec_1", [])
        assert len(pack.sources) == 0

    @pytest.mark.asyncio
    async def test_generate_spec_uses_slot_schema_outline_for_known_doc_type(self):
        # A known doc_type must yield a deterministic, Italian, type-correct
        # outline from the slot schema — NOT a weak-model invention (which
        # produced generic English "Main Content" sections).
        spec = await self.service.generate_spec(
            "chat_1", [{"role": "user", "content": "contratto di consulenza"}],
            doc_type="contract",
        )
        titles = [s["title"] for s in spec["sections"]]
        assert "Parti" in titles
        assert "Oggetto" in titles
        # Each section carries the slot retrieval hint for grounded search.
        assert any(s.get("query_hint") for s in spec["sections"])

    @pytest.mark.asyncio
    async def test_generate_spec_other_doc_type_falls_back_to_default(self):
        spec = await self.service.generate_spec("chat_1", [], doc_type="other")
        assert len(spec["sections"]) >= 1
        assert all(s.get("title") for s in spec["sections"])

    @pytest.mark.asyncio
    async def test_generate_section_ungrounded_skips_corpus(self):
        # Brief-driven mode (ground=False): never touch the corpus, so an
        # unrelated source document can't contaminate the section. Content from
        # the brief is a plain run (no placeholder/provenance marks).
        mock_llm = AsyncMock()
        mock_llm.generate.return_value = "Le parti sono Luis e Athenor Srl."
        mock_svc = AsyncMock()
        service = DraftService(llm=mock_llm, context_service=mock_svc)
        spec = {"title": "T", "brief": "Luis e Athenor Srl, 61k, 1 anno"}
        section = {"section_id": "s", "title": "Parti"}
        result = await service.generate_section(
            spec, section, context_pack=None, ground=False
        )
        mock_svc.build_section_context.assert_not_awaited()
        assert result["content"] == "Le parti sono Luis e Athenor Srl."
        assert result["provenance"] == []
        assert result["context_chunk_ids"] == []
        assert result["runs"][0]["placeholder"] is None
        assert result["runs"][0]["provenance"] is None
        assert result["placeholders"] == []

    @pytest.mark.asyncio
    async def test_generate_spec_brief_aggregates_user_messages(self):
        # Terms are often stated across turns; the brief must aggregate ALL user
        # messages, not just the last, or the section model lacks the real data.
        messages = [
            {"role": "user", "content": "Contratto tra Luis e Athenor Srl"},
            {"role": "assistant", "content": "ok"},
            {"role": "user", "content": "61.000 euro, durata un anno"},
        ]
        spec = await self.service.generate_spec("chat_1", messages, doc_type="contract")
        assert "Athenor" in spec["brief"]
        assert "61.000" in spec["brief"]

    @pytest.mark.asyncio
    async def test_generate_section_uses_query_hint_for_retrieval(self):
        mock_llm = AsyncMock()
        mock_llm.generate.return_value = "txt"
        mock_svc = AsyncMock()
        mock_svc.build_section_context.return_value = self._make_context([{"text": "t"}])
        service = DraftService(llm=mock_llm, context_service=mock_svc)
        section = {
            "section_id": "sec_parties", "title": "Parti",
            "query_hint": "parti, ragione sociale, sede legale",
        }
        await service.generate_section({"title": "T"}, section, context_pack=None)
        _, kwargs = mock_svc.build_section_context.call_args
        assert "ragione sociale" in kwargs.get("section_title", "")

    @pytest.mark.asyncio
    async def test_generate_section_prompt_forbids_copying_source_entities(self):
        mock_llm = AsyncMock()
        mock_llm.generate.side_effect = lambda prompt, *a, **k: prompt
        self.service._llm = mock_llm
        context = self._make_context([{"text": "legal"}])
        result = await self.service.generate_section(
            {"title": "T", "brief": "b"}, {"section_id": "s", "title": "Parti"}, context
        )
        assert "SOLO come riferimento di stile" in result["content"]

    @pytest.mark.asyncio
    async def test_generate_spec_with_llm_provider(self):
        mock_llm = AsyncMock()
        mock_llm.generate_structured.return_value = {
            "title": "Contract Draft",
            "sections": [{"section_id": "sec_1", "title": "Intro"}],
        }
        self.service._llm = mock_llm
        messages = [{"role": "user", "content": "Create a contract"}]
        spec = await self.service.generate_spec("chat_789", messages)
        assert spec["title"] == "Contract Draft"
        assert len(spec["sections"]) == 1
        assert spec["sections"][0]["section_id"] == "sec_1"

    @pytest.mark.asyncio
    async def test_generate_spec_llm_failure_falls_back(self):
        mock_llm = AsyncMock()
        mock_llm.generate_structured.side_effect = RuntimeError("API error")
        self.service._llm = mock_llm
        messages = [{"role": "user", "content": "Create a contract"}]
        spec = await self.service.generate_spec("chat_999", messages)
        assert "draft_id" in spec
        assert spec["title"] != ""

    @pytest.mark.asyncio
    async def test_generate_section_with_llm_provider(self):
        # Local models can't reliably emit nested JSON, so the section body is
        # generated as PLAIN TEXT via provider.generate (not generate_structured).
        mock_llm = AsyncMock()
        mock_llm.generate.return_value = "This is the section content"
        self.service._llm = mock_llm
        spec = {"title": "Test"}
        section = {"section_id": "sec_1", "title": "Premesse"}
        context = self._make_context([{"document_id": "doc_1", "text": "legal text"}])
        result = await self.service.generate_section(spec, section, context)
        assert result["content"] == "This is the section content"
        assert len(result["provenance"]) > 0
        mock_llm.generate.assert_awaited_once()
        mock_llm.generate_structured.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_generate_section_plain_text_with_newlines_and_quotes(self):
        # Regression: the model returns prose with literal newlines and quotes
        # (exactly what broke JSON parsing on llama3.1:8b). Plain-text generation
        # must accept it verbatim, never raise, never yield empty content.
        prose = 'Tra "Strategy Srl" e Luis.\n\nIl compenso è 60.000 EUR.\n'
        mock_llm = AsyncMock()
        mock_llm.generate.return_value = prose
        self.service._llm = mock_llm
        spec = {"title": "Contratto"}
        section = {"section_id": "sec_1", "title": "Premesse"}
        context = self._make_context([{"document_id": "doc_1", "text": "legal"}])
        result = await self.service.generate_section(spec, section, context)
        assert result["content"] == prose.strip()
        assert result["content"]
        assert result["runs"]

    @pytest.mark.asyncio
    async def test_generate_section_llm_failure_falls_back(self):
        mock_llm = AsyncMock()
        mock_llm.generate.side_effect = RuntimeError("API error")
        spec = {"title": "Test"}
        section = {"section_id": "sec_1", "title": "Premesse"}
        context = self._make_context([{"document_id": "doc_1", "text": "legal text"}])
        result = await self.service.generate_section(spec, section, context, mock_llm)
        assert result["content"] == ""
        assert result["status"] == "draft"

    @pytest.mark.asyncio
    async def test_generate_section_with_context_service_builds_context(self):
        mock_llm = AsyncMock()
        mock_llm.generate.return_value = "Content from context"
        mock_svc = AsyncMock()
        mock_svc.build_section_context.return_value = self._make_context(
            [{"document_id": "doc_1", "text": "source text"}]
        )
        mock_svc.build_prompt_context.return_value = "source text"
        service = DraftService(llm=mock_llm, context_service=mock_svc)
        spec = {"title": "Test"}
        section = {"section_id": "sec_1", "title": "Premesse"}
        result = await service.generate_section(spec, section, context_pack=None)
        assert result["content"] == "Content from context"
        assert len(result["provenance"]) > 0
        mock_svc.build_section_context.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_generate_section_uses_existing_context_over_service(self):
        mock_llm = AsyncMock()
        mock_llm.generate.return_value = "Existing context used"
        mock_svc = AsyncMock()
        service = DraftService(llm=mock_llm)
        spec = {"title": "Test"}
        section = {"section_id": "sec_1", "title": "Premesse"}
        context = self._make_context([{"document_id": "doc_1", "text": "existing"}])
        result = await service.generate_section(
            spec, section, context_pack=context, context_service=mock_svc
        )
        assert result["content"] == "Existing context used"
        mock_svc.build_section_context.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_generate_section_grounded_content_single_sourced_run(self):
        # With grounding context, plain-text content becomes one sourced run whose
        # provenance is resolved from the retrieved pack (not from the model).
        mock_llm = AsyncMock()
        mock_llm.generate.return_value = "Le parti sono Acme e Beta."
        self.service._llm = mock_llm
        spec = {"title": "Test"}
        section = {"section_id": "sec_1", "title": "Parti"}
        context = self._make_context([{"chunk_id": "chk_1", "text": "Acme, Beta"}])
        result = await self.service.generate_section(spec, section, context)
        assert "runs" in result
        assert result["runs"][0]["provenance"]["chunk_id"] == "chk_1"
        assert result["runs"][0]["placeholder"] is None

    @pytest.mark.asyncio
    async def test_generate_section_unsourced_content_marked_placeholder(self):
        # No context -> the content must be flagged as a placeholder span, never
        # silently accepted as sourced.
        mock_llm = AsyncMock()
        mock_llm.generate.return_value = "Clausola inventata senza fonte."
        self.service._llm = mock_llm
        spec = {"title": "Test"}
        section = {"section_id": "sec_1", "title": "Oggetto"}
        from core.services.context import ContextPack
        result = await self.service.generate_section(spec, section, ContextPack())
        assert result["runs"], "expected a synthesized placeholder run"
        run = result["runs"][0]
        assert run["placeholder"] is not None
        assert run["provenance"] is None
        assert result["placeholders"]

    @pytest.mark.asyncio
    async def test_generate_section_provenance_includes_chunk_id(self):
        mock_llm = AsyncMock()
        mock_llm.generate.return_value = "Provenance test"
        self.service._llm = mock_llm
        spec = {"title": "Test"}
        section = {"section_id": "sec_1", "title": "Premesse"}
        context = self._make_context([{"chunk_id": "chk_abc", "text": "source"}])
        result = await self.service.generate_section(spec, section, context)
        assert result["provenance"][0]["chunk_id"] == "chk_abc"
        assert result["provenance"][0]["source"] == "doc_1"

    def test_format_context_pack_exposes_ids(self):
        # The worker prompt must surface source_doc_id + chunk_id so the LLM can
        # cite them; a title-only context leaves provenance unresolvable.
        pack = self._make_context([{"chunk_id": "chk_1", "document_id": "d1", "text": "hello"}])
        out = self.service._format_context_pack(pack)
        assert "source_doc_id=d1" in out
        assert "chunk_id=chk_1" in out

    @pytest.mark.asyncio
    async def test_generate_section_provenance_falls_back_to_pack_source(self):
        # Provenance is resolved purely from the retrieved pack (the model no
        # longer emits it), so it must carry a real source_doc_id/chunk_id so the
        # promote-time NOT NULL FK can be satisfied.
        mock_llm = AsyncMock()
        mock_llm.generate.return_value = "Clausola."
        self.service._llm = mock_llm
        spec = {"title": "T"}
        section = {"section_id": "sec_1", "title": "Parti"}
        context = self._make_context(
            [{"document_id": "doc_real", "chunk_id": "chk_z", "text": "t"}]
        )
        result = await self.service.generate_section(spec, section, context)
        assert result["provenance"][0]["source_doc_id"] == "doc_real"
        assert result["provenance"][0]["chunk_id"] == "chk_z"

    @pytest.mark.asyncio
    async def test_generate_section_context_prompt_includes_italian_prefix(self):
        # The plain-text prompt must surface the source context so the model can
        # ground its prose; echo it back as the generated body to assert it.
        mock_llm = AsyncMock()
        mock_llm.generate.side_effect = lambda prompt, *a, **k: prompt
        self.service._llm = mock_llm
        spec = {"title": "Test"}
        section = {"section_id": "sec_1", "title": "Premesse"}
        context = self._make_context([{"text": "legal"}])
        result = await self.service.generate_section(spec, section, context)
        assert "Ecco il contesto dai documenti sorgente" in result["content"]

    @pytest.mark.asyncio
    async def test_generate_section_no_context_fallback(self):
        mock_llm = AsyncMock()
        mock_llm.generate.side_effect = RuntimeError("fail")
        spec = {"title": "Test"}
        section = {"section_id": "sec_1", "title": "Premesse"}
        result = await self.service.generate_section(
            spec, section, context_pack=None, llm=mock_llm
        )
        assert result["section_id"] == "sec_1"
        assert result["content"] == ""

    @pytest.mark.asyncio
    async def test_generate_section_passes_session_history_to_context_service(self):
        # Sequential pipeline: chunks already consumed by earlier sections are
        # passed via session_history so build_section_context can dedup them and
        # later sections don't re-pull (and re-emit) the same source text.
        mock_llm = AsyncMock()
        mock_llm.generate.return_value = "txt"
        mock_svc = AsyncMock()
        mock_svc.build_section_context.return_value = self._make_context([{"text": "t"}])
        service = DraftService(llm=mock_llm, context_service=mock_svc)
        spec = {"title": "T"}
        section = {"section_id": "sec_1", "title": "Premesse"}
        hist = [{"context_chunks": ["chk_old"]}]
        await service.generate_section(
            spec, section, context_pack=None, session_history=hist
        )
        _, kwargs = mock_svc.build_section_context.call_args
        assert kwargs.get("session_history") == hist

    @pytest.mark.asyncio
    async def test_generate_section_injects_previous_sections_and_antiverbatim(self):
        # The prompt must (a) list already-written sections so the model doesn't
        # repeat them and (b) instruct synthesis instead of verbatim copying.
        mock_llm = AsyncMock()
        mock_llm.generate.side_effect = lambda prompt, *a, **k: prompt
        self.service._llm = mock_llm
        spec = {"title": "Contratto"}
        section = {"section_id": "sec_2", "title": "Oggetto"}
        context = self._make_context([{"text": "legal"}])
        prev = [{"title": "Premesse", "content": "Le parti sono A e B."}]
        result = await self.service.generate_section(
            spec, section, context, previous_sections=prev
        )
        assert "Premesse" in result["content"]
        assert "RIFORMULA" in result["content"]

    @pytest.mark.asyncio
    async def test_generate_section_retries_on_refusal(self):
        # Weak local models sometimes refuse ("Non posso accedere ai file…")
        # instead of writing. A refusal must trigger ONE retry; the usable retry
        # text replaces it so no refusal sentence reaches the document.
        mock_llm = AsyncMock()
        mock_llm.generate.side_effect = [
            "Non posso accedere al contenuto dei file sorgente forniti.",
            "Il presente contratto disciplina la consulenza tra le parti.",
        ]
        self.service._llm = mock_llm
        spec = {"title": "Contratto", "brief": "x"}
        section = {"section_id": "s0", "title": "Introduction"}
        context = self._make_context([{"text": "t"}])
        result = await self.service.generate_section(spec, section, context)
        assert "Il presente contratto" in result["content"]
        assert not _looks_like_refusal(result["content"])
        assert mock_llm.generate.await_count == 2

    @pytest.mark.asyncio
    async def test_generate_section_double_refusal_yields_placeholder(self):
        # If even the retry refuses, emit an explicit [DA COMPLETARE] placeholder
        # rather than leaking a refusal sentence into the document.
        mock_llm = AsyncMock()
        mock_llm.generate.side_effect = [
            "Non posso accedere ai file sorgente.",
            "Mi dispiace, non sono in grado di farlo.",
        ]
        self.service._llm = mock_llm
        spec = {"title": "Contratto", "brief": "x"}
        section = {"section_id": "s0", "title": "Introduction"}
        context = self._make_context([{"text": "t"}])
        result = await self.service.generate_section(spec, section, context)
        assert not _looks_like_refusal(result["content"])
        assert "DA COMPLETARE" in result["content"]
        assert mock_llm.generate.await_count == 2

    @pytest.mark.asyncio
    async def test_generate_section_prompt_forbids_refusal(self):
        mock_llm = AsyncMock()
        mock_llm.generate.side_effect = lambda prompt, *a, **k: prompt
        self.service._llm = mock_llm
        spec = {"title": "T", "brief": "b"}
        section = {"section_id": "s0", "title": "Premesse"}
        context = self._make_context([{"text": "legal"}])
        result = await self.service.generate_section(spec, section, context)
        assert "NON rifiutare" in result["content"]

    @pytest.mark.asyncio
    async def test_generate_section_notes_in_prompt_with_label(self):
        # Two-phase mode: the extracted notes go into the context slot under an
        # explicit APPUNTI label; the raw corpus chunk text must NOT appear.
        mock_llm = AsyncMock()
        mock_llm.generate.side_effect = lambda prompt, *a, **k: prompt
        self.service._llm = mock_llm
        notes_pack = self._make_context(
            [{"chunk_id": "chk_1", "document_id": "doc_1", "text": "RAW SOURCE TEXT"}]
        )
        result = await self.service.generate_section(
            {"title": "T", "brief": "b"},
            {"section_id": "s", "title": "Parti"},
            context_pack=None,
            ground=False,
            notes="- usa formule standard\n- struttura in commi numerati",
            notes_pack=notes_pack,
        )
        assert "APPUNTI ESTRATTI DALLE FONTI" in result["content"]
        assert "usa formule standard" in result["content"]
        assert "RAW SOURCE TEXT" not in result["content"]

    @pytest.mark.asyncio
    async def test_generate_section_notes_provenance_and_chunk_ids_from_pack(self):
        # Provenance + consumed chunk ids come from notes_pack, so promote-time
        # ProvenanceLink rows and cross-section dedup keep working in two-phase mode.
        mock_llm = AsyncMock()
        mock_llm.generate.return_value = "Le parti sono X e Y."
        self.service._llm = mock_llm
        notes_pack = self._make_context(
            [{"chunk_id": "chk_9", "document_id": "doc_z", "text": "t"}]
        )
        result = await self.service.generate_section(
            {"title": "T", "brief": "b"},
            {"section_id": "s", "title": "Parti"},
            context_pack=None,
            ground=False,
            notes="- appunti di stile",
            notes_pack=notes_pack,
        )
        assert result["context_chunk_ids"] == ["chk_9"]
        assert result["provenance"][0]["chunk_id"] == "chk_9"
        assert result["provenance"][0]["source_doc_id"] == "doc_z"
        assert result["runs"][0]["provenance"]["chunk_id"] == "chk_9"

    @pytest.mark.asyncio
    async def test_generate_section_empty_notes_identical_to_brief_only(self):
        # Anti-contamination regression guard: notes="" must yield a result byte-
        # identical to the current brief-only (ground=False) behavior.
        mock_llm = AsyncMock()
        mock_llm.generate.side_effect = lambda prompt, *a, **k: prompt
        self.service._llm = mock_llm
        spec = {"title": "Contratto", "brief": "Luis e Athenor Srl, 61k, 1 anno"}
        section = {"section_id": "s", "title": "Parti"}
        baseline = await self.service.generate_section(
            spec, section, context_pack=None, ground=False
        )
        with_empty = await self.service.generate_section(
            spec, section, context_pack=None, ground=False, notes="", notes_pack=None
        )
        assert with_empty == baseline

    @pytest.mark.asyncio
    async def test_generate_section_returns_context_chunk_ids(self):
        # The worker accumulates these into session_history for the next section.
        mock_llm = AsyncMock()
        mock_llm.generate.return_value = "txt"
        self.service._llm = mock_llm
        spec = {"title": "T"}
        section = {"section_id": "sec_1", "title": "Premesse"}
        context = self._make_context(
            [{"chunk_id": "chk_1", "text": "a"}, {"chunk_id": "chk_2", "text": "b"}]
        )
        result = await self.service.generate_section(spec, section, context)
        assert result["context_chunk_ids"] == ["chk_1", "chk_2"]


class TestContextPackService:
    @pytest.mark.asyncio
    async def test_build_section_context_no_search_returns_empty(self):
        svc = ContextPackService()
        pack = await svc.build_section_context(
            document_id="doc_1",
            section_title="Test",
            section_id="sec_1",
        )
        assert len(pack.sources) == 0

    @pytest.mark.asyncio
    async def test_build_section_context_empty_query(self):
        mock_pgvector = AsyncMock()
        svc = ContextPackService(pgvector=mock_pgvector)
        pack = await svc.build_section_context(
            document_id="doc_1", section_title="", section_id=""
        )
        assert len(pack.sources) == 0
        mock_pgvector.fulltext_search.assert_not_called()
