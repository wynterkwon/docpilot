from __future__ import annotations

from collections.abc import Callable

from sqlalchemy import text

from docpilot.db import client
from docpilot.exceptions import SearchError
from docpilot.search.models import SearchResult

EmbedFn = Callable[[str], list[float]]


def search(
    query: str,
    embed_fn: EmbedFn,
    top_k: int = 10,
) -> list[SearchResult]:
    """
    Vector similarity search.

    Uses sqlite-vec (cosine distance) for SQLite,
    pgvector (cosine distance) for PostgreSQL.
    embed_fn: callable that converts text to a float vector.
    """
    if not query.strip():
        raise SearchError("Query must not be empty")

    try:
        query_vec = embed_fn(query)
    except Exception as e:
        raise SearchError("Failed to generate query embedding", detail=str(e)) from e

    if client.is_sqlite():
        return _sqlite_search(query_vec, top_k)
    return _pg_search(query_vec, top_k)


def _sqlite_search(query_vec: list[float], top_k: int) -> list[SearchResult]:
    try:
        import sqlite_vec
    except ImportError as e:
        raise SearchError("sqlite-vec required: pip install sqlite-vec") from e

    serialized = sqlite_vec.serialize_float32(query_vec)

    sql = text("""
        SELECT v.chunk_id, c.document_id, d.source, c.content, v.distance
        FROM vec_chunks v
        JOIN chunks c ON c.id = v.chunk_id
        JOIN documents d ON d.id = c.document_id
        WHERE v.embedding MATCH :vec
        ORDER BY v.distance
        LIMIT :top_k
    """)

    with client.session() as db:
        rows = db.execute(sql, {"vec": serialized, "top_k": top_k}).fetchall()

    return [
        SearchResult(
            chunk_id=row.chunk_id,
            document_id=row.document_id,
            source=row.source,
            content=row.content,
            score=1.0 / (1.0 + float(row.distance)),
        )
        for row in rows
    ]


def _pg_search(query_vec: list[float], top_k: int) -> list[SearchResult]:
    vec_str = f"[{','.join(str(v) for v in query_vec)}]"

    sql = text("""
        SELECT
            c.id          AS chunk_id,
            c.document_id AS document_id,
            d.source      AS source,
            c.content     AS content,
            1 - (c.embedding <=> :vec::vector) AS score
        FROM chunks c
        JOIN documents d ON d.id = c.document_id
        WHERE c.embedding IS NOT NULL
        ORDER BY c.embedding <=> :vec::vector
        LIMIT :top_k
    """)

    with client.session() as db:
        rows = db.execute(sql, {"vec": vec_str, "top_k": top_k}).fetchall()

    return [
        SearchResult(
            chunk_id=row.chunk_id,
            document_id=row.document_id,
            source=row.source,
            content=row.content,
            score=float(row.score),
        )
        for row in rows
    ]


def openai_embed_fn(
    api_key: str | None = None,
    model: str = "text-embedding-3-small",
) -> EmbedFn:
    """Factory that returns an OpenAI embedding function."""
    import os

    key = api_key or os.environ.get("OPENAI_API_KEY")
    if not key:
        raise SearchError(
            "OpenAI API key not provided",
            detail="Pass api_key or set OPENAI_API_KEY env var",
        )

    def _embed(text: str) -> list[float]:
        try:
            from openai import OpenAI
        except ImportError as e:
            raise SearchError("openai SDK required: pip install openai") from e

        c = OpenAI(api_key=key)
        response = c.embeddings.create(input=text, model=model)
        return response.data[0].embedding

    return _embed
