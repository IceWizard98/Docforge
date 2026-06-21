from unittest.mock import AsyncMock

import pytest

from core.services.context import ContextPackService
from core.services.search import SearchResult


@pytest.mark.asyncio
async def test_build_section_context_returns_empty_without_search():
    svc = ContextPackService(embedding_fn=AsyncMock(return_value=[0.0] * 8))
    pack = await svc.build_section_context(section_title="Intro")
    assert pack.sources == []


@pytest.mark.asyncio
async def test_build_section_context_calls_search():
    search = AsyncMock()
    search.hybrid_search = AsyncMock(return_value=[])
    svc = ContextPackService(
        search_service=search,
        embedding_fn=AsyncMock(return_value=[0.1] * 8),
    )

    await svc.build_section_context(section_title="Privacy clause")

    assert search.hybrid_search.await_count == 1


@pytest.mark.asyncio
async def test_build_section_context_groups_results_into_sources():
    search = AsyncMock()
    search.hybrid_search = AsyncMock(
        return_value=[
            SearchResult(chunk_id="c1", content="alpha", doc_id="d1", section_id=None, score=0.9),
            SearchResult(chunk_id="c2", content="beta", doc_id="d1", section_id=None, score=0.8),
        ]
    )
    svc = ContextPackService(
        search_service=search,
        embedding_fn=AsyncMock(return_value=[0.1] * 8),
    )

    pack = await svc.build_section_context(section_title="X")
    assert len(pack.sources) == 1
    assert pack.sources[0].doc_id == "d1"
    assert len(pack.sources[0].chunks) == 2
    prompt = svc.build_prompt_context(pack)
    assert "alpha" in prompt and "beta" in prompt
