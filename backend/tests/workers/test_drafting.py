"""The draft worker must generate sections SEQUENTIALLY, brief-driven.

Drafting is brief-driven (ground=False): the corpus is NOT injected, so an
unrelated source document can't contaminate the new document. Sections are still
generated one at a time, each fed the already-written sections (previous_sections)
so the model doesn't repeat itself.
"""

import uuid
from unittest.mock import AsyncMock, MagicMock, patch


def _session_cm(session):
    cm = AsyncMock()
    cm.__aenter__.return_value = session
    cm.__aexit__.return_value = False
    return cm


@patch("workers.drafting.get_settings")
@patch("workers.drafting.get_llm_provider")
@patch("workers.drafting.DraftService")
@patch("workers.drafting.worker_engine")
def test_generate_draft_sequential_brief_driven(
    mock_worker_engine, mock_draft_service_cls, mock_get_llm, mock_get_settings
):
    from workers.drafting import generate_draft_task

    # Extraction OFF: this test pins the pure brief-driven sequential behavior.
    mock_get_settings.return_value = MagicMock(draft_extraction_enabled=False)

    draft = MagicMock()
    draft.spec = {"doc_type": "contract"}
    draft.title = ""

    session = AsyncMock()
    session.get.return_value = draft

    # worker_engine() -> async cm yielding a session_factory; the factory is
    # called as session_factory() -> async cm yielding a session.
    session_factory = MagicMock(side_effect=lambda: _session_cm(session))
    mock_worker_engine.return_value = _session_cm(session_factory)

    svc = MagicMock()
    svc.generate_spec = AsyncMock(
        return_value={
            "draft_id": "d1",
            "title": "T",
            "brief": "b",
            "sections": [
                {"section_id": "s0", "title": "Premesse"},
                {"section_id": "s1", "title": "Oggetto"},
            ],
        }
    )

    captured: list[dict] = []

    async def fake_generate_section(  # noqa: PLR0913
        spec, sec, context_pack=None, llm=None, context_service=None,
        session_history=None, previous_sections=None, ground=True,
        notes="", notes_pack=None,
    ):
        # Snapshot: the worker passes ONE list mutated in place across sections,
        # so we must freeze its state at call time, not hold a live reference.
        captured.append(
            {
                "section_id": sec["section_id"],
                "ground": ground,
                "previous_sections": list(previous_sections or []),
            }
        )
        return {
            "section_id": sec["section_id"],
            "title": sec["title"],
            "content": f"body {sec['section_id']}",
            "status": "draft",
            "provenance": [],
            "runs": [],
            "placeholders": [],
            "context_chunk_ids": [],
        }

    svc.generate_section = AsyncMock(side_effect=fake_generate_section)
    mock_draft_service_cls.return_value = svc

    generate_draft_task(str(uuid.uuid4()), "chat_1", [{"role": "user", "content": "hi"}])

    # doc_type from the seed spec is forwarded to the outline builder.
    _, kwargs = svc.generate_spec.call_args
    assert kwargs.get("doc_type") == "contract"

    # Both sections generated, in order, brief-driven (no corpus).
    assert [c["section_id"] for c in captured] == ["s0", "s1"]
    assert all(c["ground"] is False for c in captured)

    # Section 0 has no prior sections; section 1 sees section 0's title.
    assert not captured[0]["previous_sections"]
    prev_titles = [p["title"] for p in captured[1]["previous_sections"]]
    assert "Premesse" in prev_titles

    # Draft persisted as completed.
    assert draft.status == "completed"


