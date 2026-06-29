import uuid
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from api.routes.chat import (
    _execute_draft_action,
    _handle_document_action,
    _resolve_assistant_action,
)


class TestExecuteDraftActionAsync:
    @pytest.mark.asyncio
    async def test_dispatches_worker_with_generating_status(self):
        # Local-first: the chat only signals intent; the per-section worker builds
        # the document. The draft is created 'generating' and the worker dispatched
        # with the conversation (so generate_spec/section see the user's brief).
        action = {"type": "draft", "params": {"title": "Contratto X", "doc_type": "contract"}}
        session = MagicMock()
        session.add = MagicMock()
        session.flush = AsyncMock()
        sid = uuid.uuid4()
        messages = [{"role": "user", "content": "Voglio un contratto per Acme, 60k in 12 rate"}]

        with patch("api.routes.chat.generate_draft_task") as mock_task:
            draft_id, doc_content, actions = await _execute_draft_action(
                action, sid, None, SimpleNamespace(user_id=str(uuid.uuid4())), session, messages
            )

        assert draft_id is not None
        assert doc_content is None  # nothing inline; the worker fills it
        draft_model = session.add.call_args[0][0]
        assert draft_model.status == "generating"

        mock_task.apply_async.assert_called_once()
        task_args = mock_task.apply_async.call_args[0][0]
        assert task_args[1] == str(sid)        # chat_session_id
        assert task_args[2] == messages         # the brief travels to the worker

        assert actions[0]["action"] == "draft_generating"
        assert actions[0]["payload"]["draft_id"] == str(draft_id)

    @pytest.mark.asyncio
    async def test_non_draft_returns_noop(self):
        out = await _execute_draft_action(
            {"type": "answer_question"},
            uuid.uuid4(), None, SimpleNamespace(user_id=str(uuid.uuid4())), MagicMock(), [],
        )
        assert out == (None, None, [])

# --- _resolve_assistant_action (pure) ---

def test_resolve_structured_action():
    result = {
        "reply": "Ecco la sezione",
        "action": {"type": "create_section", "label": "Aggiungi", "params": {"title": "X"}},
        "sources": [],
    }
    ai_content, action_data, actions = _resolve_assistant_action(result)
    assert ai_content == "Ecco la sezione"
    assert action_data["type"] == "create_section"
    assert actions == [{"action": "create_section", "label": "Aggiungi", "payload": {"title": "X"}}]


def test_resolve_no_action():
    ai_content, action_data, actions = _resolve_assistant_action({"reply": "Solo testo"})
    assert ai_content == "Solo testo"
    assert action_data is None
    assert actions == []


def test_resolve_action_embedded_in_reply_is_stripped():
    reply = 'Certo. {"type":"create_section","params":{"title":"Y"}}'
    ai_content, action_data, actions = _resolve_assistant_action({"reply": reply, "action": None})
    assert action_data is not None
    assert action_data["type"] == "create_section"
    # embedded JSON removed from the visible reply
    assert "{" not in ai_content
    assert actions[0]["action"] == "create_section"


# --- _handle_document_action (DB-backed, mocked) ---

def _doc_model():
    return SimpleNamespace(
        id="11111111-1111-1111-1111-111111111111",
        title="Doc",
        version=1,
        content={"type": "doc", "content": []},
    )


def _user():
    return SimpleNamespace(
        user_id="33333333-3333-3333-3333-333333333333",
    )


@pytest.mark.asyncio
async def test_handle_no_action_or_no_doc():
    res1 = await _handle_document_action(None, _doc_model(), AsyncMock(), _user(), None, "")
    assert res1 == (None, None)
    res2 = await _handle_document_action(
        {"type": "create_section"}, None, AsyncMock(), _user(), None, ""
    )
    assert res2 == (None, None)


@pytest.mark.asyncio
async def test_handle_create_section_writes_and_returns_action():
    doc = _doc_model()
    session = AsyncMock()
    action_data = {"type": "create_section", "params": {"title": "Intro", "content": "Testo"}}

    actions, updated = await _handle_document_action(action_data, doc, session, _user(), None, "")

    assert actions[0]["action"] == "section_created"
    assert "Intro" in actions[0]["label"]
    assert updated is not None
    section = updated["content"][0]
    assert section["type"] == "section"
    assert section["content"][0]["content"][0]["text"] == "Testo"
    assert doc.content == updated  # written back to the model


@pytest.mark.asyncio
async def test_handle_insert_clause_appends_to_section():
    doc = _doc_model()
    doc.content = {"type": "doc", "content": [
        {"type": "section", "attrs": {"sectionId": "sec_1"}, "content": []},
    ]}
    session = AsyncMock()
    action_data = {
        "type": "insert_clause",
        "params": {"section_id": "sec_1", "clause_text": "Clausola"},
    }

    actions, updated = await _handle_document_action(action_data, doc, session, _user(), None, "")

    assert actions[0]["action"] == "clause_inserted"
    clause = updated["content"][0]["content"][0]
    assert clause["type"] == "clause"
    assert clause["content"][0]["content"][0]["text"] == "Clausola"


@pytest.mark.asyncio
async def test_handle_rewrite_section_proposes_patch_not_inline():
    doc = _doc_model()
    session = AsyncMock()
    session.add = MagicMock()  # add() is synchronous
    action_data = {
        "type": "rewrite_section",
        "params": {"section_id": "sec_1", "content": "Nuovo testo"},
    }

    actions, updated = await _handle_document_action(action_data, doc, session, _user(), None, "")

    assert actions[0]["action"] == "patches_proposed"
    assert actions[0]["payload"]["operations"][0]["operation"] == "replace"
    # surgical: nothing written to the document until the user accepts
    assert updated is None


@pytest.mark.asyncio
async def test_handle_create_section_flush_failure_returns_none():
    from sqlalchemy.exc import SQLAlchemyError

    doc = _doc_model()
    session = AsyncMock()
    session.flush.side_effect = SQLAlchemyError("boom")
    action_data = {"type": "create_section", "params": {"title": "X", "content": "Y"}}

    result = await _handle_document_action(action_data, doc, session, _user(), None, "")
    assert result == (None, None)
