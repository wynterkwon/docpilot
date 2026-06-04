from __future__ import annotations

from collections.abc import Callable
from pathlib import Path
from typing import Any

from sqlalchemy.exc import IntegrityError

from docpilot.db import client
from docpilot.db.schema import Chunk, Document
from docpilot.exceptions import SearchError
from docpilot.ingestion.models import IngestedDocument

EmbedFn = Callable[[str], list[float]]

_CHUNK_SIZE = 1000
_CHUNK_OVERLAP = 200


def index(
    doc: IngestedDocument,
    embed_fn: EmbedFn | None = None,
    chunk_size: int = _CHUNK_SIZE,
    overlap: int = _CHUNK_OVERLAP,
) -> int:
    """
    Index an IngestedDocument into the database.

    Returns the document ID. Skips re-indexing if the source already exists.
    embed_fn: optional callable (text -> vector) for generating embeddings.
    """
    with client.session() as db:
        existing = (
            db.query(Document)
            .filter(Document.source == str(doc.source))
            .first()
        )
        if existing:
            return existing.id

        db_doc = Document(
            source=str(doc.source),
            mime_type=doc.mime_type,
            content=doc.content,
            metadata_=doc.metadata,
        )
        db.add(db_doc)
        db.flush()  # get db_doc.id before adding chunks

        chunks = _split(doc.content, chunk_size, overlap)
        for i, chunk_text in enumerate(chunks):
            chunk = Chunk(
                document_id=db_doc.id,
                chunk_index=i,
                content=chunk_text,
            )
            db.add(chunk)
            db.flush()

            if embed_fn:
                _set_embedding(db, chunk.id, embed_fn(chunk_text))

        return db_doc.id


def reindex(
    doc: IngestedDocument,
    embed_fn: EmbedFn | None = None,
    chunk_size: int = _CHUNK_SIZE,
    overlap: int = _CHUNK_OVERLAP,
) -> int:
    """Delete existing document and re-index from scratch."""
    with client.session() as db:
        existing = (
            db.query(Document)
            .filter(Document.source == str(doc.source))
            .first()
        )
        if existing:
            db.delete(existing)

    return index(doc, embed_fn=embed_fn, chunk_size=chunk_size, overlap=overlap)


def index_folder(
    folder: str | Path,
    embed_fn: EmbedFn | None = None,
) -> list[int]:
    """Ingest and index all supported files in a folder."""
    from docpilot.ingestion import text as text_ing
    from docpilot.ingestion import pdf as pdf_ing
    from docpilot.ingestion import image as image_ing
    from docpilot.ingestion import pptx as pptx_ing
    from docpilot.exceptions import IngestionError

    folder = Path(folder)
    if not folder.is_dir():
        raise SearchError("Not a directory", detail=str(folder))

    ingesters = {
        **{ext: text_ing.ingest for ext in text_ing.SUPPORTED_EXTENSIONS},
        ".pdf": pdf_ing.ingest,
        **{ext: image_ing.ingest for ext in image_ing.SUPPORTED_EXTENSIONS},
        ".pptx": pptx_ing.ingest,
    }

    doc_ids: list[int] = []
    for file in sorted(folder.rglob("*")):
        if not file.is_file():
            continue
        ingester = ingesters.get(file.suffix.lower())
        if not ingester:
            continue
        try:
            doc = ingester(file)
            doc_id = index(doc, embed_fn=embed_fn)
            doc_ids.append(doc_id)
        except IngestionError:
            raise
        except Exception as e:
            raise SearchError("Unexpected error during indexing", detail=str(e)) from e

    return doc_ids


def _split(text: str, chunk_size: int, overlap: int) -> list[str]:
    if not text:
        return []
    chunks: list[str] = []
    start = 0
    while start < len(text):
        end = start + chunk_size
        chunks.append(text[start:end])
        start += chunk_size - overlap
    return chunks


def _set_embedding(db: Any, chunk_id: int, vector: list[float]) -> None:
    from sqlalchemy import text
    from docpilot.db import client

    if client.is_sqlite():
        try:
            import sqlite_vec
        except ImportError as e:
            raise SearchError("sqlite-vec required for embeddings: pip install sqlite-vec") from e
        db.execute(
            text("INSERT OR REPLACE INTO vec_chunks(chunk_id, embedding) VALUES (:id, :vec)"),
            {"id": chunk_id, "vec": sqlite_vec.serialize_float32(vector)},
        )
    else:
        db.execute(
            text("UPDATE chunks SET embedding = :vec WHERE id = :id"),
            {"vec": str(vector), "id": chunk_id},
        )
