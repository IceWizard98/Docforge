import shutil
from io import BytesIO
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from adapters.export.libreoffice import docx_to_pdf


def _write_output(cmd, **kwargs):
    """Mimic soffice: drop <stem>.pdf into the --outdir it was told to use."""
    outdir = cmd[cmd.index("--outdir") + 1]
    in_path = cmd[-1]
    out = Path(outdir) / (Path(in_path).stem + ".pdf")
    out.write_bytes(b"%PDF-1.4 fake")
    return MagicMock(returncode=0, stderr=b"")


class TestDocxToPdfMocked:
    def test_invokes_soffice_with_temp_profile_and_timeout(self):
        with patch("adapters.export.libreoffice.subprocess.run", side_effect=_write_output) as run:
            out = docx_to_pdf(b"docx-bytes")

        assert out.startswith(b"%PDF")
        cmd = run.call_args.args[0]
        assert cmd[0] == "soffice"
        assert "--headless" in cmd
        # Per-call profile dir is mandatory: LibreOffice's default profile has a
        # lock that serialises (and breaks) concurrent conversions.
        assert any(a.startswith("-env:UserInstallation=file://") for a in cmd)
        assert "--convert-to" in cmd
        assert "pdf" in cmd
        assert run.call_args.kwargs["timeout"] == 120

    def test_missing_output_raises_runtimeerror(self):
        # rc 0 but no file produced.
        with patch(
            "adapters.export.libreoffice.subprocess.run",
            return_value=MagicMock(returncode=0, stderr=b"broken font"),
        ), pytest.raises(RuntimeError):
            docx_to_pdf(b"docx-bytes")

    def test_nonzero_return_code_raises_runtimeerror(self):
        with patch(
            "adapters.export.libreoffice.subprocess.run",
            return_value=MagicMock(returncode=1, stderr=b"conversion error"),
        ), pytest.raises(RuntimeError):
            docx_to_pdf(b"docx-bytes")


@pytest.mark.skipif(shutil.which("soffice") is None, reason="LibreOffice non installato")
def test_real_conversion_produces_pdf():
    from docx import Document

    doc = Document()
    doc.add_paragraph("ciao mondo")
    buf = BytesIO()
    doc.save(buf)

    pdf = docx_to_pdf(buf.getvalue())
    assert pdf.startswith(b"%PDF")
