from unittest.mock import AsyncMock

import pytest

from core.services.drafting import ContextPack, DraftService


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

    @pytest.mark.asyncio
    async def test_generate_section_returns_dict(self):
        spec = {"title": "Test"}
        section = {"section_id": "sec_1", "title": "Premesse"}
        context = ContextPack(chunks=[{"document_id": "doc_1", "text": "some text"}])
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
        assert len(pack.chunks) == 1
        assert pack.chunks[0]["id"] == "chk_1"

    @pytest.mark.asyncio
    async def test_compose_context_pack_empty(self):
        pack = await self.service.compose_context_pack("doc_1", "sec_1", [])
        assert len(pack.chunks) == 0

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
        context = ContextPack(chunks=[{"document_id": "doc_1", "text": "legal text"}])
        result = await self.service.generate_section(spec, section, context)
        assert result["content"] == "This is the section content"
        assert len(result["provenance"]) > 0

    @pytest.mark.asyncio
    async def test_generate_section_llm_failure_falls_back(self):
        mock_llm = AsyncMock()
        mock_llm.generate_structured.side_effect = RuntimeError("API error")
        spec = {"title": "Test"}
        section = {"section_id": "sec_1", "title": "Premesse"}
        context = ContextPack(chunks=[{"document_id": "doc_1", "text": "legal text"}])
        result = await self.service.generate_section(spec, section, context, mock_llm)
        assert result["content"] == ""
        assert result["status"] == "draft"
