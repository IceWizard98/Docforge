"""A classification failure must leave the source on a terminal 'failed' status.

Otherwise the source stays 'uploaded' forever -> UI shows "In coda" and the
4s polling never stops. We force the LLM provider to raise and assert the source
row is flipped to 'failed'.
"""

import uuid
from unittest.mock import AsyncMock, MagicMock, patch

from workers.classification import classify_document_task


@patch("workers.classification.get_llm_provider")
@patch("workers.classification.worker_session")
def test_classify_marks_source_failed_on_provider_error(mock_worker_session, mock_get_llm):
    source = MagicMock()
    source.parsed_content = None
    source.parsed_text = "some text"
    source.status = "uploaded"

    session = AsyncMock()
    exec_result = MagicMock()
    exec_result.scalar_one_or_none.return_value = source
    session.execute.return_value = exec_result

    cm = AsyncMock()
    cm.__aenter__.return_value = session
    cm.__aexit__.return_value = False
    mock_worker_session.return_value = cm

    # Classification blows up partway through.
    mock_get_llm.side_effect = RuntimeError("LLM provider unavailable")

    classify_document_task(str(uuid.uuid4()), None)

    assert source.status == "failed", "source must be marked failed when classification errors"
    session.commit.assert_awaited()
