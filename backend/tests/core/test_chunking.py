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
