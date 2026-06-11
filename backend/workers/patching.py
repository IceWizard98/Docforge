import asyncio
import logging

from adapters.llm.factory import get_llm_provider
from core.events import PatchGenerated
from core.services.patching import PatchService
from workers.celery_app import celery_app

logger = logging.getLogger(__name__)


@celery_app.task
def generate_patch_task(document_id: str, document: dict, instructions: str) -> PatchGenerated:
    try:
        provider = get_llm_provider()
        service = PatchService(llm=provider)
        plan = asyncio.run(
            service.generate_patch_plan(document, instructions, llm=provider)
        )
        return PatchGenerated(
            patch_set_id=plan.get("id", f"ps_{document_id[:8]}"),
            document_id=document_id,
        )
    except Exception as e:
        logger.error("Patch generation failed for %s: %s", document_id, e)
        return PatchGenerated(patch_set_id=f"ps_{document_id[:8]}", document_id=document_id)


@celery_app.task
def validate_patch_task(patch_set: dict, document: dict) -> list[dict]:
    try:
        service = PatchService()
        return asyncio.run(service.validate_patch(patch_set, document))
    except Exception as e:
        logger.error("Patch validation failed: %s", e)
        return []
