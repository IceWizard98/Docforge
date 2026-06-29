import uuid

from sqlalchemy import (
    JSON,
    Boolean,
    Column,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.sql import func

from adapters.postgresql.base import Base


class UserModel(Base):
    __tablename__ = "users"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    email = Column(String(255), nullable=False)
    display_name = Column(String(255))
    role = Column(String(32), nullable=False, default="editor")
    password_hash = Column(String(255), nullable=False)
    email_verified = Column(Boolean, nullable=False, default=False)
    settings = Column(JSON, nullable=False, default=dict)
    last_login_at = Column(DateTime(timezone=True))
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )

    __table_args__ = (
        UniqueConstraint("email", name="uq_user_email"),
    )


class DocumentModel(Base):
    __tablename__ = "documents"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    title = Column(String(500), nullable=False)
    doc_type = Column(String(64), nullable=False, default="")
    status = Column(String(32), nullable=False, default="draft")
    language = Column(String(8), nullable=False, default="it")
    version = Column(Integer, nullable=False, default=1)
    content = Column(JSON, nullable=False, default=dict)
    outline = Column(JSON, nullable=False, default=list)
    tags = Column(JSON, nullable=False, default=list)
    created_by = Column(UUID(as_uuid=True), nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )


class SourceDocumentModel(Base):
    __tablename__ = "source_documents"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    document_id = Column(UUID(as_uuid=True), ForeignKey("documents.id"), nullable=True)
    created_by = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True)
    filename = Column(String(500), nullable=False)
    doc_type = Column(String(64), nullable=False, default="")
    language = Column(String(8), nullable=True)
    jurisdiction = Column(String(64), nullable=True)
    tags = Column(JSON, nullable=True)
    parties = Column(JSON, nullable=True)
    classification_confidence = Column(Float, nullable=True)
    file_key = Column(String(500), nullable=False)
    status = Column(String(32), nullable=False, default="uploaded")
    parsed_content = Column(JSON, nullable=True)
    parsed_text = Column(Text, nullable=True)
    doc_metadata = Column("metadata", JSON, nullable=False, default=dict)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class DocumentChunkModel(Base):
    __tablename__ = "document_chunks"

    id = Column(String(64), primary_key=True)
    document_id = Column(
        UUID(as_uuid=True), ForeignKey("documents.id"), nullable=True, index=True
    )
    source_document_id = Column(
        UUID(as_uuid=True), ForeignKey("source_documents.id"), nullable=True
    )
    section_id = Column(String(64), nullable=True)
    chunk_index = Column(Integer, nullable=False, default=0)
    text_content = Column(Text, nullable=False)
    token_count = Column(Integer, nullable=False, default=0)
    chunk_metadata = Column("metadata", JSON, nullable=False, default=dict)
    embedding = Column(Text, nullable=True)
    tsv_content = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class ChatSessionModel(Base):
    __tablename__ = "chat_sessions"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    document_id = Column(UUID(as_uuid=True), ForeignKey("documents.id"), nullable=True)
    user_id = Column(UUID(as_uuid=True), nullable=False)
    title = Column(String(500), nullable=False, default="New Chat")
    context_type = Column(String(32), nullable=False, default="create_new")
    status = Column(String(32), nullable=False, default="active")
    spec = Column(JSON, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )


