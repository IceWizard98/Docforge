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
