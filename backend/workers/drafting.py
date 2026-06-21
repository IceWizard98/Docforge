import asyncio
import logging
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm.attributes import flag_modified

from adapters.llm.factory import get_llm_provider
from adapters.postgresql.models import DraftModel
from adapters.postgresql.pgvector import PgvectorAdapter
from config.settings import get_settings
from core.events import DraftGenerated, SectionGenerated
from core.services.context import ContextPackService
from core.services.drafting import (
    DraftService,
    assemble_draft_content,
    build_section_node,
    spec_sections_with_provenance,
)
from workers.celery_app import celery_app

logger = logging.getLogger(__name__)


def _session_factory():
    settings = get_settings()
    engine = create_async_engine(settings.database_url, echo=False)
    return async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


@celery_app.task
def generate_draft_task(
    draft_id: str,
    chat_session_id: str,
    messages: list[dict],
    document_id: str | None = None,
) -> DraftGenerated:
    """Generate the full draft section-by-section and persist it to the DraftModel.

    Each section is grounded via corpus retrieval; content carries per-span
    provenance/placeholder marks and the spec keeps per-section provenance for
    promote-time links.
    """
    try:
        session_factory = _session_factory()

        async def _run():
            async with session_factory() as session:
                provider = get_llm_provider()
                ctx_svc = ContextPackService(
                    pgvector=PgvectorAdapter(session), llm_provider=provider
                )
                service = DraftService(llm=provider, context_service=ctx_svc)

                spec = await service.generate_spec(chat_session_id, messages, llm=provider)
                results = []
                for sec in spec.get("sections", []):
                    results.append(await service.generate_section(
                        spec, sec, context_pack=None, llm=provider, context_service=ctx_svc
                    ))

                draft = await session.get(DraftModel, UUID(draft_id))
                if draft is None:
                    logger.error("Draft %s not found for generation", draft_id)
                    return

                draft.title = spec.get("title") or draft.title
                draft.spec = {
                    **(draft.spec or {}),
                    "title": spec.get("title", ""),
                    "doc_type": spec.get("doc_type", ""),
                    "sections": spec_sections_with_provenance(results),
                }
                draft.content = assemble_draft_content(results)
                draft.progress = {
                    "total_sections": len(results),
                    "completed_sections": len(results),
                }
                draft.status = "completed"
                flag_modified(draft, "spec")
                flag_modified(draft, "content")
                flag_modified(draft, "progress")
                await session.commit()

        asyncio.run(_run())
        return DraftGenerated(draft_id=draft_id, document_id=document_id)
    except Exception as e:
        logger.error("Draft generation failed for %s: %s", draft_id, e)
        _mark_failed(draft_id)
        return DraftGenerated(draft_id=draft_id, document_id=document_id)


@celery_app.task
def generate_section_task(
    draft_id: str, section_id: str, document_id: str | None = None
) -> SectionGenerated:
    """Regenerate a single section in place and persist content + provenance."""
    try:
        session_factory = _session_factory()

        async def _run():
            async with session_factory() as session:
                draft = await session.get(DraftModel, UUID(draft_id))
                if draft is None:
                    logger.error("Draft %s not found for section regen", draft_id)
                    return

                spec = dict(draft.spec or {})
                spec_sections = spec.get("sections", [])
                idx = next(
                    (i for i, s in enumerate(spec_sections)
                     if s.get("section_id") == section_id),
                    None,
                )
                if idx is None:
                    logger.error("Section %s not in draft %s spec", section_id, draft_id)
                    return

                provider = get_llm_provider()
                ctx_svc = ContextPackService(
                    pgvector=PgvectorAdapter(session), llm_provider=provider
                )
                service = DraftService(llm=provider, context_service=ctx_svc)
                section = {
                    "section_id": section_id,
                    "title": spec_sections[idx].get("title", ""),
                }
                result = await service.generate_section(
                    spec, section, context_pack=None, llm=provider, context_service=ctx_svc
                )

                # Update the matching ProseMirror section node + spec provenance.
                content = dict(draft.content or {"type": "doc", "content": []})
                nodes = content.get("content", [])
                for i, node in enumerate(nodes):
                    if (
                        isinstance(node, dict)
                        and node.get("type") == "section"
                        and node.get("attrs", {}).get("sectionId") == section_id
                    ):
                        nodes[i] = build_section_node(result, i)
                        break
                content["content"] = nodes
                spec_sections[idx] = spec_sections_with_provenance([result])[0]
                spec["sections"] = spec_sections

                draft.content = content
                draft.spec = spec
                flag_modified(draft, "content")
                flag_modified(draft, "spec")
                await session.commit()

        asyncio.run(_run())
        return SectionGenerated(draft_id=draft_id, section_id=section_id)
    except Exception as e:
        logger.error("Section generation failed for %s/%s: %s", draft_id, section_id, e)
        return SectionGenerated(draft_id=draft_id, section_id=section_id)


def _mark_failed(draft_id: str) -> None:
    """Best-effort: flip a draft to 'failed' after a generation error."""
    try:
        session_factory = _session_factory()

        async def _run():
            async with session_factory() as session:
                draft = await session.get(DraftModel, UUID(draft_id))
                if draft is not None:
                    draft.status = "failed"
                    await session.commit()

        asyncio.run(_run())
    except Exception:
        logger.exception("Failed to mark draft %s as failed", draft_id)
