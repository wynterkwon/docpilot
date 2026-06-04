from __future__ import annotations

from pathlib import Path

from docpilot.exceptions import IngestionError
from docpilot.ingestion.models import IngestedDocument

SUPPORTED_EXTENSIONS = {".txt", ".md", ".rst", ".csv"}


def ingest(path: str | Path) -> IngestedDocument:
    path = Path(path)

    if not path.exists():
        raise IngestionError("File not found", detail=str(path))

    if path.suffix.lower() not in SUPPORTED_EXTENSIONS:
        raise IngestionError(
            f"Unsupported extension '{path.suffix}'",
            detail=str(path),
        )

    try:
        content = path.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        content = path.read_text(encoding="cp949")
    except OSError as e:
        raise IngestionError("Failed to read file", detail=str(e)) from e

    return IngestedDocument(
        source=path,
        content=content,
        mime_type="text/plain",
        metadata={"encoding": "utf-8", "size_bytes": path.stat().st_size},
    )
