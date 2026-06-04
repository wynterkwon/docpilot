from __future__ import annotations

import zipfile
from pathlib import Path

from docpilot.exceptions import IngestionError
from docpilot.ingestion.models import IngestedDocument


def ingest(path: str | Path) -> IngestedDocument:
    path = Path(path)

    if not path.exists():
        raise IngestionError("File not found", detail=str(path))

    if path.suffix.lower() != ".hwpx":
        raise IngestionError(f"Expected .hwpx, got '{path.suffix}'", detail=str(path))

    try:
        from lxml import etree
    except ImportError as e:
        raise IngestionError("lxml is required: pip install lxml") from e

    try:
        with zipfile.ZipFile(path, "r") as zf:
            content_xml = _find_content(zf)
            root = etree.fromstring(content_xml)
    except zipfile.BadZipFile as e:
        raise IngestionError("Invalid HWPX file (not a ZIP)", detail=str(e)) from e
    except Exception as e:
        raise IngestionError("Failed to parse HWPX", detail=str(e)) from e

    paragraphs = _extract_text(root)
    content = "\n".join(paragraphs)

    return IngestedDocument(
        source=path,
        content=content,
        mime_type="application/hwp+zip",
        metadata={
            "paragraph_count": len(paragraphs),
            "size_bytes": path.stat().st_size,
        },
    )


def _find_content(zf: zipfile.ZipFile) -> bytes:
    candidates = [n for n in zf.namelist() if n.endswith("content.hml") or n.endswith("section0.xml")]
    if not candidates:
        raise IngestionError("No content file found in HWPX")
    return zf.read(candidates[0])


def _extract_text(root) -> list[str]:
    # Support both 2011 and 2012 Hancom namespace variants
    ns = root.nsmap.get("hp", "http://www.hancom.co.kr/hwpml/2012/paragraph")
    hp_p = f"{{{ns}}}p"
    hp_t = f"{{{ns}}}t"

    results: list[str] = []
    for para in root.iter(hp_p):
        text = "".join(el.text or "" for el in para.iter(hp_t)).strip()
        if text:
            results.append(text)
    return results
