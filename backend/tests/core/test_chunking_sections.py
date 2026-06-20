from core.services.chunking import ChunkingService


def _text(s: str) -> dict:
    return {"type": "text", "text": s}


def _para(s: str) -> dict:
    return {"type": "paragraph", "content": [_text(s)]}


def _section(sid: str, title: str, paras: list[str]) -> dict:
    content = [{"type": "heading", "content": [_text(title)]}]
    content += [_para(p) for p in paras]
    return {"type": "section", "attrs": {"sectionId": sid, "title": title}, "content": content}


class TestChunkProseMirror:
    def setup_method(self):
        self.svc = ChunkingService()

    def test_one_chunk_per_short_section(self):
        content = {"type": "doc", "content": [
            _section("sec_1", "Introduzione", ["Testo introduttivo breve."]),
            _section("sec_2", "Oggetto", ["Definizione dell'oggetto."]),
        ]}
        chunks = self.svc.chunk_prosemirror(content, doc_id="d1", source_id="s1")
        assert len(chunks) == 2
        assert chunks[0].section_id == "sec_1"
        assert chunks[0].metadata["section_title"] == "Introduzione"
        assert "introduttivo" in chunks[0].text
        assert chunks[1].section_id == "sec_2"
        assert all(c.metadata["document_id"] == "d1" for c in chunks)
        assert all(c.metadata["source_document_id"] == "s1" for c in chunks)

    def test_long_section_is_split_into_subchunks(self):
        long_para = "parola " * 1200  # ~1800 tokens worth of chars
        content = {"type": "doc", "content": [_section("sec_1", "Lunga", [long_para])]}
        chunks = self.svc.chunk_prosemirror(content, doc_id="d1", source_id="s1")
        assert len(chunks) > 1
        assert all(c.section_id == "sec_1" for c in chunks)
        # sub-chunk indexes are sequential
        assert [c.chunk_index for c in chunks] == list(range(len(chunks)))

    def test_skips_empty_sections(self):
        content = {"type": "doc", "content": [
            _section("sec_1", "Vuota", []),
            _section("sec_2", "Piena", ["Contenuto."]),
        ]}
        chunks = self.svc.chunk_prosemirror(content, doc_id="d1", source_id="s1")
        assert len(chunks) == 1
        assert chunks[0].section_id == "sec_2"

    def test_handles_non_section_top_level_nodes(self):
        content = {"type": "doc", "content": [
            _para("Paragrafo introduttivo fuori sezione."),
            _section("sec_1", "Prima", ["Corpo."]),
        ]}
        chunks = self.svc.chunk_prosemirror(content, doc_id="d1", source_id="s1")
        # leading paragraph captured as a chunk with no section_id, plus the section
        assert any(c.section_id == "sec_1" for c in chunks)
        assert any(c.section_id is None and "introduttivo" in c.text for c in chunks)

    def test_empty_content_returns_empty(self):
        assert self.svc.chunk_prosemirror({"type": "doc", "content": []}) == []
        assert self.svc.chunk_prosemirror(None) == []
