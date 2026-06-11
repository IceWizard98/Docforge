from dataclasses import dataclass, field
from uuid import uuid4


@dataclass
class DocumentChunk:
    id: str = ""
    document_id: str = ""
    section_id: str | None = None
    chunk_index: int = 0
    text: str = ""
    token_count: int = 0
    metadata: dict = field(default_factory=dict)


def _estimate_tokens(text: str) -> int:
    return len(text) // 4


def _split_section_text(
    text: str, target_tokens: int, overlap_ratio: float
) -> list[tuple[str, int]]:
    overlap_chars = int(target_tokens * 4 * overlap_ratio)
    stride = int(target_tokens * 4) - overlap_chars
    if stride <= 0:
        stride = 1
    chunks: list[tuple[str, int]] = []
    start = 0
    while start < len(text):
        end = start + int(target_tokens * 4)
        chunk_text = text[start:end]
        if not chunk_text:
            break
        chunks.append((chunk_text, _estimate_tokens(chunk_text)))
        start += stride
    return chunks


class ChunkingService:
    def chunk_document(
        self, document: dict, target_tokens: int = 750, overlap: float = 0.1
    ) -> list[DocumentChunk]:
        doc_id = document.get("id", "")
        content = document.get("content", {})
        sections = content.get("sections", []) if isinstance(content, dict) else []
        chunks: list[DocumentChunk] = []
        chunk_index = 0

        for section in sections:
            section_id = section.get("section_id", "")
            section_text = section.get("content", "")
            if not section_text:
                continue
            section_chunks = _split_section_text(section_text, target_tokens, overlap)
            for text, tokens in section_chunks:
                chunk = DocumentChunk(
                    id=f"chk_{uuid4().hex[:12]}",
                    document_id=doc_id,
                    section_id=section_id,
                    chunk_index=chunk_index,
                    text=text,
                    token_count=tokens,
                    metadata={
                        "document_id": doc_id,
                        "section_id": section_id,
                        "chunk_index": chunk_index,
                    },
                )
                chunks.append(chunk)
                chunk_index += 1

        return chunks

    def chunk_text(self, text: str, target_tokens: int = 750) -> list[DocumentChunk]:
        raw_chunks = _split_section_text(text, target_tokens, 0.1)
        return [
            DocumentChunk(
                id=f"chk_{uuid4().hex[:12]}",
                chunk_index=i,
                text=t,
                token_count=c,
                metadata={"chunk_index": i},
            )
            for i, (t, c) in enumerate(raw_chunks)
        ]
