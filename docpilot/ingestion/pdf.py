from __future__ import annotations

from pathlib import Path

from docpilot.exceptions import IngestionError
from docpilot.ingestion.models import IngestedDocument

# Minimum characters per page to consider a PDF text-based (not scanned)
_MIN_CHARS_PER_PAGE = 50


def ingest(path: str | Path, ocr_language: str = "kor+eng") -> IngestedDocument:
    path = Path(path)

    if not path.exists():
        raise IngestionError("File not found", detail=str(path))

    if path.suffix.lower() != ".pdf":
        raise IngestionError(f"Expected .pdf, got '{path.suffix}'", detail=str(path))

    text, used_ocr, page_count = _extract(path, ocr_language)

    return IngestedDocument(
        source=path,
        content=text,
        mime_type="application/pdf",
        metadata={
            "page_count": page_count,
            "ocr": used_ocr,
            "ocr_language": ocr_language if used_ocr else None,
            "size_bytes": path.stat().st_size,
        },
    )


def _extract(path: Path, ocr_language: str) -> tuple[str, bool, int]:
    try:
        import pdfplumber
    except ImportError as e:
        raise IngestionError("pdfplumber is required: pip install pdfplumber") from e

    try:
        with pdfplumber.open(path) as pdf:
            pages = pdf.pages
            page_count = len(pages)
            texts = [page.extract_text() or "" for page in pages]
    except Exception as e:
        raise IngestionError("Failed to open PDF", detail=str(e)) from e

    total_chars = sum(len(t) for t in texts)
    if page_count > 0 and (total_chars / page_count) >= _MIN_CHARS_PER_PAGE:
        return "\n\n".join(texts).strip(), False, page_count

    # Scanned PDF — fall back to OCR
    ocr_text = _ocr(path, ocr_language, page_count)
    return ocr_text, True, page_count


def _ocr(path: Path, language: str, page_count: int) -> str:
    try:
        from pdf2image import convert_from_path
        import pytesseract
    except ImportError as e:
        raise IngestionError(
            "pdf2image and pytesseract are required for OCR: "
            "pip install pdf2image pytesseract"
        ) from e

    try:
        images = convert_from_path(str(path))
    except Exception as e:
        raise IngestionError("Failed to convert PDF pages to images", detail=str(e)) from e

    texts: list[str] = []
    for image in images:
        try:
            texts.append(pytesseract.image_to_string(image, lang=language))
        except Exception as e:
            raise IngestionError("OCR failed", detail=str(e)) from e

    return "\n\n".join(texts).strip()
