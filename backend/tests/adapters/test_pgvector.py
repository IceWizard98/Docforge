from unittest.mock import AsyncMock, MagicMock

import pytest


def test_owner_filter_scopes_by_created_by():
    # Corpus isolation: owner_id must add a created_by predicate so a user's
    # retrieval can never return another user's source chunks.
    from adapters.postgresql.pgvector import PgvectorAdapter
    from core.services.search import RetrievalFilters

    adapter = PgvectorAdapter(MagicMock())
    clause, params = adapter._build_filter_clauses(RetrievalFilters(owner_id="11111111-1111-1111-1111-111111111111"))
    assert "sd.created_by" in clause
    assert params["owner_id"] == "11111111-1111-1111-1111-111111111111"

    # Without owner_id, no created_by scoping is added.
    clause2, _ = adapter._build_filter_clauses(RetrievalFilters())
    assert "created_by" not in clause2


def test_excluded_source_ids_adds_null_safe_not_in_clause():
    # Per-document exclusion: excluded ids must drop those source chunks while the
    # IS NULL guard keeps provenance-less chunks (NULL NOT IN (...) is NULL -> drops).
    from adapters.postgresql.pgvector import PgvectorAdapter
    from core.services.search import RetrievalFilters

    adapter = PgvectorAdapter(MagicMock())
    ex = ["11111111-1111-1111-1111-111111111111", "22222222-2222-2222-2222-222222222222"]
    clause, params = adapter._build_filter_clauses(
        RetrievalFilters(excluded_source_ids=ex)
    )
    assert "dc.source_document_id IS NULL OR dc.source_document_id NOT IN" in clause
    assert "CAST(:ex_0 AS uuid)" in clause
    assert "CAST(:ex_1 AS uuid)" in clause
    assert params["ex_0"] == ex[0]
    assert params["ex_1"] == ex[1]


def test_excluded_source_ids_combines_with_owner_id():
    from adapters.postgresql.pgvector import PgvectorAdapter
    from core.services.search import RetrievalFilters

    adapter = PgvectorAdapter(MagicMock())
    clause, params = adapter._build_filter_clauses(
        RetrievalFilters(
            owner_id="33333333-3333-3333-3333-333333333333",
            excluded_source_ids=["44444444-4444-4444-4444-444444444444"],
        )
    )
    assert "sd.created_by" in clause
    assert "NOT IN" in clause
    assert params["owner_id"] == "33333333-3333-3333-3333-333333333333"
    assert params["ex_0"] == "44444444-4444-4444-4444-444444444444"


def test_excluded_source_ids_empty_is_noop():
    from adapters.postgresql.pgvector import PgvectorAdapter
    from core.services.search import RetrievalFilters

    adapter = PgvectorAdapter(MagicMock())
    clause, params = adapter._build_filter_clauses(RetrievalFilters(excluded_source_ids=[]))
    assert "NOT IN" not in clause
    assert not any(k.startswith("ex_") for k in params)


@pytest.mark.asyncio
async def test_create_extension():
    mock_session = AsyncMock()
    mock_session.execute = AsyncMock()
    mock_session.flush = AsyncMock()

    from adapters.postgresql.pgvector import PgvectorAdapter

    adapter = PgvectorAdapter(mock_session)
    await adapter.create_extension()
    mock_session.execute.assert_called_once()
    mock_session.flush.assert_called_once()


@pytest.mark.asyncio
async def test_store_embeddings():
    mock_session = AsyncMock()
    mock_session.execute = AsyncMock()
    mock_session.flush = AsyncMock()

    from adapters.postgresql.pgvector import PgvectorAdapter

    adapter = PgvectorAdapter(mock_session)
    chunks = [{
        "id": "chk_1", "document_id": "doc_1",
        "text": "hello", "token_count": 1, "metadata": {},
    }]
    embeddings = [[0.1, 0.2, 0.3]]
    await adapter.store_embeddings(chunks, embeddings)
    mock_session.execute.assert_called_once()
    mock_session.flush.assert_called_once()


@pytest.mark.asyncio
async def test_search_similar():
    mock_session = AsyncMock()
    mock_result = MagicMock()
    mock_result.all.return_value = []
    mock_session.execute = AsyncMock(return_value=mock_result)

    from adapters.postgresql.pgvector import PgvectorAdapter

    adapter = PgvectorAdapter(mock_session)
    results = await adapter.search_similar([0.1, 0.2, 0.3], limit=5)
    assert results == []


@pytest.mark.asyncio
async def test_store_embeddings_binds_document_id():
    mock_session = AsyncMock()
    mock_session.execute = AsyncMock()
    mock_session.flush = AsyncMock()

    from adapters.postgresql.pgvector import PgvectorAdapter

    adapter = PgvectorAdapter(mock_session)
    chunks = [{
        "id": "chk_1", "document_id": None,
        "source_document_id": "src_1", "text": "hello", "token_count": 1, "metadata": {},
    }]
    await adapter.store_embeddings(chunks, [[0.1, 0.2, 0.3]])
    params = mock_session.execute.call_args[0][1]
    assert params["document_id"] is None
    assert params["source_document_id"] == "src_1"
    sql = str(mock_session.execute.call_args[0][0])
    assert "tenant_id" not in sql


@pytest.mark.asyncio
async def test_delete_document_embeddings():
    mock_session = AsyncMock()
    mock_session.execute = AsyncMock()
    mock_session.flush = AsyncMock()

    from adapters.postgresql.pgvector import PgvectorAdapter

    adapter = PgvectorAdapter(mock_session)
    await adapter.delete_document_embeddings("doc_1")
    mock_session.execute.assert_called_once()
    mock_session.flush.assert_called_once()
