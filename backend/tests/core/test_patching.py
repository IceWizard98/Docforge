from unittest.mock import AsyncMock

import pytest

from core.services.patching import PatchService


class TestPatchService:
    def setup_method(self):
        self.service = PatchService()

    @pytest.mark.asyncio
    async def test_generate_patch_plan_without_llm(self):
        doc = {"id": "doc_1", "title": "Test", "version": 3, "content": {"sections": []}}
        result = await self.service.generate_patch_plan(doc, "Add a new section")
        assert result["id"].startswith("ps_")
        assert result["document_id"] == "doc_1"
        assert result["version_from"] == 3
        assert result["version_to"] == 4
        assert result["operations"] == []

    @pytest.mark.asyncio
    async def test_generate_patch_plan_with_llm(self):
        doc = {"id": "doc_1", "title": "Test", "version": 2, "content": {"sections": []}}
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
        doc = {"id": "doc_1", "title": "Test", "version": 1, "content": {"sections": []}}
        mock_llm = AsyncMock()
        mock_llm.generate_structured.side_effect = RuntimeError("API down")
        result = await self.service.generate_patch_plan(doc, "fix", mock_llm)
        assert result["operations"] == []

    @pytest.mark.asyncio
    async def test_validate_patch_target_not_found(self):
        doc = {"content": {"sections": [{"section_id": "sec_1"}]}}
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
        doc = {"content": {"sections": [{"section_id": "sec_1"}, {"section_id": "sec_2"}]}}
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
        doc = {"content": {"sections": []}}
        patch_set = {"operations": []}
        issues = await self.service.validate_patch(patch_set, doc)
        assert issues == []

    @pytest.mark.asyncio
    async def test_apply_patch_insert(self):
        doc = {"id": "doc_1", "version": 1, "content": {"sections": []}}
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
        assert len(result["content"]["sections"]) == 1
        assert result["content"]["sections"][0]["section_id"] == "sec_new"
        assert result["_patched"] is True
        assert result["_operations_applied"] == 1

    @pytest.mark.asyncio
    async def test_apply_patch_replace(self):
        doc = {
            "version": 1,
            "content": {
                "sections": [
                    {"section_id": "sec_1", "title": "Old", "content": "old text"}
                ]
            },
        }
        patch_set = {
            "version_to": 2,
            "operations": [
                {
                    "status": "accepted",
                    "operation": "replace",
                    "target_section": "sec_1",
                    "content": {"title": "New", "content": "new text"},
                }
            ],
        }
        result = await self.service.apply_patch(patch_set, doc)
        section = result["content"]["sections"][0]
        assert section["title"] == "New"
        assert section["content"] == "new text"

    @pytest.mark.asyncio
    async def test_apply_patch_replace_with_path(self):
        doc = {
            "version": 1,
            "content": {
                "sections": [
                    {"section_id": "sec_1", "title": "Old", "nested": {"key": "val"}},
                ]
            },
        }
        patch_set = {
            "version_to": 2,
            "operations": [
                {
                    "status": "accepted",
                    "operation": "replace",
                    "target_section": "sec_1",
                    "target_path": ["nested", "key"],
                    "content": "new_val",
                }
            ],
        }
        result = await self.service.apply_patch(patch_set, doc)
        assert result["content"]["sections"][0]["nested"]["key"] == "new_val"

    @pytest.mark.asyncio
    async def test_apply_patch_delete(self):
        doc = {
            "version": 1,
            "content": {
                "sections": [
                    {"section_id": "sec_1", "title": "Delete Me"},
                    {"section_id": "sec_2", "title": "Keep Me"},
                ]
            },
        }
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
        assert len(result["content"]["sections"]) == 1
        assert result["content"]["sections"][0]["section_id"] == "sec_2"

    @pytest.mark.asyncio
    async def test_apply_patch_only_accepted(self):
        doc = {"version": 1, "content": {"sections": []}}
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
        assert len(result["content"]["sections"]) == 1
        assert result["_operations_applied"] == 1
