import asyncio
import logging

from adapters.llm.factory import get_llm_provider
from core.events import DraftGenerated, SectionGenerated
from core.services.drafting import DraftService
from workers.celery_app import celery_app

logger = logging.getLogger(__name__)


def _reconstruct_context_pack(data: dict | None):
    if not data:
        return None
    from core.services.context import ContextChunk, ContextPack, ContextSource

    sources = []
    for s in data.get("sources", []):
        chunks = [
            ContextChunk(
                chunk_id=c.get("chunk_id", ""),
                content=c.get("content", ""),
                source_doc_id=c.get("source_doc_id", ""),
            )
            for c in s.get("chunks", [])
        ]
        sources.append(ContextSource(doc_id=s.get("doc_id", ""), chunks=chunks))
    return ContextPack(sources=sources, total_tokens=data.get("total_tokens", 0))


@celery_app.task
def generate_draft_task(
    chat_session_id: str, messages: list[dict], document_id: str | None = None
) -> DraftGenerated:
    try:
        provider = get_llm_provider()
        service = DraftService(llm=provider)
        spec = asyncio.run(service.generate_spec(chat_session_id, messages, llm=provider))
        draft_id = spec.get("draft_id", "")
        return DraftGenerated(
            draft_id=draft_id,
            document_id=document_id,
        )
    except Exception as e:
        logger.error("Draft generation failed for session %s: %s", chat_session_id, e)
        return DraftGenerated(draft_id="", document_id=document_id)


@celery_app.task
def generate_section_task(
    draft_id: str, section_id: str, spec: dict, context_pack: dict | None = None
) -> SectionGenerated:
    try:
        provider = get_llm_provider()
        from core.services.context import ContextPackService

        context_svc = ContextPackService()
        service = DraftService(llm=provider, context_service=context_svc)
        section = {"section_id": section_id}
        cp = _reconstruct_context_pack(context_pack)

        asyncio.run(
            service.generate_section(
                spec, section, context_pack=cp, llm=provider, context_service=context_svc
            )
        )
        return SectionGenerated(
            draft_id=draft_id,
            section_id=section_id,
        )
    except Exception as e:
        logger.error("Section generation failed for %s/%s: %s", draft_id, section_id, e)
        return SectionGenerated(draft_id=draft_id, section_id=section_id)
