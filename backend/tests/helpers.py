import uuid
from datetime import UTC, datetime
from unittest.mock import MagicMock


def build_mock_document(overrides=None):
    now = datetime.now(UTC)
    doc = MagicMock()
    doc.id = uuid.uuid4()
    doc.title = "Test Document"
    doc.doc_type = "contract"
    doc.status = "draft"
    doc.language = "en"
    doc.version = 1
    doc.content = {}
    doc.outline = []
    doc.created_by = uuid.uuid4()
    doc.created_at = now
    doc.updated_at = now
    if overrides:
        for k, v in overrides.items():
            setattr(doc, k, v)
    return doc
