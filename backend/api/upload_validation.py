"""Shared upload validation for the file-upload routes.

Sources, documents and templates all gate an incoming ``UploadFile`` the same
way (filename present, allowed extension, non-empty, within the size cap). This
is the single copy so a policy change — a new size cap, MIME sniffing, an added
extension — lands everywhere at once instead of drifting between three routes.
"""

from pathlib import Path

from fastapi import HTTPException, UploadFile, status

MAX_UPLOAD_SIZE = 50 * 1024 * 1024  # 50 MB


async def read_validated_upload(
    file: UploadFile,
    allowed_extensions: set[str],
    *,
    bad_request_status: int = status.HTTP_400_BAD_REQUEST,
) -> tuple[str, bytes]:
    """Validate and read an upload; return ``(lowercased ext, bytes)``.

    ``bad_request_status`` picks the status for a missing filename / disallowed
    extension (routes use 400, templates uses 422). Empty-file (400) and
    oversize (413) are uniform across callers.
    """
    if not file.filename:
        raise HTTPException(status_code=bad_request_status, detail="Nome file mancante")

    ext = Path(file.filename).suffix.lower()
    if ext not in allowed_extensions:
        raise HTTPException(
            status_code=bad_request_status,
            detail=f"Tipo file non supportato: '{ext}'",
        )

    data = await file.read()
    if len(data) == 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="Cannot upload empty file"
        )
    if len(data) > MAX_UPLOAD_SIZE:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail="File exceeds 50 MB limit",
        )
    return ext, data
