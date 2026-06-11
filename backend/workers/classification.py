from core.events import DocumentClassified


async def classify_document(document_id: str) -> DocumentClassified:
    return DocumentClassified(
        document_id=document_id,
    )
