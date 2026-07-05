import subprocess
import tempfile
from pathlib import Path


def docx_to_pdf(docx_bytes: bytes) -> bytes:
    """Convert a DOCX to PDF via headless LibreOffice, preserving template
    styling/fonts/headers that WeasyPrint's HTML path cannot reproduce.

    A per-call `UserInstallation` profile is mandatory: the default profile holds
    a lock that serialises and breaks concurrent conversions across worker
    children.
    """
    with tempfile.TemporaryDirectory() as tmp:
        in_path = Path(tmp) / "in.docx"
        in_path.write_bytes(docx_bytes)
        out_path = Path(tmp) / "in.pdf"

        # Fixed argv, no shell: the only external input (docx_bytes) is written to a
        # temp file, never interpolated into the command.
        result = subprocess.run(  # noqa: S603
            [  # noqa: S607
                "soffice",
                "--headless",
                f"-env:UserInstallation=file://{tmp}/lo",
                "--convert-to",
                "pdf",
                "--outdir",
                tmp,
                str(in_path),
            ],
            timeout=120,
            capture_output=True,
            check=False,
        )

        if result.returncode != 0:
            stderr = result.stderr.decode("utf-8", "replace")[:500]
            raise RuntimeError(
                f"LibreOffice conversion failed (rc={result.returncode}): {stderr}"
            )
        if not out_path.exists():
            stderr = result.stderr.decode("utf-8", "replace")[:500]
            raise RuntimeError(f"LibreOffice produced no PDF output: {stderr}")

        return out_path.read_bytes()
