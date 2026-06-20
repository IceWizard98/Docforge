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


def _node_text(node: dict) -> str:
    """Recursively extract plain text from a ProseMirror node."""
    if not isinstance(node, dict):
        return ""
    if node.get("type") == "text":
        return node.get("text", "")
    parts = [_node_text(child) for child in node.get("content", []) or []]
    block_types = {"paragraph", "heading", "blockquote", "listItem", "clause", "codeBlock"}
    joiner = "\n" if node.get("type") in block_types else ""
    return joiner.join(p for p in parts if p)


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
    def chunk_prosemirror(
        self,
        content: dict | None,
        doc_id: str = "",
        source_id: str = "",
        target_tokens: int = 750,
        overlap: float = 0.1,
    ) -> list[DocumentChunk]:
        """Section-aware chunking of a ProseMirror document.

        One chunk per top-level section node (split into sub-chunks if it exceeds
        target_tokens), carrying sectionId + title in metadata. Non-section
        top-level nodes are captured as section-less chunks so nothing is lost.
        """
        if not isinstance(content, dict):
            return []
        nodes = content.get("content", [])
        if not isinstance(nodes, list):
            return []

        chunks: list[DocumentChunk] = []
        chunk_index = 0

        def _emit(text: str, section_id: str | None, title: str) -> None:
            nonlocal chunk_index
            text = text.strip()
            if not text:
                return
            for raw_part, tokens in _split_section_text(text, target_tokens, overlap):
                part = raw_part.strip()
                if not part:
                    continue
                meta = {
                    "document_id": doc_id,
                    "source_document_id": source_id,
                    "chunk_index": chunk_index,
                }
                if section_id is not None:
                    meta["section_id"] = section_id
                if title:
                    meta["section_title"] = title
                chunks.append(DocumentChunk(
                    id=f"chk_{uuid4().hex[:12]}",
                    document_id=doc_id,
                    section_id=section_id,
                    chunk_index=chunk_index,
                    text=part,
                    token_count=tokens,
                    metadata=meta,
                ))
                chunk_index += 1

        for node in nodes:
            if not isinstance(node, dict):
                continue
            if node.get("type") == "section":
                attrs = node.get("attrs", {})
                section_id = attrs.get("sectionId")
                title = attrs.get("title", "")
                body = "\n".join(
                    _node_text(c)
                    for c in node.get("content", []) or []
                    if isinstance(c, dict) and c.get("type") != "heading"
                ).strip()
                if not body:
                    continue
                text = f"{title}\n{body}" if title else body
                _emit(text, section_id, title)
            else:
                _emit(_node_text(node), None, "")

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
