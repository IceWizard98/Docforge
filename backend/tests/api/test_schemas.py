import pytest
from pydantic import ValidationError

from api.schemas.auth import ForgotPasswordRequest, LoginRequest, RegisterRequest
from api.schemas.chat import ChatMessageRequest, ChatSessionCreate, EditContext
from api.schemas.document import DocumentCreate
from api.schemas.exports import ExportCreate


class TestLoginRequest:
    def test_valid_input(self):
        data = LoginRequest(email="user@example.com", password="securepass123")
        assert data.email == "user@example.com"
        assert data.password == "securepass123"

    def test_invalid_email_raises(self):
        with pytest.raises(ValidationError, match="email"):
            LoginRequest(email="not-an-email", password="securepass123")

    def test_short_password_raises(self):
        with pytest.raises(ValidationError, match="password"):
            LoginRequest(email="user@example.com", password="short")

    def test_short_password_boundary(self):
        with pytest.raises(ValidationError):
            LoginRequest(email="user@example.com", password="1234567")

    def test_min_length_password_ok(self):
        data = LoginRequest(email="user@example.com", password="12345678")
        assert data.password == "12345678"

    def test_empty_payload_raises(self):
        with pytest.raises(ValidationError):
            LoginRequest()

    def test_optional_tenant_slug(self):
        data = LoginRequest(
            email="user@example.com", password="securepass123", tenant_slug="my-tenant"
        )
        assert data.tenant_slug == "my-tenant"

    def test_tenant_slug_omitted(self):
        data = LoginRequest(email="user@example.com", password="securepass123")
        assert data.tenant_slug is None


class TestRegisterRequest:
    def test_valid_input(self):
        data = RegisterRequest(
            email="test@example.com",
            password="securepass123",
            display_name="Test User",
            tenant_slug="test-tenant",
        )
        assert data.display_name == "Test User"

    def test_missing_display_name_raises(self):
        with pytest.raises(ValidationError, match="display_name"):
            RegisterRequest(
                email="test@example.com",
                password="securepass123",
                tenant_slug="test-tenant",
            )

    def test_invalid_email_raises(self):
        with pytest.raises(ValidationError, match="email"):
            RegisterRequest(
                email="bad-email",
                password="securepass123",
                display_name="User",
                tenant_slug="test",
            )

    def test_short_password_raises(self):
        with pytest.raises(ValidationError):
            RegisterRequest(
                email="test@example.com",
                password="short",
                display_name="User",
                tenant_slug="test",
            )


class TestForgotPasswordRequest:
    def test_valid_email(self):
        data = ForgotPasswordRequest(email="user@example.com")
        assert data.email == "user@example.com"

    def test_invalid_email_raises(self):
        with pytest.raises(ValidationError):
            ForgotPasswordRequest(email="bad")


class TestDocumentCreate:
    def test_valid_input(self):
        data = DocumentCreate(title="My Document")
        assert data.title == "My Document"
        assert data.doc_type == ""

    def test_empty_title_raises(self):
        with pytest.raises(ValidationError, match="title"):
            DocumentCreate(title="")

    def test_title_too_long_raises(self):
        with pytest.raises(ValidationError):
            DocumentCreate(title="x" * 501)

    def test_max_length_title_ok(self):
        data = DocumentCreate(title="x" * 500)
        assert len(data.title) == 500

    def test_with_doc_type(self):
        data = DocumentCreate(title="Test", doc_type="contract")
        assert data.doc_type == "contract"


class TestChatSessionCreate:
    def test_valid_input(self):
        data = ChatSessionCreate(title="New Chat")
        assert data.context_type == "create_new"

    def test_invalid_context_type_raises(self):
        with pytest.raises(ValidationError):
            ChatSessionCreate(context_type="invalid_type")

    def test_edit_existing_context(self):
        data = ChatSessionCreate(context_type="edit_existing")
        assert data.context_type == "edit_existing"

    def test_review_context(self):
        data = ChatSessionCreate(context_type="review")
        assert data.context_type == "review"

    def test_create_new_context(self):
        data = ChatSessionCreate(context_type="create_new")
        assert data.context_type == "create_new"

    def test_with_document_id(self):
        data = ChatSessionCreate(document_id="doc_123")
        assert data.document_id == "doc_123"


class TestChatMessageRequest:
    def test_valid_input(self):
        data = ChatMessageRequest(content="Hello")
        assert data.content == "Hello"

    def test_with_edit_context(self):
        ctx = EditContext(document_id="doc_1", section_id="sec_1", selected_text="foo")
        data = ChatMessageRequest(content="Hello", edit_context=ctx)
        assert data.edit_context.document_id == "doc_1"
        assert data.edit_context.section_id == "sec_1"
        assert data.edit_context.selected_text == "foo"

    def test_edit_context_defaults(self):
        ctx = EditContext()
        assert ctx.document_id is None
        assert ctx.section_id is None
        assert ctx.selected_text is None


class TestExportCreate:
    def test_default_format_is_pdf(self):
        data = ExportCreate()
        assert data.format == "pdf"

    def test_docx_format(self):
        data = ExportCreate(format="docx")
        assert data.format == "docx"

    def test_invalid_format_raises(self):
        with pytest.raises(ValidationError):
            ExportCreate(format="html")
