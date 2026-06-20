from unittest.mock import AsyncMock

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

    # --- validate_document_full tests ---

    @pytest.mark.asyncio
    async def test_full_validation_perfect_document(self):
        doc = {
            "id": "doc_1",
            "version": 1,
            "content": {
                "sections": [
                    {"section_id": "sec_1", "title": "Intro", "content": "text"},
                ]
            },
        }
        result = await self.service.validate_document_full(doc)
        assert result["passed"] is True
        assert result["score"] == 100
        assert result["issues"] == []
        assert result["issues_grouped"]["error"] == []

    @pytest.mark.asyncio
    async def test_full_validation_missing_sections(self):
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
                {"section_id": "sec_2", "title": "Body"},
                {"section_id": "sec_3", "title": "Conclusion"},
            ]
        }
        result = await self.service.validate_document_full(doc, spec)
        assert result["passed"] is False
        types = [i["type"] for i in result["issues"]]
        assert types.count("missing_section") == 2

    @pytest.mark.asyncio
    async def test_full_validation_clause_numbering_gap(self):
        doc = {
            "id": "doc_1",
            "version": 1,
            "content": {
                "sections": [
                    {
                        "section_id": "sec_1",
                        "title": "Terms",
                        "content": "text",
                        "clauses": [
                            {"clause_id": "cl_1", "number": "1", "content": "First"},
                            {"clause_id": "cl_2", "number": "3", "content": "Third"},
                            {"clause_id": "cl_3", "number": "4", "content": "Fourth"},
                        ],
                    },
                ]
            },
        }
        result = await self.service.validate_document_full(doc)
        assert result["passed"] is False
        types = [i["type"] for i in result["issues"]]
        assert "clause_numbering_gap" in types
        assert result["score"] == 85

    @pytest.mark.asyncio
    async def test_full_validation_sequential_clauses_pass(self):
        doc = {
            "id": "doc_1",
            "version": 1,
            "content": {
                "sections": [
                    {
                        "section_id": "sec_1",
                        "title": "Terms",
                        "content": "text",
                        "clauses": [
                            {"clause_id": "cl_1", "number": "1", "content": "First"},
                            {"clause_id": "cl_2", "number": "2", "content": "Second"},
                            {"clause_id": "cl_3", "number": "3", "content": "Third"},
                        ],
                    },
                ]
            },
        }
        result = await self.service.validate_document_full(doc)
        assert result["passed"] is True
        assert result["score"] == 100

    @pytest.mark.asyncio
    async def test_full_validation_broken_cross_reference(self):
        doc = {
            "id": "doc_1",
            "version": 1,
            "content": {
                "sections": [
                    {
                        "section_id": "sec_1",
                        "number": "1",
                        "title": "Definitions",
                        "content": "As defined in Section 3",
                    },
                    {
                        "section_id": "sec_2",
                        "number": "2",
                        "title": "Terms",
                        "content": "See Section 1 for definitions",
                    },
                ]
            },
        }
        result = await self.service.validate_document_full(doc)
        assert result["passed"] is False
        types = [i["type"] for i in result["issues"]]
        assert "broken_cross_reference" in types

    @pytest.mark.asyncio
    async def test_full_validation_valid_cross_reference(self):
        doc = {
            "id": "doc_1",
            "version": 1,
            "content": {
                "sections": [
                    {
                        "section_id": "sec_1",
                        "number": "1",
                        "title": "Definitions",
                        "content": "Key terms defined here.",
                    },
                    {
                        "section_id": "sec_2",
                        "number": "2",
                        "title": "Terms",
                        "content": "As defined in Section 1",
                    },
                ]
            },
        }
        result = await self.service.validate_document_full(doc)
        assert result["passed"] is True
        assert result["score"] == 100

    @pytest.mark.asyncio
    async def test_full_validation_empty_section_with_spec(self):
        doc = {
            "id": "doc_1",
            "version": 1,
            "content": {
                "sections": [
                    {"section_id": "sec_1", "title": "Intro", "content": ""},
                ]
            },
        }
        spec = {
            "sections": [
                {"section_id": "sec_1", "title": "Intro"},
                {"section_id": "sec_2", "title": "Body"},
            ]
        }
        result = await self.service.validate_document_full(doc, spec)
        assert result["passed"] is False
        types = [i["type"] for i in result["issues"]]
        assert "empty_section" in types
        assert "missing_section" in types

    @pytest.mark.asyncio
    async def test_full_validation_issues_grouped_by_severity(self):
        doc = {
            "id": "doc_1",
            "version": 1,
            "content": {
                "sections": [
                    {
                        "section_id": "sec_1",
                        "title": "Terms",
                        "content": "",
                        "clauses": [
                            {"clause_id": "cl_1", "number": "1", "content": "First"},
                            {"clause_id": "cl_2", "number": "3", "content": "Third"},
                        ],
                    },
                ]
            },
        }
        result = await self.service.validate_document_full(doc)
        assert "issues_grouped" in result
        assert "error" in result["issues_grouped"]
        assert "warning" in result["issues_grouped"]
        assert len(result["issues_grouped"]["error"]) >= 1
        assert len(result["issues_grouped"]["warning"]) >= 1

    @pytest.mark.asyncio
    async def test_full_validation_title_mismatch_with_spec(self):
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
                {"section_id": "sec_1", "title": "Introduction"},
            ]
        }
        result = await self.service.validate_document_full(doc, spec)
        types = [i["type"] for i in result["issues"]]
        assert "title_mismatch" in types
        warnings = result["issues_grouped"]["warning"]
        assert any(i["type"] == "title_mismatch" for i in warnings)

    # --- validate_with_llm tests ---

    @pytest.mark.asyncio
    async def test_validate_with_llm_returns_issues(self):
        doc = {
            "id": "doc_1",
            "version": 1,
            "content": {
                "sections": [
                    {
                        "section_id": "sec_1",
                        "title": "Test",
                        "content": "Some ambiguous language here",
                    },
                ]
            },
        }
        mock_provider = AsyncMock()
        mock_provider.generate_structured.return_value = {
            "issues": [
                {"section_id": "sec_1", "message": "Ambiguous term 'reasonable' not defined"},
                {"section_id": "sec_1", "message": "Incomplete clause"},
            ]
        }
        issues = await self.service.validate_with_llm(doc, mock_provider)
        assert len(issues) == 2
        assert issues[0]["type"] == "llm_semantic_issue"
        assert issues[0]["severity"] == "warning"
        assert "reasonable" in issues[0]["message"]

    @pytest.mark.asyncio
    async def test_validate_with_llm_empty_document(self):
        doc = {"id": "doc_1", "version": 1, "content": {}}
        mock_provider = AsyncMock()
        mock_provider.generate_structured.return_value = {"issues": []}
        issues = await self.service.validate_with_llm(doc, mock_provider)
        assert issues == []

    @pytest.mark.asyncio
    async def test_validate_with_llm_failure_returns_empty(self):
        doc = {
            "id": "doc_1",
            "version": 1,
            "content": {
                "sections": [
                    {"section_id": "sec_1", "title": "Test", "content": "Text"},
                ]
            },
        }
        mock_provider = AsyncMock()
        mock_provider.generate_structured.side_effect = RuntimeError("LLM down")
        issues = await self.service.validate_with_llm(doc, mock_provider)
        assert issues == []

    @pytest.mark.asyncio
    async def test_validate_with_llm_includes_clause_context(self):
        doc = {
            "id": "doc_1",
            "version": 1,
            "content": {
                "sections": [
                    {
                        "section_id": "sec_1",
                        "title": "Terms",
                        "content": "Section content",
                        "clauses": [
                            {"clause_id": "cl_1", "number": "1", "content": "Clause text"},
                        ],
                    },
                ]
            },
        }
        mock_provider = AsyncMock()
        mock_provider.generate_structured.return_value = {
            "issues": [
                {"section_id": "sec_1", "message": "Missing definition"},
            ]
        }
        issues = await self.service.validate_with_llm(doc, mock_provider)
        assert len(issues) == 1
        # Verify provider was called with prompt containing content
        call_args = mock_provider.generate_structured.call_args
        assert call_args is not None
        prompt = call_args[0][0]
        assert "Terms" in prompt
        assert "Clause" in prompt

    @pytest.mark.asyncio
    async def test_validate_with_llm_handles_non_dict_items(self):
        doc = {
            "id": "doc_1",
            "version": 1,
            "content": {
                "sections": [
                    {"section_id": "sec_1", "title": "Test", "content": "text"},
                ]
            },
        }
        mock_provider = AsyncMock()
        mock_provider.generate_structured.return_value = {
            "issues": ["not a dict", None]
        }
        issues = await self.service.validate_with_llm(doc, mock_provider)
        assert issues == []


class TestProseMirrorSchema:
    """Regression: validation must read real ProseMirror docs (content.content), not only flat schema."""

    def setup_method(self):
        from core.services.validation import _get_sections
        self._get_sections = _get_sections

    def test_parses_prosemirror_section_nodes(self):
        doc = {"content": {"type": "doc", "content": [
            {"type": "section", "attrs": {"sectionId": "sec_1", "title": "Intro"},
             "content": [{"type": "paragraph", "content": [{"type": "text", "text": "Hello body"}]}]},
        ]}}
        sections = self._get_sections(doc)
        assert len(sections) == 1
        assert sections[0]["section_id"] == "sec_1"
        assert sections[0]["title"] == "Intro"
        assert "Hello body" in sections[0]["content"]

    @pytest.mark.asyncio
    async def test_empty_prosemirror_section_flagged(self):
        from core.services.validation import ValidationService
        doc = {"id": "d1", "content": {"type": "doc", "content": [
            {"type": "section", "attrs": {"sectionId": "sec_1", "title": "Vuota"}, "content": []},
        ]}}
        result = await ValidationService().validate_document(doc)
        assert any(i["type"] == "empty_section" for i in result["issues"])
        assert result["passed"] is False
