import pytest

from core.services.validation import ValidationService


class TestValidationService:
    def setup_method(self):
        self.service = ValidationService()

    @pytest.mark.asyncio
    async def test_perfect_document_scores_100(self):
        doc = {
            "id": "doc_1",
            "version": 1,
            "content": {
                "sections": [
                    {"section_id": "sec_1", "title": "Intro", "content": "Some content"},
                ]
            },
        }
        result = await self.service.validate_document(doc)
        assert result["score"] == 100
        assert result["passed"] is True
        assert result["issues"] == []

    @pytest.mark.asyncio
    async def test_empty_section_reduces_score(self):
        doc = {
            "id": "doc_1",
            "version": 1,
            "content": {
                "sections": [
                    {"section_id": "sec_1", "title": "Intro", "content": ""},
                ]
            },
        }
        result = await self.service.validate_document(doc)
        assert result["score"] == 90
        assert result["passed"] is False
        assert len(result["issues"]) == 1
        assert result["issues"][0]["type"] == "empty_section"

    @pytest.mark.asyncio
    async def test_missing_section_from_spec(self):
        doc = {
            "id": "doc_1",
            "version": 1,
            "content": {
                "sections": [
                    {"section_id": "sec_1", "title": "Intro", "content": "text"},
                ]
            },
        }
        spec = {
            "sections": [
                {"section_id": "sec_1", "title": "Intro"},
                {"section_id": "sec_2", "title": "Missing"},
            ]
        }
        result = await self.service.validate_document(doc, spec)
        assert result["passed"] is False
        types = [i["type"] for i in result["issues"]]
        assert "missing_section" in types

    @pytest.mark.asyncio
    async def test_mixed_issues_score(self):
        doc = {
            "id": "doc_1",
            "version": 1,
            "content": {
                "sections": [
                    {"section_id": "sec_1", "title": "Intro", "content": ""},
                    {"section_id": "sec_2", "title": "Body", "content": "content"},
                ]
            },
        }
        spec = {
            "sections": [
                {"section_id": "sec_1", "title": "Intro"},
                {"section_id": "sec_2", "title": "Body"},
                {"section_id": "sec_3", "title": "Missing"},
            ]
        }
        result = await self.service.validate_document(doc, spec)
        assert result["score"] < 100
        assert result["passed"] is False
        types = [i["type"] for i in result["issues"]]
        assert "missing_section" in types
        assert "empty_section" in types

    @pytest.mark.asyncio
    async def test_empty_document(self):
        doc = {"id": "doc_1", "version": 1, "content": {}}
        result = await self.service.validate_document(doc)
        assert result["score"] == 100
        assert result["passed"] is True

    @pytest.mark.asyncio
    async def test_document_with_whitespace_only_section(self):
        doc = {
            "id": "doc_1",
            "version": 1,
            "content": {
                "sections": [
                    {"section_id": "sec_1", "title": "Spaces", "content": "   "},
                ]
            },
        }
        result = await self.service.validate_document(doc)
        assert result["passed"] is False
        assert result["issues"][0]["type"] == "empty_section"

    @pytest.mark.asyncio
    async def test_all_penalty_types(self):
        doc = {
            "id": "doc_1",
            "version": 1,
            "content": {
                "sections": [
                    {"section_id": "sec_1", "title": "Intro", "content": "text"},
                ]
            },
        }
        spec = {
            "sections": [
                {"section_id": "sec_1", "title": "Wrong Title"},
                {"section_id": "sec_2", "title": "Missing"},
            ]
        }
        result = await self.service.validate_document(doc, spec)
        assert result["score"] == 70
        assert result["passed"] is False

    @pytest.mark.asyncio
    async def test_validate_section_empty_content(self):
        section = {"section_id": "sec_1", "title": "Title", "content": ""}
        spec_section = {"section_id": "sec_1", "title": "Title"}
        issues = await self.service.validate_section(section, spec_section)
        assert len(issues) == 1
        assert issues[0]["type"] == "empty_section"

    @pytest.mark.asyncio
    async def test_validate_section_title_mismatch(self):
        section = {"section_id": "sec_1", "title": "Actual", "content": "text"}
        spec_section = {"section_id": "sec_1", "title": "Expected"}
        issues = await self.service.validate_section(section, spec_section)
        types = [i["type"] for i in issues]
        assert "title_mismatch" in types

    @pytest.mark.asyncio
    async def test_validate_section_clean(self):
        section = {"section_id": "sec_1", "title": "Title", "content": "text"}
        spec_section = {"section_id": "sec_1", "title": "Title"}
        issues = await self.service.validate_section(section, spec_section)
        assert issues == []

    @pytest.mark.asyncio
    async def test_validate_section_no_spec_title_skips_mismatch_check(self):
        section = {"section_id": "sec_1", "title": "Any", "content": "text"}
        spec_section = {"section_id": "sec_1", "title": ""}
        issues = await self.service.validate_section(section, spec_section)
        assert issues == []
