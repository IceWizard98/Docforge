from core.services.chunking import ChunkingService, DocumentChunk


class TestChunkingService:
    def setup_method(self):
        self.service = ChunkingService()

    def test_chunk_text_returns_chunks(self):
        text = "Hello world. " * 500
        chunks = self.service.chunk_text(text, target_tokens=100)
        assert len(chunks) > 0
        assert all(isinstance(c, DocumentChunk) for c in chunks)
        assert all(c.id.startswith("chk_") for c in chunks)

    def test_chunk_text_sequential_indices(self):
        text = "Word. " * 200
        chunks = self.service.chunk_text(text, target_tokens=50)
        for i, c in enumerate(chunks):
            assert c.chunk_index == i

    def test_chunk_text_empty_string(self):
        chunks = self.service.chunk_text("", target_tokens=100)
        assert chunks == []

    def test_chunk_text_short_text(self):
        chunks = self.service.chunk_text("Short text", target_tokens=100)
        assert len(chunks) > 0
        assert chunks[0].text == "Short text"

    def test_chunk_document_with_sections(self):
        doc = {
            "id": "doc_123",
            "content": {
                "sections": [
                    {"section_id": "sec_1", "content": "Section one content. " * 50},
                    {"section_id": "sec_2", "content": "Section two content. " * 50},
                ]
            },
        }
        chunks = self.service.chunk_document(doc, target_tokens=200)
        assert len(chunks) > 0
        for c in chunks:
            assert c.document_id == "doc_123"
            assert c.section_id in ("sec_1", "sec_2")

    def test_chunk_document_empty_sections(self):
        doc = {
            "id": "doc_123",
            "content": {
                "sections": [
                    {"section_id": "sec_1", "content": ""},
                ]
            },
        }
        chunks = self.service.chunk_document(doc)
        assert chunks == []

    def test_chunk_document_no_content(self):
        doc = {"id": "doc_123", "content": {}}
        chunks = self.service.chunk_document(doc)
        assert chunks == []
