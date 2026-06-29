import asyncio
import logging
from uuid import UUID

from sqlalchemy.orm.attributes import flag_modified

from adapters.llm.factory import get_llm_provider
from adapters.postgresql.models import DraftModel
from core.events import DraftGenerated, SectionGenerated
from core.services.drafting import (
    DraftService,
    assemble_draft_content,
    build_section_node,
    spec_sections_with_provenance,
)
from workers.celery_app import celery_app
from workers.db import worker_engine, worker_session

logger = logging.getLogger(__name__)


@celery_app.task
def generate_draft_task(  # noqa: PLR0915
    draft_id: str,
    chat_session_id: str,
    messages: list[dict],
    document_id: str | None = None,
) -> DraftGenerated:
    """Generate the full draft section-by-section and persist it to the DraftModel.

    Sections are generated SEQUENTIALLY and BRIEF-DRIVEN (ground=False): the
    corpus is not injected, because it holds the user's OTHER documents and weak
    models copy their parties/amounts/dates into the new one. Each later section
    is fed the sections already written (``previous_sections``) so the model
    doesn't repeat itself. The outline comes from the slot schema for the
    chat-captured doc_type.
    """
    try:
        async def _run():
            async with worker_engine() as session_factory:
                provider = get_llm_provider()

                # Read the chat-captured doc_type so the outline can come from the
                # slot schema (deterministic, type-correct) instead of a weak
                # model's generic invention.
                async with session_factory() as session:
                    seed = await session.get(DraftModel, UUID(draft_id))
                    seed_doc_type = (seed.spec or {}).get("doc_type", "") if seed else ""

                spec = await DraftService(llm=provider).generate_spec(
                    chat_session_id, messages, llm=provider, doc_type=seed_doc_type
                )
                sections = spec.get("sections", [])
                total = len(sections)

                async def _set_progress(completed: int) -> None:
                    # Tiny UPDATE so the UI sees the document being built section by
                    # section instead of a dead 0/0 spinner for minutes.
                    async with session_factory() as session:
                        d = await session.get(DraftModel, UUID(draft_id))
                        if d is not None:
                            d.progress = {"total_sections": total, "completed_sections": completed}
                            flag_modified(d, "progress")
                            await session.commit()

                # Show the real total up front.
                await _set_progress(0)

                # Brief-driven: sections are written from the user's brief, NOT the
                # corpus (which holds the user's OTHER documents and would
                # contaminate the new one). Accumulate previous_sections so the
                # model doesn't repeat itself across sections.
                previous_sections: list[dict] = []
                results: list[dict] = []
                service = DraftService(llm=provider)

                for done, sec in enumerate(sections, start=1):
                    result = await service.generate_section(
                        spec, sec, context_pack=None, llm=provider,
                        previous_sections=previous_sections,
                        ground=False,
                    )
                    results.append(result)
                    previous_sections.append({
                        "title": result.get("title", ""),
                        "content": result.get("content", ""),
                    })
                    await _set_progress(done)

                async with session_factory() as session:
                    draft = await session.get(DraftModel, UUID(draft_id))
                    if draft is None:
                        logger.error("Draft %s not found for generation", draft_id)
                        return

                    existing_spec = draft.spec or {}
                    if not results:
                        # No outline/sections produced (weak model or spec failure):
                        # fail loudly instead of silently completing with an empty
                        # document that the frontend would write over the open doc.
                        logger.error("Draft %s produced no sections; marking failed", draft_id)
                        draft.status = "failed"
                        flag_modified(draft, "status")
                        await session.commit()
                        return

                    draft.title = spec.get("title") or draft.title
                    draft.spec = {
                        **existing_spec,
                        "title": spec.get("title") or existing_spec.get("title", ""),
                        # Preserve the chat-captured doc_type/language; generate_spec
                        # doesn't emit them. Persist the brief for section regen.
                        "doc_type": existing_spec.get("doc_type") or spec.get("doc_type", ""),
                        "language": existing_spec.get("language", "it"),
                        "brief": spec.get("brief", "") or existing_spec.get("brief", ""),
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
        async def _run():
            async with worker_session() as session:
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
                # Brief-driven, consistent with generate_draft_task: no corpus
                # injection (it would contaminate the regenerated section).
                service = DraftService(llm=provider)
                section = {
                    "section_id": section_id,
                    "title": spec_sections[idx].get("title", ""),
                }
                result = await service.generate_section(
                    spec, section, context_pack=None, llm=provider, ground=False
                )
                # Keep the existing sectionId stable across regeneration.
                result["section_id"] = section_id

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
        async def _run():
            async with worker_session() as session:
                draft = await session.get(DraftModel, UUID(draft_id))
                if draft is not None:
                    draft.status = "failed"
                    await session.commit()

        asyncio.run(_run())
    except Exception:
        logger.exception("Failed to mark draft %s as failed", draft_id)
