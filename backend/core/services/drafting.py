import logging
from dataclasses import dataclass, field
from uuid import uuid4

from ports.llm import LLMProvider

logger = logging.getLogger(__name__)


@dataclass
class DocumentSpec:
    draft_id: str = ""
    chat_session_id: str = ""
    title: str = ""
    sections: list[dict] = field(default_factory=list)
    metadata: dict = field(default_factory=dict)


@dataclass
class DraftSection:
    section_id: str = ""
    title: str = ""
    content: str = ""
    status: str = "draft"
    provenance: list[dict] = field(default_factory=list)


@dataclass
class ContextPack:
    chunks: list[dict] = field(default_factory=list)
    clauses: list[dict] = field(default_factory=list)
    source_documents: list[dict] = field(default_factory=list)


SPEC_PROMPT_TEMPLATE = """Analyze the following chat messages and produce a document spec outline.

Chat messages:
{messages}

Return a JSON object with:
- "title": a concise document title
- "sections": array of {{"section_id": "slug", "title": "..."}}

Respond with valid JSON only."""

SECTION_PROMPT_TEMPLATE = """Write content for the document section based on spec and context.

Document title: {title}
Section title: {section_title}
Section ID: {section_id}

Context:
{context}

Write the full content for this section in a professional, clear style.
Return a JSON object with:
- "content": the full section text
- "provenance": array of {{"source": "...", "confidence": <float>}} if context was used

Respond with valid JSON only."""


class DraftService:
    def __init__(self, llm: LLMProvider | None = None):
        self._llm = llm

    async def generate_spec(
        self, chat_session_id: str, messages: list[dict], llm: LLMProvider | None = None
    ) -> dict:
        provider = llm or self._llm
        if provider:
            last_message = messages[-1]["content"] if messages else ""
            prompt = SPEC_PROMPT_TEMPLATE.format(
                messages=last_message[:3000] if last_message else "(no messages)"
            )
            try:
                result = await provider.generate_structured(prompt, dict)
                return {
                    "draft_id": f"draft_{uuid4().hex[:8]}",
                    "chat_session_id": chat_session_id,
                    "title": result.get("title", f"Draft from chat {chat_session_id[:8]}"),
                    "sections": result.get("sections", []),
                    "metadata": {
                        "source": "chat",
                        "message_count": len(messages),
                        "intent": last_message[:200] if last_message else "",
                    },
                }
            except Exception:
                logger.exception("LLM spec generation failed for session %s", chat_session_id)
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
        self, spec: dict, section: dict, context_pack: ContextPack, llm: LLMProvider | None = None
    ) -> dict:
        provider = llm or self._llm
        if provider:
            context_text = "\n".join(
                c.get("text", "") for c in context_pack.chunks
            )[:4000]
            prompt = SECTION_PROMPT_TEMPLATE.format(
                title=spec.get("title", ""),
                section_title=section.get("title", ""),
                section_id=section.get("section_id", ""),
                context=context_text or "(no context available)",
            )
            try:
                result = await provider.generate_structured(prompt, dict)
                content = result.get("content", "")
                provenance_raw = result.get("provenance", [])
                provenance = [
                    {
                        "source": p.get("source", c.get("document_id", "")),
                        "confidence": p.get("confidence", 0.0),
                    }
                    for c in context_pack.chunks[:3]
                    for p in (provenance_raw if provenance_raw else [{}])
                ][:3]
                return {
                    "section_id": section.get("section_id", f"sec_{uuid4().hex[:8]}"),
                    "title": section.get("title", ""),
                    "content": content,
                    "status": "draft",
                    "provenance": provenance,
                }
            except Exception:
                logger.exception(
                    "LLM section generation failed for %s/%s",
                    spec.get("draft_id", ""),
                    section.get("section_id", ""),
                )
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
