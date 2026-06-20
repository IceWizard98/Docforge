from unittest.mock import AsyncMock, MagicMock

import pytest


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
