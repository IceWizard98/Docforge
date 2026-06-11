from dataclasses import dataclass, field
from uuid import uuid4


@dataclass
class ContextPack:
    chunks: list[dict] = field(default_factory=list)
    clauses: list[dict] = field(default_factory=list)
    source_documents: list[dict] = field(default_factory=list)


class DraftService:
    async def generate_spec(self, chat_session_id: str, messages: list[dict]) -> dict:
        spec = {
            "draft_id": f"draft_{uuid4().hex[:8]}",
            "chat_session_id": chat_session_id,
            "title": "Generated Document",
            "sections": [],
            "metadata": {},
        }
        last_message = messages[-1]["content"] if messages else ""
        spec["title"] = f"Draft from chat {chat_session_id[:8]}"
        spec["metadata"]["source"] = "chat"
        spec["metadata"]["message_count"] = len(messages)
        spec["metadata"]["intent"] = last_message[:200] if last_message else ""
        return spec

    async def generate_section(
        self, spec: dict, section: dict, context_pack: ContextPack
    ) -> dict:
        return {
            "section_id": section.get("section_id", f"sec_{uuid4().hex[:8]}"),
            "title": section.get("title", ""),
            "content": "",
            "status": "draft",
            "provenance": [
                {
                    "source": c.get("document_id", ""),
                    "confidence": 0.0,
                }
                for c in context_pack.chunks[:3]
            ],
        }

    async def compose_context_pack(
        self, document_id: str, section_id: str, retrieved_chunks: list[dict]
    ) -> ContextPack:
        return ContextPack(
            chunks=retrieved_chunks,
            clauses=[],
            source_documents=[],
        )
