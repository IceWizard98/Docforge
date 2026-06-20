import pytest

from adapters.export.markdown import export_markdown


class TestExportMarkdown:
    def test_heading_conversion(self):
        content = {
            "type": "doc",
            "content": [
                {"type": "heading", "attrs": {"level": 1}, "content": [{"type": "text", "text": "Title"}]},
                {"type": "heading", "attrs": {"level": 2}, "content": [{"type": "text", "text": "Section"}]},
            ],
        }
        result = export_markdown(content)
        assert "# Title" in result
        assert "## Section" in result

    def test_paragraph_conversion(self):
        content = {
            "type": "doc",
            "content": [
                {"type": "paragraph", "content": [{"type": "text", "text": "Hello world"}]},
            ],
        }
        result = export_markdown(content)
        assert "Hello world" in result

    def test_bold_italic_code_marks(self):
        content = {
            "type": "doc",
            "content": [
                {"type": "paragraph", "content": [
                    {"type": "text", "marks": [{"type": "bold"}], "text": "bold"},
                    {"type": "text", "text": " "},
                    {"type": "text", "marks": [{"type": "italic"}], "text": "italic"},
                    {"type": "text", "text": " "},
                    {"type": "text", "marks": [{"type": "code"}], "text": "code"},
                ]},
            ],
        }
        result = export_markdown(content)
        assert "**bold**" in result
        assert "*italic*" in result
        assert "`code`" in result

    def test_bullet_list(self):
        content = {
            "type": "doc",
            "content": [
                {"type": "bulletList", "content": [
                    {"type": "listItem", "content": [{"type": "paragraph", "content": [{"type": "text", "text": "Item 1"}]}]},
                    {"type": "listItem", "content": [{"type": "paragraph", "content": [{"type": "text", "text": "Item 2"}]}]},
                ]},
            ],
        }
        result = export_markdown(content)
        assert "- Item 1" in result
        assert "- Item 2" in result

    def test_ordered_list(self):
        content = {
            "type": "doc",
            "content": [
                {"type": "orderedList", "content": [
                    {"type": "listItem", "content": [{"type": "paragraph", "content": [{"type": "text", "text": "First"}]}]},
                    {"type": "listItem", "content": [{"type": "paragraph", "content": [{"type": "text", "text": "Second"}]}]},
                ]},
            ],
        }
        result = export_markdown(content)
        assert "1. First" in result
        assert "2. Second" in result

    def test_blockquote(self):
        content = {
            "type": "doc",
            "content": [
                {"type": "blockquote", "content": [
                    {"type": "paragraph", "content": [{"type": "text", "text": "quoted"}]},
                ]},
            ],
        }
        result = export_markdown(content)
        assert "> quoted" in result

    def test_code_block(self):
        content = {
            "type": "doc",
            "content": [
                {"type": "codeBlock", "attrs": {"language": "python"}, "content": [
                    {"type": "text", "text": "print('hello')"},
                ]},
            ],
        }
        result = export_markdown(content)
        assert "```python" in result
        assert "print('hello')" in result
        assert "```" in result

    def test_horizontal_rule(self):
        content = {
            "type": "doc",
            "content": [
                {"type": "horizontalRule"},
            ],
        }
        result = export_markdown(content)
        assert "---" in result

    def test_empty_document(self):
        content = {"type": "doc", "content": []}
        result = export_markdown(content)
        assert result == ""

    def test_nested_content(self):
        """Deeply nested nodes should still render."""
        content = {
            "type": "doc",
            "content": [
                {"type": "section", "attrs": {"sectionId": "s1"}, "content": [
                    {"type": "heading", "attrs": {"level": 2}, "content": [{"type": "text", "text": "Section Title"}]},
                    {"type": "clause", "attrs": {"clauseId": "c1"}, "content": [
                        {"type": "paragraph", "content": [{"type": "text", "text": "Clause content"}]},
                    ]},
                ]},
            ],
        }
        result = export_markdown(content)
        assert "Section Title" in result
        assert "Clause content" in result

    def test_table(self):
        content = {
            "type": "doc",
            "content": [
                {"type": "table", "content": [
                    {"type": "tableRow", "content": [
                        {"type": "tableHeader", "content": [{"type": "paragraph", "content": [{"type": "text", "text": "Col A"}]}]},
                        {"type": "tableHeader", "content": [{"type": "paragraph", "content": [{"type": "text", "text": "Col B"}]}]},
                    ]},
                    {"type": "tableRow", "content": [
                        {"type": "tableCell", "content": [{"type": "paragraph", "content": [{"type": "text", "text": "Val 1"}]}]},
                        {"type": "tableCell", "content": [{"type": "paragraph", "content": [{"type": "text", "text": "Val 2"}]}]},
                    ]},
                ]},
            ],
        }
        result = export_markdown(content)
        assert "| Col A | Col B |" in result
        assert "| Val 1 | Val 2 |" in result
