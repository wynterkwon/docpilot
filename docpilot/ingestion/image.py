from __future__ import annotations

from pathlib import Path

from docpilot.exceptions import IngestionError
from docpilot.ingestion.models import IngestedDocument

SUPPORTED_EXTENSIONS = {".jpg", ".jpeg", ".png", ".tiff", ".tif", ".bmp", ".webp"}


def ingest(path: str | Path, ocr_language: str = "kor+eng") -> IngestedDocument:
    path = Path(path)

    if not path.exists():
        raise IngestionError("File not found", detail=str(path))

    if path.suffix.lower() not in SUPPORTED_EXTENSIONS:
        raise IngestionError(
            f"Unsupported image format '{path.suffix}'",
            detail=str(path),
        )

    try:
        from PIL import Image
        import pytesseract
    except ImportError as e:
        raise IngestionError(
            "Pillow and pytesseract are required: pip install Pillow pytesseract"
        ) from e

    try:
        image = Image.open(path)
        image.load()
    except Exception as e:
        raise IngestionError("Failed to open image", detail=str(e)) from e

    try:
        text = pytesseract.image_to_string(image, lang=ocr_language)
    except Exception as e:
        raise IngestionError("OCR failed", detail=str(e)) from e

    return IngestedDocument(
        source=path,
        content=text.strip(),
        mime_type=_mime_type(path.suffix.lower()),
        metadata={
            "ocr_language": ocr_language,
            "width": image.width,
            "height": image.height,
            "mode": image.mode,
            "size_bytes": path.stat().st_size,
        },
    )


def _mime_type(suffix: str) -> str:
    return {
        ".jpg": "image/jpeg",
        ".jpeg": "image/jpeg",
        ".png": "image/png",
        ".tiff": "image/tiff",
        ".tif": "image/tiff",
        ".bmp": "image/bmp",
        ".webp": "image/webp",
    }.get(suffix, "image/octet-stream")
