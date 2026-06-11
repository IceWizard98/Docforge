from core.events import PatchGenerated


async def generate_patch_task(document_id: str, instructions: str) -> PatchGenerated:
    return PatchGenerated(
        patch_set_id=f"ps_{document_id[:8]}",
        document_id=document_id,
    )


async def validate_patch_task(patch_set: dict, document: dict) -> list[dict]:
    return []
