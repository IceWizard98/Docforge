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


@patch("workers.drafting.get_llm_provider")
@patch("workers.drafting.DraftService")
@patch("workers.drafting.worker_engine")
def test_generate_draft_sequential_brief_driven(
    mock_worker_engine, mock_draft_service_cls, mock_get_llm
):
    from workers.drafting import generate_draft_task

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
