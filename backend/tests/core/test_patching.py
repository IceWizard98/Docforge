from unittest.mock import AsyncMock

import pytest

from core.services.patching import PatchService


def _ps_sections(*section_ids: str) -> list[dict]:
    """Build ProseMirror section nodes."""
    return [
        {"type": "section", "attrs": {"sectionId": sid, "number": str(i + 1), "status": "draft"}, "content": []}
        for i, sid in enumerate(section_ids)
    ]


def _ps_doc(sections: list[dict] | None = None) -> dict:
    """Build a ProseMirror document dict."""
    return {"content": {"type": "doc", "content": sections or []}}


class TestPatchService:
    def setup_method(self):
        self.service = PatchService()

    @pytest.mark.asyncio
    async def test_generate_patch_plan_without_llm(self):
        doc = {"id": "doc_1", "title": "Test", "version": 3, "content": {"type": "doc", "content": []}}
        result = await self.service.generate_patch_plan(doc, "Add a new section")
        assert result["id"].startswith("ps_")
        assert result["document_id"] == "doc_1"
        assert result["version_from"] == 3
        assert result["version_to"] == 4
        assert result["operations"] == []

    @pytest.mark.asyncio
    async def test_generate_patch_plan_with_llm(self):
        doc = {"id": "doc_1", "title": "Test", "version": 2, "content": {"type": "doc", "content": []}}
        mock_llm = AsyncMock()
        mock_llm.generate_structured.return_value = {
            "summary": "Add intro section",
            "operations": [{"operation": "insert", "target_section": "sec_new"}],
        }
        self.service._llm = mock_llm
        result = await self.service.generate_patch_plan(doc, "Add intro")
        assert result["summary"] == "Add intro section"
        assert len(result["operations"]) == 1
        assert result["version_to"] == 3

    @pytest.mark.asyncio
    async def test_generate_patch_plan_llm_failure_falls_back(self):
        doc = {"id": "doc_1", "title": "Test", "version": 1, "content": {"type": "doc", "content": []}}
        mock_llm = AsyncMock()
        mock_llm.generate_structured.side_effect = RuntimeError("API down")
        result = await self.service.generate_patch_plan(doc, "fix", mock_llm)
        assert result["operations"] == []

    @pytest.mark.asyncio
    async def test_validate_patch_target_not_found(self):
        doc = _ps_doc(_ps_sections("sec_1"))
        patch_set = {
            "operations": [
                {"id": "op_1", "target_section": "sec_missing"}
            ]
        }
        issues = await self.service.validate_patch(patch_set, doc)
        assert len(issues) == 1
        assert issues[0]["type"] == "target_not_found"

    @pytest.mark.asyncio
    async def test_validate_patch_all_found(self):
        doc = _ps_doc(_ps_sections("sec_1", "sec_2"))
        patch_set = {
            "operations": [
                {"id": "op_1", "target_section": "sec_1"},
                {"id": "op_2", "target_section": "sec_2"},
            ]
        }
        issues = await self.service.validate_patch(patch_set, doc)
        assert issues == []

    @pytest.mark.asyncio
    async def test_validate_patch_empty_operations(self):
        doc = _ps_doc()
        patch_set = {"operations": []}
        issues = await self.service.validate_patch(patch_set, doc)
        assert issues == []

    @pytest.mark.asyncio
    async def test_apply_patch_insert(self):
        doc = {"id": "doc_1", "version": 1, "content": {"type": "doc", "content": []}}
        patch_set = {
            "version_to": 2,
            "operations": [
                {
                    "status": "accepted",
                    "operation": "insert",
                    "target_section": "sec_new",
                    "content": {"title": "New Section", "content": "Hello"},
                }
            ],
        }
        result = await self.service.apply_patch(patch_set, doc)
        assert result["version"] == 2
        sections = result["content"]["content"]
        assert len(sections) == 1
        assert sections[0]["attrs"]["sectionId"] == "sec_new"
        assert result["_patched"] is True
        assert result["_operations_applied"] == 1

    @pytest.mark.asyncio
    async def test_apply_patch_replace(self):
        doc = {"version": 1, "content": {"type": "doc", "content": _ps_sections("sec_1")}}
        patch_set = {
            "version_to": 2,
            "operations": [
                {
                    "status": "accepted",
                    "operation": "replace",
                    "target_section": "sec_1",
                    "content": {"content": [{"type": "paragraph", "content": [{"type": "text", "text": "new text"}]}]},
                }
            ],
        }
        result = await self.service.apply_patch(patch_set, doc)
        section = result["content"]["content"][0]
        assert section["content"][0]["content"][0]["text"] == "new text"

    @pytest.mark.asyncio
    async def test_apply_patch_delete(self):
        doc = {"version": 1, "content": {"type": "doc", "content": _ps_sections("sec_1", "sec_2")}}
        patch_set = {
            "version_to": 2,
            "operations": [
                {
                    "status": "accepted",
                    "operation": "delete",
                    "target_section": "sec_1",
                }
            ],
        }
        result = await self.service.apply_patch(patch_set, doc)
        sections = result["content"]["content"]
        assert len(sections) == 1
        assert sections[0]["attrs"]["sectionId"] == "sec_2"

    @pytest.mark.asyncio
    async def test_apply_patch_only_accepted(self):
        doc = {"version": 1, "content": {"type": "doc", "content": []}}
        patch_set = {
            "version_to": 2,
            "operations": [
                {"status": "accepted", "operation": "insert",
                 "target_section": "s1", "content": {}},
                {"status": "rejected", "operation": "insert",
                 "target_section": "s2", "content": {}},
            ],
        }
        result = await self.service.apply_patch(patch_set, doc)
        assert len(result["content"]["content"]) == 1
        assert result["_operations_applied"] == 1

    @pytest.mark.asyncio
    async def test_apply_patch_preserves_non_section_nodes(self):
        leading = {"type": "paragraph", "content": [{"type": "text", "text": "intro"}]}
        doc = {
            "version": 1,
            "content": {"type": "doc", "content": [leading, *_ps_sections("sec_1")]},
        }
        patch_set = {
            "version_to": 2,
            "operations": [
                {
                    "status": "accepted",
                    "operation": "replace",
                    "target_section": "sec_1",
                    "content": {"content": [{"type": "paragraph", "content": [{"type": "text", "text": "new"}]}]},
                }
            ],
        }
        result = await self.service.apply_patch(patch_set, doc)
        children = result["content"]["content"]
        assert children[0]["type"] == "paragraph"
        assert children[0]["content"][0]["text"] == "intro"
        section = next(n for n in children if n.get("type") == "section")
        assert section["content"][0]["content"][0]["text"] == "new"

    @pytest.mark.asyncio
    async def test_apply_patch_delete_preserves_non_section_nodes(self):
        leading = {"type": "paragraph", "content": [{"type": "text", "text": "intro"}]}
        doc = {
            "version": 1,
            "content": {"type": "doc", "content": [leading, *_ps_sections("sec_1", "sec_2")]},
        }
        patch_set = {
            "version_to": 2,
            "operations": [
                {"status": "accepted", "operation": "delete", "target_section": "sec_1"},
            ],
        }
        result = await self.service.apply_patch(patch_set, doc)
        children = result["content"]["content"]
        assert children[0]["type"] == "paragraph"
        section_ids = [n["attrs"]["sectionId"] for n in children if n.get("type") == "section"]
        assert section_ids == ["sec_2"]

    @pytest.mark.asyncio
    async def test_apply_patch_replace_with_path(self):
        sections = _ps_sections("sec_1")
        sections[0]["attrs"]["title"] = "old"
        doc = {"version": 1, "content": {"type": "doc", "content": sections}}
        patch_set = {
            "version_to": 2,
            "operations": [
                {
                    "status": "accepted",
                    "operation": "replace",
                    "target_section": "sec_1",
                    "target_path": ["attrs", "title"],
                    "content": "new title",
                }
            ],
        }
        result = await self.service.apply_patch(patch_set, doc)
        section = result["content"]["content"][0]
        assert section["attrs"]["title"] == "new title"
