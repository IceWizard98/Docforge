from unittest.mock import AsyncMock

import pytest

from core.services.context import ContextChunk, ContextPack, ContextPackService, ContextSource
from core.services.drafting import (
    DraftService,
    assemble_draft_content,
    build_section_node,
    build_section_paragraph,
    spec_sections_with_provenance,
)


class TestDraftAssembly:
    def test_build_section_paragraph_plain(self):
        node = build_section_paragraph({"content": "Ciao"})
        assert node["type"] == "paragraph"
        assert node["content"][0]["text"] == "Ciao"
        assert "marks" not in node["content"][0]

    def test_build_section_paragraph_runs_marks(self):
        node = build_section_paragraph({"runs": [
            {"text": "A", "provenance": {"source_doc_id": "d1", "chunk_id": "c1"}, "placeholder": None},
            {"text": "B", "provenance": None, "placeholder": {"slot_id": "s", "reason": "r"}},
        ]})
        assert node["content"][0]["marks"][0]["type"] == "provenance"
        assert node["content"][1]["marks"][0]["type"] == "placeholderMark"

    def test_build_section_node_attrs(self):
        node = build_section_node({"section_id": "sec_x", "title": "T", "content": "c"}, 0)
        assert node["type"] == "section"
        assert node["attrs"]["sectionId"] == "sec_x"
        assert node["attrs"]["number"] == 1

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
        assert spec["title"] == "Draft from chat chat_456"

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
        mock_llm = AsyncMock()
        mock_llm.generate_structured.return_value = {
            "content": "This is the section content",
            "provenance": [{"source": "doc_1", "confidence": 0.95}],
        }
        self.service._llm = mock_llm
        spec = {"title": "Test"}
        section = {"section_id": "sec_1", "title": "Premesse"}
        context = self._make_context([{"document_id": "doc_1", "text": "legal text"}])
        result = await self.service.generate_section(spec, section, context)
        assert result["content"] == "This is the section content"
        assert len(result["provenance"]) > 0

    @pytest.mark.asyncio
    async def test_generate_section_llm_failure_falls_back(self):
        mock_llm = AsyncMock()
        mock_llm.generate_structured.side_effect = RuntimeError("API error")
        spec = {"title": "Test"}
        section = {"section_id": "sec_1", "title": "Premesse"}
        context = self._make_context([{"document_id": "doc_1", "text": "legal text"}])
        result = await self.service.generate_section(spec, section, context, mock_llm)
        assert result["content"] == ""
        assert result["status"] == "draft"

    @pytest.mark.asyncio
    async def test_generate_section_with_context_service_builds_context(self):
        mock_llm = AsyncMock()
        mock_llm.generate_structured.return_value = {
            "content": "Content from context",
            "provenance": [{"source": "doc_1", "confidence": 0.9}],
        }
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
        mock_llm.generate_structured.return_value = {
            "content": "Existing context used",
            "provenance": [],
        }
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
    async def test_generate_section_maps_runs(self):
        mock_llm = AsyncMock()
        mock_llm.generate_structured.return_value = {
            "content": "Le parti sono Acme e Beta.",
            "provenance": [{"source": "doc_1", "confidence": 0.9}],
            "runs": [
                {"text": "Le parti sono Acme e Beta.",
                 "provenance": {"source": "doc_1", "chunk_id": "chk_1", "confidence": 0.9},
                 "placeholder": None},
            ],
        }
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
        # No provenance and no runs -> the content must be flagged as a placeholder
        # span, never silently accepted as sourced.
        mock_llm = AsyncMock()
        mock_llm.generate_structured.return_value = {
            "content": "Clausola inventata senza fonte.",
            "provenance": [],
        }
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
        mock_llm.generate_structured.return_value = {
            "content": "Provenance test",
            "provenance": [{"source": "doc_1", "confidence": 0.95}],
        }
        self.service._llm = mock_llm
        spec = {"title": "Test"}
        section = {"section_id": "sec_1", "title": "Premesse"}
        context = self._make_context([{"chunk_id": "chk_abc", "text": "source"}])
        result = await self.service.generate_section(spec, section, context)
        assert result["provenance"][0]["chunk_id"] == "chk_abc"
        assert result["provenance"][0]["source"] == "doc_1"

    @pytest.mark.asyncio
    async def test_generate_section_context_prompt_includes_italian_prefix(self):
        mock_llm = AsyncMock()
        mock_llm.generate_structured.side_effect = (
            lambda prompt, _: {"content": prompt, "provenance": []}
        )
        self.service._llm = mock_llm
        spec = {"title": "Test"}
        section = {"section_id": "sec_1", "title": "Premesse"}
        context = self._make_context([{"text": "legal"}])
        result = await self.service.generate_section(spec, section, context)
        assert "Ecco il contesto dai documenti sorgente" in result["content"]

    @pytest.mark.asyncio
    async def test_generate_section_no_context_fallback(self):
        mock_llm = AsyncMock()
        mock_llm.generate_structured.side_effect = RuntimeError("fail")
        spec = {"title": "Test"}
        section = {"section_id": "sec_1", "title": "Premesse"}
        result = await self.service.generate_section(
            spec, section, context_pack=None, llm=mock_llm
        )
        assert result["section_id"] == "sec_1"
        assert result["content"] == ""


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
