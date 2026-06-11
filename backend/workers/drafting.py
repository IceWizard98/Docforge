import asyncio
import logging

from adapters.llm.factory import get_llm_provider
from core.events import DraftGenerated, SectionGenerated
from core.services.drafting import DraftService
from workers.celery_app import celery_app

logger = logging.getLogger(__name__)


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
    draft_id: str, section_id: str, spec: dict, context_pack: dict
) -> SectionGenerated:
    try:
        provider = get_llm_provider()
        service = DraftService(llm=provider)
        section = {"section_id": section_id}
        from core.services.drafting import ContextPack
        cp = ContextPack(**context_pack) if isinstance(context_pack, dict) else context_pack
        asyncio.run(
            service.generate_section(spec, section, cp, llm=provider)
        )
        return SectionGenerated(
            draft_id=draft_id,
            section_id=section_id,
        )
    except Exception as e:
        logger.error("Section generation failed for %s/%s: %s", draft_id, section_id, e)
        return SectionGenerated(draft_id=draft_id, section_id=section_id)


async def generate_draft(spec: dict, document_id: str | None = None) -> DraftGenerated:
    return DraftGenerated(
        draft_id=spec.get("draft_id", ""),
        document_id=document_id,
    )


async def generate_section(
    draft_id: str, section_id: str, spec: dict, context_pack: dict
) -> SectionGenerated:
    return SectionGenerated(
        draft_id=draft_id,
        section_id=section_id,
    )
