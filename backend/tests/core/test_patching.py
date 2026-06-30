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
    async def test_apply_patch_skips_already_applied(self):
        # An op flagged applied=True must not be re-applied (idempotency: accept
        # already applied it incrementally).
        doc = {"version": 1, "content": {"type": "doc", "content": []}}
        patch_set = {
            "version_to": 2,
            "operations": [
                {"status": "accepted", "operation": "insert", "target_section": "s1",
                 "content": {}, "applied": True},
                {"status": "accepted", "operation": "insert", "target_section": "s2",
                 "content": {}},
            ],
        }
        result = await self.service.apply_patch(patch_set, doc)
        # Only the not-yet-applied op (s2) is applied.
        assert len(result["content"]["content"]) == 1
        assert result["content"]["content"][0]["attrs"]["sectionId"] == "s2"

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

    @pytest.mark.asyncio
    async def test_apply_operation_insert(self):
        doc = {"version": 3, "content": {"type": "doc", "content": []}}
        op = {
            "operation": "insert",
            "target_section": "sec_new",
            "content": {"title": "New", "content": "Hello"},
        }
        result = await self.service.apply_operation(op, doc)
        assert result["version"] == 4
        sections = result["content"]["content"]
        assert len(sections) == 1
        assert sections[0]["attrs"]["sectionId"] == "sec_new"

    @pytest.mark.asyncio
    async def test_apply_operation_replace(self):
        doc = {"version": 1, "content": {"type": "doc", "content": _ps_sections("sec_1")}}
        op = {
            "operation": "replace",
            "target_section": "sec_1",
            "content": {"content": [{"type": "paragraph", "content": [{"type": "text", "text": "x"}]}]},
        }
        result = await self.service.apply_operation(op, doc)
        section = result["content"]["content"][0]
        assert section["content"][0]["content"][0]["text"] == "x"

    @pytest.mark.asyncio
    async def test_apply_operation_delete(self):
        doc = {"version": 1, "content": {"type": "doc", "content": _ps_sections("sec_1", "sec_2")}}
        op = {"operation": "delete", "target_section": "sec_1"}
        result = await self.service.apply_operation(op, doc)
        sections = result["content"]["content"]
        assert len(sections) == 1
        assert sections[0]["attrs"]["sectionId"] == "sec_2"

    @pytest.mark.asyncio
    async def test_apply_operation_applies_only_the_given_op(self):
        # A single accepted op among several must not pull in the other ops.
        doc = {"version": 1, "content": {"type": "doc", "content": []}}
        op = {"operation": "insert", "target_section": "s1", "content": {"content": "only"}}
        result = await self.service.apply_operation(op, doc)
        assert len(result["content"]["content"]) == 1
        assert result["content"]["content"][0]["attrs"]["sectionId"] == "s1"

    @pytest.mark.asyncio
    async def test_apply_operation_replace_bare_list_content(self):
        # Weak models often emit content as a bare node array, not {"content": [...]}.
        doc = {"version": 1, "content": {"type": "doc", "content": _ps_sections("sec_1")}}
        op = {
            "operation": "replace",
            "target_section": "sec_1",
            "content": [{"type": "paragraph", "content": [{"type": "text", "text": "bare"}]}],
        }
        result = await self.service.apply_operation(op, doc)
        assert result["_changed"] is True
        assert result["content"]["content"][0]["content"][0]["content"][0]["text"] == "bare"

    @pytest.mark.asyncio
    async def test_apply_operation_replace_string_content(self):
        # Or even a plain string — wrap it in a paragraph instead of no-op'ing.
        doc = {"version": 1, "content": {"type": "doc", "content": _ps_sections("sec_1")}}
        op = {"operation": "replace", "target_section": "sec_1", "content": "solo testo"}
        result = await self.service.apply_operation(op, doc)
        assert result["_changed"] is True
        assert result["content"]["content"][0]["content"][0]["content"][0]["text"] == "solo testo"

    @pytest.mark.asyncio
    async def test_apply_operation_replace_int_path_falls_back_to_body(self):
        # target_path with an int index is meaningless for prose. The old code wrote
        # section[0] = content (a junk key, no visible change) — the "applied but
        # nothing changed" bug. Now it must fall back to a real body replacement.
        doc = {"version": 1, "content": {"type": "doc", "content": _ps_sections("sec_1")}}
        op = {"operation": "replace", "target_section": "sec_1", "target_path": [0], "content": "nuovo testo"}
        result = await self.service.apply_operation(op, doc)
        assert result["_changed"] is True
        sec = result["content"]["content"][0]
        assert sec["content"][0]["content"][0]["text"] == "nuovo testo"
        assert 0 not in sec  # no junk integer key written into the node

    @pytest.mark.asyncio
    async def test_generate_patch_plan_prompt_includes_section_body(self):
        # The model must SEE the current section text to rewrite it; otherwise it
        # invents field-style patches that don't touch the visible prose.
        from unittest.mock import AsyncMock
        mock_llm = AsyncMock()
        mock_llm.generate_structured = AsyncMock(return_value={"summary": "s", "operations": []})
        doc = {"content": {"type": "doc", "content": [
            {"type": "section", "attrs": {"sectionId": "sec_1", "title": "Durata"},
             "content": [{"type": "paragraph", "content": [{"type": "text", "text": "dodici mesi"}]}]},
        ]}}
        await PatchService().generate_patch_plan(doc, "cambia in 18 mesi", mock_llm)
        prompt = mock_llm.generate_structured.call_args[0][0]
        assert "dodici mesi" in prompt   # current body text is shown
        assert "sec_1" in prompt          # exact id to target

    @pytest.mark.asyncio
    async def test_apply_operation_replace_rejects_invalid_node_list(self):
        # A list that isn't valid ProseMirror nodes must NOT be written (would break
        # the editor); treat as a no-op so accept reports nothing changed.
        doc = {"version": 1, "content": {"type": "doc", "content": _ps_sections("sec_1")}}
        op = {"operation": "replace", "target_section": "sec_1", "content": ["foo", "bar"]}
        result = await self.service.apply_operation(op, doc)
        assert result["_changed"] is False
        assert result["content"]["content"][0]["content"] == []  # unchanged

    @pytest.mark.asyncio
    async def test_apply_operation_insert_string_content_no_crash(self):
        # An insert op whose content is a plain string (or null) must not crash.
        doc = {"version": 1, "content": {"type": "doc", "content": []}}
        op = {"operation": "insert", "target_section": "sec_x", "content": "testo semplice"}
        result = await self.service.apply_operation(op, doc)
        assert result["_changed"] is True
        sec = result["content"]["content"][0]
        assert sec["content"][0]["content"][0]["text"] == "testo semplice"

    @pytest.mark.asyncio
    async def test_apply_operation_insert_null_content_no_crash(self):
        doc = {"version": 1, "content": {"type": "doc", "content": []}}
        op = {"operation": "insert", "target_section": "sec_x", "content": None}
        result = await self.service.apply_operation(op, doc)
        assert result["_changed"] is True

    @pytest.mark.asyncio
    async def test_apply_operation_null_doc_content_yields_valid_root(self):
        # A doc whose content was null must become a proper PM root (type 'doc').
        doc = {"version": 1, "content": None}
        op = {"operation": "insert", "target_section": "sec_x", "content": {"content": "x"}}
        result = await self.service.apply_operation(op, doc)
        assert result["content"]["type"] == "doc"
        assert len(result["content"]["content"]) == 1

    @pytest.mark.asyncio
    async def test_apply_operation_does_not_mutate_input(self):
        doc = {"version": 1, "content": {"type": "doc", "content": []}}
        op = {"operation": "insert", "target_section": "s1", "content": {"content": "x"}}
        await self.service.apply_operation(op, doc)
        assert doc["content"]["content"] == []
        assert doc["version"] == 1