def _extraction_env(mock_worker_engine, mock_draft_service_cls, extraction_enabled):
    """Wire the common mocks for the two-phase (extraction) worker tests.

    Returns (session, svc, captured, ctx_calls, extract_mock).
    """
    from core.services.context import ContextChunk, ContextPack, ContextSource

    draft = MagicMock()
    draft.spec = {"doc_type": "contract"}
    draft.title = ""
    draft.document_id = None

    chat_session = MagicMock()
    chat_session.user_id = uuid.uuid4()
    chat_session.document_id = uuid.uuid4()

    session = AsyncMock()

    def _get(model, ident):
        # ChatSessionModel resolves the owner; anything else is the draft row.
        if getattr(model, "__name__", "") == "ChatSessionModel":
            return chat_session
        return draft

    session.get = AsyncMock(side_effect=_get)

    exc_result = MagicMock()
    exc_result.scalars.return_value.all.return_value = [uuid.uuid4()]  # one excluded source
    session.execute = AsyncMock(return_value=exc_result)

    session_factory = MagicMock(side_effect=lambda: _session_cm(session))
    mock_worker_engine.return_value = _session_cm(session_factory)

    svc = MagicMock()
    svc.generate_spec = AsyncMock(
        return_value={
            "draft_id": "d1", "title": "T", "brief": "b",
            "sections": [
                {"section_id": "s0", "title": "Premesse", "query_hint": "parti, ragione sociale"},
                {"section_id": "s1", "title": "Oggetto", "query_hint": "oggetto, prestazioni"},
            ],
        }
    )

    captured: list[dict] = []

    async def fake_generate_section(  # noqa: PLR0913
        spec, sec, context_pack=None, llm=None, context_service=None,
        session_history=None, previous_sections=None, ground=True,
        notes="", notes_pack=None,
    ):
        ids = []
        if notes_pack is not None:
            for src in notes_pack.sources:
                ids += [c.chunk_id for c in src.chunks]
        captured.append({"section_id": sec["section_id"], "notes": notes, "chunk_ids": ids})
        return {
            "section_id": sec["section_id"], "title": sec["title"],
            "content": f"body {sec['section_id']}", "status": "draft",
            "provenance": [], "runs": [], "placeholders": [], "context_chunk_ids": ids,
        }

    svc.generate_section = AsyncMock(side_effect=fake_generate_section)
    mock_draft_service_cls.return_value = svc

    pack = ContextPack(
        sources=[ContextSource(doc_id="d1", chunks=[ContextChunk(chunk_id="chk_a", content="t")])]
    )
    ctx_calls: list[dict] = []

    async def fake_build(section_title="", filters=None, session_history=None, **kw):
        ctx_calls.append(
            {"section_title": section_title, "filters": filters,
             "session_history": list(session_history or [])}
        )
        return pack

    ctx_instance = MagicMock()
    ctx_instance.build_section_context = AsyncMock(side_effect=fake_build)

    extract_mock = AsyncMock(return_value="- appunto di stile")
    extract_instance = MagicMock()
    extract_instance.extract_notes = extract_mock

    return (
        session, svc, captured, ctx_calls, ctx_instance, extract_instance,
        extract_mock, chat_session,
    )


@patch("workers.drafting.PgvectorAdapter")
@patch("workers.drafting.ExtractionService")
@patch("workers.drafting.ContextPackService")
@patch("workers.drafting.get_settings")
@patch("workers.drafting.get_llm_provider")
@patch("workers.drafting.DraftService")
@patch("workers.drafting.worker_engine")
def test_generate_draft_two_phase_extraction(  # noqa: PLR0913
    mock_worker_engine, mock_draft_service_cls, mock_get_llm, mock_get_settings,
    mock_ctx_cls, mock_extract_cls, mock_pgvector,
):
    from workers.drafting import generate_draft_task

    mock_get_settings.return_value = MagicMock(draft_extraction_enabled=True)
    (session, svc, captured, ctx_calls, ctx_instance, extract_instance,
     extract_mock, chat_session) = _extraction_env(
        mock_worker_engine, mock_draft_service_cls, extraction_enabled=True
    )
    mock_ctx_cls.return_value = ctx_instance
    mock_extract_cls.return_value = extract_instance

    generate_draft_task(str(uuid.uuid4()), str(uuid.uuid4()), [{"role": "user", "content": "hi"}])

    # Extraction runs once per section.
    assert extract_mock.await_count == 2
    # Retrieval uses the slot query_hint, and filters carry owner + exclusions.
    assert ctx_calls[0]["section_title"] == "parti, ragione sociale"
    assert ctx_calls[0]["filters"].owner_id == str(chat_session.user_id)
    assert ctx_calls[0]["filters"].excluded_source_ids  # one excluded source id
    # History dedup grows: section 1's retrieval sees section 0's consumed chunk.
    assert not ctx_calls[0]["session_history"]
    assert any("chk_a" in (h.get("context_chunks") or []) for h in ctx_calls[1]["session_history"])
    # Notes were passed into section generation.
    assert all(c["notes"] == "- appunto di stile" for c in captured)


