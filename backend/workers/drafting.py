import asyncio
import logging
from uuid import UUID

from sqlalchemy.orm.attributes import flag_modified

from adapters.llm.factory import get_llm_provider
from adapters.postgresql.models import ChatSessionModel, DraftModel
from adapters.postgresql.pgvector import PgvectorAdapter
from adapters.postgresql.repositories import excluded_source_ids
from config.settings import get_settings
from core.events import DraftGenerated, SectionGenerated
from core.services.context import ContextPackService
from core.services.drafting import (
    DraftService,
    assemble_draft_content,
    build_section_node,
    spec_sections_with_provenance,
)
from core.services.extraction import ExtractionService
from core.services.search import RetrievalFilters
from workers.celery_app import celery_app
from workers.db import worker_engine, worker_session

logger = logging.getLogger(__name__)


async def _extract_section_notes(  # noqa: PLR0913
    session_factory, extraction, provider, section, brief, filters, history,
) -> tuple[str, object | None]:
    """Phase 1: retrieve for a section, then distil style/structure notes.

    Retrieval runs in its OWN short-lived session (opened and closed here) so the
    DB connection is released BEFORE the extraction LLM call — otherwise a
    connection would sit idle-in-transaction for the minutes each section's LLM
    calls take, exhausting the Postgres pool under concurrent drafts. The returned
    ContextPack is plain dataclasses, safe to use after the session closes.

    Returns (notes, notes_pack). notes="" (and notes_pack=None) whenever there's
    nothing usable, so the caller falls back to pure brief-driven drafting. Never
    raises: retrieval failure (DB/embedding) must degrade to brief-only, not fail
    the whole draft.
    """
    try:
        async with session_factory() as session:
            ctx_svc = ContextPackService(pgvector=PgvectorAdapter(session))
            pack = await ctx_svc.build_section_context(
                section_title=section.get("query_hint") or section.get("title", ""),
                filters=filters,
                session_history=history,
            )
    except Exception:
        logger.exception("Section retrieval failed for %s", section.get("title", ""))
        return "", None
    if not getattr(pack, "sources", None):
        return "", None
    notes = await extraction.extract_notes(
        section_title=section.get("title", ""),
        brief=brief,
        context_pack=pack,
        llm=provider,
    )
    return (notes, pack) if notes else ("", None)


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
        async def _run():  # noqa: PLR0915
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

                # Two-phase (draft_extraction_enabled): before writing each section
                # we retrieve the user's OWN corpus (owner-scoped, minus per-document
                # exclusions) and distil STYLE/STRUCTURE notes from it — never the raw
                # text, and never parties/amounts/dates (those stay authoritative in
                # the brief). Kill-switch → pure brief-driven, no retrieval at all.
                extraction_enabled = get_settings().draft_extraction_enabled
                filters: RetrievalFilters | None = None
                if extraction_enabled:
                    async with session_factory() as session:
                        chat_session = await session.get(
                            ChatSessionModel, UUID(chat_session_id)
                        )
                        owner_id = str(chat_session.user_id) if chat_session else None
                        doc_uuid = None
                        if document_id:
                            doc_uuid = UUID(document_id)
                        elif chat_session and chat_session.document_id:
                            doc_uuid = chat_session.document_id
                        excluded = await excluded_source_ids(session, doc_uuid)
                    # No owner → don't retrieve (would leak across users' corpora).
                    if owner_id:
                        filters = RetrievalFilters(
                            owner_id=owner_id, excluded_source_ids=excluded or None
                        )

                # Accumulate previous_sections so the model doesn't repeat itself,
                # and history so each section's consumed chunks are deduplicated from
                # later sections' retrieval.
                previous_sections: list[dict] = []
                history: list[dict] = []
                results: list[dict] = []
                service = DraftService(llm=provider)
                extraction = ExtractionService()

                # No long-lived retrieval session: each section's retrieval opens
                # and closes its own short session inside _extract_section_notes, so
                # no DB connection is held across the (slow) per-section LLM calls.
                for done, sec in enumerate(sections, start=1):
                    notes, notes_pack = "", None
                    if filters is not None:
                        notes, notes_pack = await _extract_section_notes(
                            session_factory, extraction, provider, sec,
                            spec.get("brief", ""), filters, history,
                        )
                    result = await service.generate_section(
                        spec, sec, context_pack=None, llm=provider,
                        previous_sections=previous_sections,
                        ground=False, notes=notes, notes_pack=notes_pack,
                    )
                    results.append(result)
                    previous_sections.append({
                        "title": result.get("title", ""),
                        "content": result.get("content", ""),
                    })
                    consumed = result.get("context_chunk_ids") or []
                    if consumed:
                        history.append({"context_chunks": consumed})
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
def generate_section_task(  # noqa: PLR0915
    draft_id: str, section_id: str, document_id: str | None = None
) -> SectionGenerated:
    """Regenerate a single section in place and persist content + provenance.

    DB sessions are short-lived and never held across the LLM calls: one session
    to load the draft + resolve owner/exclusions, then retrieval (its own session)
    and generation with NO connection held, then a final session to persist. This
    keeps a Postgres connection from sitting idle-in-transaction for the minutes
    the regeneration LLM calls take.
    """
    try:
        async def _run():  # noqa: PLR0915
            async with worker_engine() as session_factory:
                provider = get_llm_provider()
                service = DraftService(llm=provider)

                # 1. Load spec + resolve section + owner/exclusions (short session).
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
                    section = {
                        "section_id": section_id,
                        "title": spec_sections[idx].get("title", ""),
                        "query_hint": spec_sections[idx].get("query_hint", ""),
                    }
                    filters = None
                    if get_settings().draft_extraction_enabled:
                        chat_session = await session.get(
                            ChatSessionModel, draft.chat_session_id
                        )
                        owner_id = str(chat_session.user_id) if chat_session else None
                        if owner_id:
                            doc_uuid = draft.document_id or (
                                chat_session.document_id if chat_session else None
                            )
                            excluded = await excluded_source_ids(session, doc_uuid)
                            filters = RetrievalFilters(
                                owner_id=owner_id, excluded_source_ids=excluded or None
                            )

                # 2. Retrieval (own short session) + generation — no session held.
                notes, notes_pack = "", None
                if filters is not None:
                    notes, notes_pack = await _extract_section_notes(
                        session_factory, ExtractionService(), provider, section,
                        spec.get("brief", ""), filters, None,
                    )
                result = await service.generate_section(
                    spec, section, context_pack=None, llm=provider, ground=False,
                    notes=notes, notes_pack=notes_pack,
                )
                # Keep the existing sectionId stable across regeneration.
                result["section_id"] = section_id

                # 3. Persist content + provenance (short session).
                async with session_factory() as session:
                    draft = await session.get(DraftModel, UUID(draft_id))
                    if draft is None:
                        logger.error("Draft %s vanished before section save", draft_id)
                        return
                    spec = dict(draft.spec or {})
                    spec_sections = spec.get("sections", [])
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
                    if idx < len(spec_sections):
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
