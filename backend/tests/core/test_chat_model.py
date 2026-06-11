import re
from datetime import UTC, datetime

from core.models.chat import (
    ChatActionPayload,
    ChatContextType,
    ChatMessage,
    ChatSession,
    PatchPayload,
    SourceCitation,
)


def _is_uuid_hex(s: str, prefix: str) -> bool:
    return bool(re.match(rf"^{prefix}[a-f0-9]{{8}}$", s))


class TestChatContextType:
    def test_enum_values(self):
        assert ChatContextType.CREATE_NEW.value == "create_new"
        assert ChatContextType.UPDATE_EXISTING.value == "update_existing"
        assert ChatContextType.QA.value == "qa"


class TestChatActionPayload:
    def test_all_fields(self):
        payload = ChatActionPayload(
            action="navigate",
            target={"section_id": "sec_1"},
            payload={"offset": 42},
            label="Go to section",
            icon="arrow-right",
        )
        assert payload.action == "navigate"
        assert payload.target == {"section_id": "sec_1"}
        assert payload.payload == {"offset": 42}
        assert payload.label == "Go to section"
        assert payload.icon == "arrow-right"

    def test_minimal_fields(self):
        payload = ChatActionPayload(
            action="insert",
            target={},
            payload={},
        )
        assert payload.label == ""
        assert payload.icon is None

    def test_different_actions(self):
        for action in ("navigate", "insert", "replace", "delete", "highlight"):
            payload = ChatActionPayload(action=action, target={}, payload={})
            assert payload.action == action


class TestSourceCitation:
    def test_minimal(self):
        src = SourceCitation(doc_id="doc_1")
        assert src.doc_id == "doc_1"
        assert src.chunk_id is None
        assert src.snippet is None
        assert src.confidence == 0.0

    def test_all_fields(self):
        src = SourceCitation(
            doc_id="doc_1",
            chunk_id="chk_42",
            snippet="relevant text",
            confidence=0.95,
        )
        assert src.chunk_id == "chk_42"
        assert src.snippet == "relevant text"
        assert src.confidence == 0.95

    def test_confidence_range(self):
        src1 = SourceCitation(doc_id="d", confidence=-0.1)
        src2 = SourceCitation(doc_id="d", confidence=1.5)
        assert src1.confidence == -0.1
        assert src2.confidence == 1.5

    def test_snippet_none(self):
        src = SourceCitation(doc_id="d", snippet=None)
        assert src.snippet is None


class TestPatchPayload:
    def test_all_fields(self):
        ops = [{"operation": "insert", "content": {}}]
        patch = PatchPayload(patch_set_id="ps_1", operations=ops, summary="Insert section")
        assert patch.patch_set_id == "ps_1"
        assert patch.operations == ops
        assert patch.summary == "Insert section"

    def test_empty_operations(self):
        patch = PatchPayload(patch_set_id="ps_1", operations=[], summary="")
        assert patch.operations == []


class TestChatMessage:
    def test_default_creation(self):
        msg = ChatMessage()
        assert _is_uuid_hex(msg.id, "msg_")
        assert msg.role == "user"
        assert msg.content == ""
        assert msg.actions == []
        assert msg.patches == []
        assert msg.sources == []
        assert msg.validation == []
        assert msg.edit_context is None
        assert isinstance(msg.created_at, datetime)
        assert msg.created_at.tzinfo is UTC

    def test_with_all_fields(self):
        actions = [ChatActionPayload(action="insert", target={}, payload={})]
        patches = [PatchPayload(patch_set_id="ps_1", operations=[], summary="")]
        sources = [SourceCitation(doc_id="doc_1")]
        msg = ChatMessage(
            session_id="chat_1",
            role="assistant",
            content="Here is the draft",
            actions=actions,
            patches=patches,
            sources=sources,
            validation=[{"key": "val"}],
            edit_context={"section": "sec_1"},
        )
        assert msg.session_id == "chat_1"
        assert msg.role == "assistant"
        assert msg.content == "Here is the draft"
        assert len(msg.actions) == 1
        assert len(msg.patches) == 1
        assert len(msg.sources) == 1
        assert msg.validation == [{"key": "val"}]
        assert msg.edit_context == {"section": "sec_1"}

    def test_unique_ids(self):
        msg1 = ChatMessage()
        msg2 = ChatMessage()
        assert msg1.id != msg2.id

    def test_different_roles(self):
        for role in ("user", "assistant", "system"):
            msg = ChatMessage(role=role)
            assert msg.role == role


class TestChatSession:
    def test_default_creation(self):
        session = ChatSession()
        assert _is_uuid_hex(session.id, "chat_")
        assert session.status == "active"
        assert session.context_type == ChatContextType.CREATE_NEW
        assert session.document_id is None
        assert session.spec is None
        assert isinstance(session.created_at, datetime)

    def test_with_all_fields(self):
        session = ChatSession(
            tenant_id="t_1",
            document_id="doc_1",
            user_id="u_1",
            title="Contract Review",
            context_type=ChatContextType.QA,
            status="archived",
            spec={"sections": []},
        )
        assert session.tenant_id == "t_1"
        assert session.document_id == "doc_1"
        assert session.user_id == "u_1"
        assert session.title == "Contract Review"
        assert session.context_type == ChatContextType.QA
        assert session.status == "archived"
        assert session.spec == {"sections": []}

    def test_status_values(self):
        for status in ("active", "archived", "completed"):
            session = ChatSession(status=status)
            assert session.status == status

    def test_unique_ids(self):
        s1 = ChatSession()
        s2 = ChatSession()
        assert s1.id != s2.id