@patch("workers.drafting.PgvectorAdapter")
@patch("workers.drafting.ExtractionService")
@patch("workers.drafting.ContextPackService")
@patch("workers.drafting.get_settings")
@patch("workers.drafting.get_llm_provider")
@patch("workers.drafting.DraftService")
@patch("workers.drafting.worker_engine")
def test_generate_draft_extraction_kill_switch(  # noqa: PLR0913
    mock_worker_engine, mock_draft_service_cls, mock_get_llm, mock_get_settings,
    mock_ctx_cls, mock_extract_cls, mock_pgvector,
):
    from workers.drafting import generate_draft_task

    mock_get_settings.return_value = MagicMock(draft_extraction_enabled=False)
    (session, svc, captured, ctx_calls, ctx_instance, extract_instance,
     extract_mock, chat_session) = _extraction_env(
        mock_worker_engine, mock_draft_service_cls, extraction_enabled=False
    )
    mock_ctx_cls.return_value = ctx_instance
    mock_extract_cls.return_value = extract_instance

    generate_draft_task(str(uuid.uuid4()), str(uuid.uuid4()), [{"role": "user", "content": "hi"}])

    # Kill-switch off: no retrieval, no extraction, pure brief-driven.
    assert extract_mock.await_count == 0
    assert ctx_calls == []
    assert all(c["notes"] == "" for c in captured)
    assert [c["section_id"] for c in captured] == ["s0", "s1"]


@patch("workers.drafting.PgvectorAdapter")
@patch("workers.drafting.ExtractionService")
@patch("workers.drafting.ContextPackService")
@patch("workers.drafting.get_settings")
@patch("workers.drafting.get_llm_provider")
@patch("workers.drafting.DraftService")
@patch("workers.drafting.worker_engine")
def test_generate_draft_retrieval_failure_degrades_to_brief_only(  # noqa: PLR0913
    mock_worker_engine, mock_draft_service_cls, mock_get_llm, mock_get_settings,
    mock_ctx_cls, mock_extract_cls, mock_pgvector,
):
    from workers.drafting import generate_draft_task

    mock_get_settings.return_value = MagicMock(draft_extraction_enabled=True)
    (session, svc, captured, ctx_calls, ctx_instance, extract_instance,
     extract_mock, chat_session) = _extraction_env(
        mock_worker_engine, mock_draft_service_cls, extraction_enabled=True
    )
    # Retrieval blows up (DB/embedding) — the draft must still complete brief-only.
    ctx_instance.build_section_context = AsyncMock(side_effect=RuntimeError("pgvector down"))
    mock_ctx_cls.return_value = ctx_instance
    mock_extract_cls.return_value = extract_instance

    generate_draft_task(str(uuid.uuid4()), str(uuid.uuid4()), [{"role": "user", "content": "hi"}])

    assert extract_mock.await_count == 0  # no extraction without a pack
    assert all(c["notes"] == "" for c in captured)
    assert [c["section_id"] for c in captured] == ["s0", "s1"]