class ChatMessageModel(Base):
    __tablename__ = "chat_messages"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    session_id = Column(
        UUID(as_uuid=True), ForeignKey("chat_sessions.id"), nullable=False, index=True
    )
    role = Column(String(32), nullable=False)
    content = Column(Text, nullable=False, default="")
    actions = Column(JSON, nullable=False, default=list)
    patches = Column(JSON, nullable=False, default=list)
    sources = Column(JSON, nullable=False, default=list)
    source_refs = Column(JSON, nullable=False, default=list)
    action_type = Column(String(32), nullable=True)
    validation = Column(JSON, nullable=False, default=list)
    # Transparency: one-line "what I understood" + per-slot filled/missing status.
    intent_summary = Column(Text, nullable=True)
    slot_status = Column(JSON, nullable=False, default=list)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class CommentModel(Base):
    __tablename__ = "comments"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    document_id = Column(UUID(as_uuid=True), ForeignKey("documents.id"), nullable=False, index=True)
    section_id = Column(String(64), nullable=True)
    clause_id = Column(String(64), nullable=True)
    thread_id = Column(UUID(as_uuid=True), nullable=True)
    author = Column(String(255), nullable=False)
    content = Column(Text, nullable=False)
    resolved = Column(Boolean, nullable=False, default=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class PatchSetModel(Base):
    __tablename__ = "patch_sets"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    document_id = Column(UUID(as_uuid=True), ForeignKey("documents.id"), nullable=False, index=True)
    chat_message_id = Column(UUID(as_uuid=True), nullable=True)
    version_from = Column(Integer, nullable=False, default=0)
    version_to = Column(Integer, nullable=True)
    status = Column(String(32), nullable=False, default="proposed")
    summary = Column(String(500), nullable=False, default="")
    operations = Column(JSON, nullable=False, default=list)
    created_by = Column(UUID(as_uuid=True), nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )


class TemplateModel(Base):
    __tablename__ = "templates"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name = Column(String(255), nullable=False)
    description = Column(Text, nullable=True)
    doc_type = Column(String(50), nullable=True)
    content = Column(JSONB, nullable=False)
    category = Column(String(100), nullable=True)
    is_public = Column(Boolean, default=False, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )


class AuditEventModel(Base):
    __tablename__ = "audit_events"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), nullable=False)
    event_type = Column(String(64), nullable=False)
    entity_type = Column(String(64), nullable=False)
    entity_id = Column(String(64), nullable=False)
    payload = Column(JSON, nullable=False, default=dict)
    ip_address = Column(String(45), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class DraftModel(Base):
    __tablename__ = "drafts"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    document_id = Column(UUID(as_uuid=True), ForeignKey("documents.id"), nullable=True)
    chat_session_id = Column(UUID(as_uuid=True), ForeignKey("chat_sessions.id"), nullable=False)
    title = Column(String(500), nullable=False)
    spec = Column(JSON, nullable=False, default=dict)
    content = Column(JSON, nullable=False, default=dict)
    status = Column(String(32), nullable=False, default="generating")
    progress = Column(JSON, nullable=False, default=dict)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )


class DocumentVersionModel(Base):
    __tablename__ = "document_versions"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    document_id = Column(
        UUID(as_uuid=True), ForeignKey("documents.id"), nullable=False, index=True
    )
    version = Column(Integer, nullable=False)
    content = Column(JSON, nullable=False, default=dict)
    outline = Column(JSON, nullable=False, default=list)
    created_by = Column(UUID(as_uuid=True), nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    __table_args__ = (
        UniqueConstraint("document_id", "version", name="uq_doc_version"),
    )


class CitationModel(Base):
    __tablename__ = "citations"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    chat_message_id = Column(UUID(as_uuid=True), ForeignKey("chat_messages.id"), nullable=True)
    patch_set_id = Column(UUID(as_uuid=True), ForeignKey("patch_sets.id"), nullable=True)
    chunk_id = Column(String(64), ForeignKey("document_chunks.id"), nullable=True)
    source_doc_id = Column(UUID(as_uuid=True), ForeignKey("source_documents.id"), nullable=True)
    confidence = Column(Float, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class ProvenanceLinkModel(Base):
    __tablename__ = "provenance_links"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    document_id = Column(UUID(as_uuid=True), ForeignKey("documents.id"), nullable=False)
    source_doc_id = Column(UUID(as_uuid=True), ForeignKey("source_documents.id"), nullable=False)
    section_id = Column(String(64), nullable=True)
    chunk_id = Column(String(64), nullable=True)
    confidence = Column(Float, nullable=True)
    version_number = Column(Integer, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
