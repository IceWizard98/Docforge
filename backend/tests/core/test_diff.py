from core.services.diff import DiffService


class TestDiffService:
    def setup_method(self):
        self.service = DiffService()

    def test_compute_diff_empty(self):
        before = {"id": "doc_1", "content": {"sections": []}}
        after = {"id": "doc_1", "content": {"sections": []}}
        result = self.service.compute_diff(before, after, 1, 2)
        assert len(result["operations"]) == 0

    def test_compute_diff_added_section(self):
        before = {"id": "doc_1", "content": {"sections": []}}
        after = {
            "id": "doc_1",
            "content": {
                "sections": [
                    {"section_id": "sec_1", "title": "New Section", "content": "Text"}
                ]
            },
        }
        result = self.service.compute_diff(before, after, 1, 2)
        assert len(result["operations"]) == 1
        assert result["operations"][0]["type"] == "insert"
        assert result["operations"][0]["section_id"] == "sec_1"

    def test_compute_diff_removed_section(self):
        before = {
            "id": "doc_1",
            "content": {
                "sections": [
                    {"section_id": "sec_1", "title": "Old", "content": "Text"}
                ]
            },
        }
        after = {"id": "doc_1", "content": {"sections": []}}
        result = self.service.compute_diff(before, after, 1, 2)
        assert len(result["operations"]) == 1
        assert result["operations"][0]["type"] == "delete"
        assert result["operations"][0]["section_id"] == "sec_1"

    def test_compute_diff_modified_section(self):
        before = {
            "id": "doc_1",
            "content": {
                "sections": [
                    {"section_id": "sec_1", "title": "Old", "content": "Old text"}
                ]
            },
        }
        after = {
            "id": "doc_1",
            "content": {
                "sections": [
                    {"section_id": "sec_1", "title": "New", "content": "New text"}
                ]
            },
        }
        result = self.service.compute_diff(before, after, 1, 2)
        assert len(result["operations"]) == 1
        assert result["operations"][0]["type"] == "replace"

    def test_compute_diff_combined(self):
        before = {
            "id": "doc_1",
            "content": {
                "sections": [
                    {"section_id": "sec_1", "title": "Keep", "content": "Same"},
                    {"section_id": "sec_2", "title": "Remove", "content": "Bye"},
                ]
            },
        }
        after = {
            "id": "doc_1",
            "content": {
                "sections": [
                    {"section_id": "sec_1", "title": "Keep", "content": "Same"},
                    {"section_id": "sec_3", "title": "Add", "content": "New"},
                ]
            },
        }
        result = self.service.compute_diff(before, after, 1, 2)
        types = {op["type"] for op in result["operations"]}
        assert "insert" in types
        assert "delete" in types

    def test_compute_summary(self):
        operations = [
            {"type": "insert"},
            {"type": "insert"},
            {"type": "delete"},
            {"type": "replace"},
        ]
        summary = self.service.compute_summary(operations)
        assert summary["total"] == 4
        assert summary["insertions"] == 2
        assert summary["deletions"] == 1
        assert summary["modifications"] == 1

    def test_compute_summary_empty(self):
        summary = self.service.compute_summary([])
        assert summary["total"] == 0

    def test_versions_in_result(self):
        before = {"id": "doc_1", "content": {"sections": []}}
        after = {"id": "doc_1", "content": {"sections": []}}
        result = self.service.compute_diff(before, after, 3, 4)
        assert result["version_from"] == 3
        assert result["version_to"] == 4
