"""
Tesseract OCR adapter for scanned PDFs and images.

Requires:
- pytesseract (Python): pip install pytesseract
- tesseract-ocr (system): apt-get install tesseract-ocr or brew install tesseract
- Language packs: tesseract-ocr-ita, tesseract-ocr-eng etc.

For Docker: install tesseract-ocr + language packs in Dockerfile.
"""

import asyncio

from config.settings import get_settings


class TesseractOCRAdapter:
    def __init__(self, tesseract_cmd: str | None = None):
        settings = get_settings()
        self.tesseract_cmd = tesseract_cmd or settings.tesseract_cmd

    async def ocr_image(self, image_bytes: bytes, language: str = "ita+eng") -> str:
        try:
            import pytesseract
            from PIL import Image
        except ImportError:
            raise ImportError(
                "pytesseract and Pillow are required. "
                "Install with: pip install pytesseract Pillow"
            )

        pytesseract.pytesseract.tesseract_cmd = self.tesseract_cmd

        img = Image.open(__import__("io").BytesIO(image_bytes))
        text = await asyncio.to_thread(
            pytesseract.image_to_string, img, lang=language
        )
        return text.strip()

    async def ocr_pdf(self, pdf_bytes: bytes, language: str = "ita+eng") -> str:
        try:
            import fitz
        except ImportError:
            raise ImportError("pymupdf is required. Install with: pip install pymupdf")

        try:
            import pytesseract
            from PIL import Image
        except ImportError:
            raise ImportError(
                "pytesseract and Pillow are required. "
                "Install with: pip install pytesseract Pillow"
            )

        pytesseract.pytesseract.tesseract_cmd = self.tesseract_cmd
        doc = fitz.open(stream=pdf_bytes, filetype="pdf")
        pages_text: list[str] = []

        for page_num in range(len(doc)):
            page = doc[page_num]
            pix = page.get_pixmap()
            img = Image.open(__import__("io").BytesIO(pix.tobytes("png")))
            text = await asyncio.to_thread(
                pytesseract.image_to_string, img, lang=language
            )
            cleaned = text.strip()
            if cleaned:
                pages_text.append(f"--- Page {page_num + 1} ---\n{cleaned}")

        doc.close()
        return "\n\n".join(pages_text)
