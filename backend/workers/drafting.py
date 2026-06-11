from core.events import DraftGenerated, SectionGenerated


async def generate_draft(spec: dict, document_id: str | None = None) -> DraftGenerated:
    draft_id = spec.get("draft_id", "")
    return DraftGenerated(
        draft_id=draft_id,
        document_id=document_id,
    )


async def generate_section(
    draft_id: str, section_id: str, spec: dict, context_pack: dict
) -> SectionGenerated:
    return SectionGenerated(
        draft_id=draft_id,
        section_id=section_id,
    )
