"""The draft worker must generate sections SEQUENTIALLY and accumulate context.

On a weak local model, generating all sections in parallel with the same
retrieved chunks makes the model repeat the same source text across sections.
Generating one section at a time and feeding each later section (a) the chunk
ids already consumed (session_history) and (b) the sections already written
(previous_sections) lets it dedup retrieval and avoid repetition.
"""

import uuid
from unittest.mock import AsyncMock, MagicMock, patch


def _session_cm(session):
    cm = AsyncMock()
    cm.__aenter__.return_value = session
    cm.__aexit__.return_value = False
    return cm


@patch("workers.drafting.PgvectorAdapter")
@patch("workers.drafting.ContextPackService")
@patch("workers.drafting.get_llm_provider")
@patch("workers.drafting.DraftService")
@patch("workers.drafting.worker_engine")
def test_generate_draft_sequential_accumulates_context(
    mock_worker_engine, mock_draft_service_cls, mock_get_llm, mock_ctx_cls, mock_pg_cls
):
    from workers.drafting import generate_draft_task

    draft = MagicMock()
    draft.spec = {}
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
        session_history=None, previous_sections=None,
    ):
        # Snapshot: the worker passes ONE list mutated in place across sections,
        # so we must freeze its state at call time, not hold a live reference.
        captured.append(
            {
                "section_id": sec["section_id"],
                "session_history": list(session_history or []),
                "previous_sections": list(previous_sections or []),
            }
        )
        cid = f"chk_{sec['section_id']}"
        return {
            "section_id": sec["section_id"],
            "title": sec["title"],
            "content": f"body {sec['section_id']}",
            "status": "draft",
            "provenance": [],
            "runs": [],
            "placeholders": [],
            "context_chunk_ids": [cid],
        }

    svc.generate_section = AsyncMock(side_effect=fake_generate_section)
    mock_draft_service_cls.return_value = svc

    generate_draft_task(str(uuid.uuid4()), "chat_1", [{"role": "user", "content": "hi"}])

    # Both sections generated, in order.
    assert [c["section_id"] for c in captured] == ["s0", "s1"]

    # Section 0 has no prior context.
    assert not captured[0]["session_history"]
    assert not captured[0]["previous_sections"]

    # Section 1 must SEE section 0's consumed chunk + its written content.
    used_chunks = [
        c
        for entry in (captured[1]["session_history"] or [])
        for c in entry.get("context_chunks", [])
    ]
    assert "chk_s0" in used_chunks
    prev_titles = [p["title"] for p in (captured[1]["previous_sections"] or [])]
    assert "Premesse" in prev_titles

    # Draft persisted as completed.
    assert draft.status == "completed"
