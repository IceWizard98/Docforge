from datetime import datetime
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest

from api.routes.chat import _corpus_catalog, _document_outline, _section_title


def _section(sid: str, title: str | None = None, status: str = "draft", heading: str | None = None):
    content = []
    if heading:
        content.append({"type": "heading", "content": [{"type": "text", "text": heading}]})
    attrs = {"sectionId": sid, "status": status}
    if title:
        attrs["title"] = title
    return {"type": "section", "attrs": attrs, "content": content}


def test_document_outline_lists_sections_with_ids():
    content = {"type": "doc", "content": [
        _section("sec_1", title="Introduzione", status="approved"),
        _section("sec_2", heading="Obblighi delle parti"),
    ]}
    outline = _document_outline(content)
    assert "[sec_1]" in outline
    assert "Introduzione" in outline
    assert "approved" in outline
    assert "[sec_2]" in outline
    assert "Obblighi delle parti" in outline  # title from heading fallback


def test_document_outline_empty_for_no_sections():
    assert _document_outline({"type": "doc", "content": []}) == ""
    assert _document_outline(None) == ""


def test_section_title_prefers_attrs_then_heading():
    assert _section_title(_section("s", title="T", heading="H")) == "T"
    assert _section_title(_section("s", heading="H")) == "H"
    assert _section_title(_section("s")) == "(senza titolo)"


@pytest.mark.asyncio
async def test_corpus_catalog_formats_sources():
    src = SimpleNamespace(
        filename="nda_acme.pdf", doc_type="contract", language="it",
        tags=["nda", "acme"], created_at=datetime(2026, 1, 15),
    )
    result = MagicMock()
    result.scalars.return_value.all.return_value = [src]
    session = AsyncMock()
    session.execute = AsyncMock(return_value=result)

    catalog = await _corpus_catalog(session)
    assert "nda_acme.pdf" in catalog
    assert "contract" in catalog
    assert "nda, acme" in catalog
    assert "2026-01-15" in catalog


@pytest.mark.asyncio
async def test_corpus_catalog_empty_when_no_sources():
    result = MagicMock()
    result.scalars.return_value.all.return_value = []
    session = AsyncMock()
    session.execute = AsyncMock(return_value=result)
    assert await _corpus_catalog(session) == ""
