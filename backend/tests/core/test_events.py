import re
from datetime import UTC, datetime

from core.events import (
    DocumentApproved,
    DocumentClassified,
    DocumentIndexed,
    DocumentParsed,
    DomainEvent,
    DraftGenerated,
    ExportCompleted,
    PatchApplied,
    SectionGenerated,
    SpecGenerated,
)


def _assert_event_fields(evt, cls):
    assert isinstance(evt.event_id, str)
    assert evt.event_id.startswith("evt_")
    assert len(evt.event_id) > 4
    assert isinstance(evt.timestamp, datetime)
    assert evt.timestamp.tzinfo is not None
    assert isinstance(evt, DomainEvent)
    assert isinstance(evt, cls)


class TestDomainEvent:
    def test_event_id_format(self):
        evt = DomainEvent()
        assert re.match(r"^evt_[a-f0-9]{8}$", evt.event_id)

    def test_timestamp_utc(self):
        evt = DomainEvent()
        assert evt.timestamp.tzinfo is UTC

    def test_default_creation(self):
        evt = DomainEvent()
        assert evt.event_id is not None
        assert evt.timestamp is not None

    def test_unique_event_ids(self):
        evt1 = DomainEvent()
        evt2 = DomainEvent()
        assert evt1.event_id != evt2.event_id


class TestDocumentParsed:
    def test_default_values(self):
        evt = DocumentParsed()
        _assert_event_fields(evt, DocumentParsed)
        assert evt.document_id == ""

    def test_with_document_id(self):
        evt = DocumentParsed(document_id="doc_123")
        assert evt.document_id == "doc_123"


class TestDocumentClassified:
    def test_default_values(self):
        evt = DocumentClassified()
        _assert_event_fields(evt, DocumentClassified)
        assert evt.doc_type == ""
        assert evt.language == ""
        assert evt.tags == []
        assert evt.jurisdiction == ""
        assert evt.parties == []
        assert evt.classification_confidence == 0.0

    def test_with_tags(self):
        evt = DocumentClassified(
            document_id="doc_1",
            doc_type="contract",
            language="en",
            tags=["legal", "nda"],
            jurisdiction="US",
            parties=["Acme Corp", "Beta Inc"],
            classification_confidence=0.85,
        )
        assert evt.tags == ["legal", "nda"]
        assert evt.doc_type == "contract"
        assert evt.language == "en"
        assert evt.jurisdiction == "US"
        assert evt.parties == ["Acme Corp", "Beta Inc"]
        assert evt.classification_confidence == 0.85


class TestDocumentIndexed:
    def test_default_values(self):
        evt = DocumentIndexed()
        _assert_event_fields(evt, DocumentIndexed)
        assert evt.chunk_count == 0

    def test_with_chunk_count(self):
        evt = DocumentIndexed(document_id="doc_1", chunk_count=15)
        assert evt.chunk_count == 15


class TestSpecGenerated:
    def test_default_values(self):
        evt = SpecGenerated()
        _assert_event_fields(evt, SpecGenerated)
        assert evt.session_id == ""

    def test_with_session_id(self):
        evt = SpecGenerated(session_id="chat_abc")
        assert evt.session_id == "chat_abc"


class TestDraftGenerated:
    def test_default_values(self):
        evt = DraftGenerated()
        _assert_event_fields(evt, DraftGenerated)
        assert evt.draft_id == ""

    def test_with_document(self):
        evt = DraftGenerated(draft_id="draft_1", document_id="doc_1")
        assert evt.draft_id == "draft_1"
        assert evt.document_id == "doc_1"


class TestSectionGenerated:
    def test_default_values(self):
        evt = SectionGenerated()
        _assert_event_fields(evt, SectionGenerated)
        assert evt.section_id == ""

    def test_with_ids(self):
        evt = SectionGenerated(draft_id="draft_1", section_id="sec_1")
        assert evt.draft_id == "draft_1"
        assert evt.section_id == "sec_1"


class TestPatchApplied:
    def test_default_values(self):
        evt = PatchApplied()
        _assert_event_fields(evt, PatchApplied)
        assert evt.new_version == 0

    def test_with_values(self):
        evt = PatchApplied(document_id="doc_1", new_version=3, patch_set_id="ps_1")
        assert evt.document_id == "doc_1"
        assert evt.new_version == 3
        assert evt.patch_set_id == "ps_1"




class TestDocumentApproved:
    def test_default_values(self):
        evt = DocumentApproved()
        _assert_event_fields(evt, DocumentApproved)
        assert evt.approved_by == ""

    def test_with_approver(self):
        evt = DocumentApproved(
            document_id="doc_1",
            version_number=2,
            approved_by="user_42",
        )
        assert evt.approved_by == "user_42"
        assert evt.version_number == 2


class TestExportCompleted:
    def test_default_values(self):
        evt = ExportCompleted()
        _assert_event_fields(evt, ExportCompleted)
        assert evt.format == ""
        assert evt.file_key == ""

    def test_with_values(self):
        evt = ExportCompleted(
            job_id="job_1",
            document_id="doc_1",
            format="pdf",
            file_key="exports/doc_1.pdf",
        )
        assert evt.format == "pdf"
        assert evt.file_key == "exports/doc_1.pdf"
