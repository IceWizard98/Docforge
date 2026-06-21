from core.models.document import Document, DocumentStatus, OutlineEntry, SectionStatus


class TestDocument:
    def test_create_document_has_id(self):
        doc = Document(title="Test Contract")
        assert doc.doc_id.startswith("d_")
        assert doc.title == "Test Contract"

    def test_document_default_status_is_draft(self):
        doc = Document()
        assert doc.status == DocumentStatus.DRAFT

    def test_document_with_outline(self):
        outline = [
            OutlineEntry(section_id="sec_1", number="1", title="Premesse"),
            OutlineEntry(
                section_id="sec_2", number="2", title="Oggetto", status=SectionStatus.PENDING
            ),
        ]
        doc = Document(title="Contract", outline=outline)
        assert len(doc.outline) == 2
        assert doc.outline[0].section_id == "sec_1"
        assert doc.outline[1].status == SectionStatus.PENDING


class TestUser:
    def test_user_default_role_is_editor(self):
        from core.models.user import User, UserRole
        u = User(email="test@acme.com")
        assert u.role == UserRole.EDITOR
