from __future__ import annotations

from docpilot.db import client
from docpilot.db.schema import Chunk, Document
from docpilot.exceptions import SearchError
from docpilot.search.models import SearchResult


def search(query: str, top_k: int = 10) -> list[SearchResult]:
    """
    Morpheme-based search using kiwipiepy.

    Tokenizes both query and chunk content into morphemes,
    then ranks chunks by Jaccard similarity of morpheme sets.
    """
    if not query.strip():
        raise SearchError("Query must not be empty")

    query_morphemes = _tokenize(query)
    if not query_morphemes:
        raise SearchError("No morphemes extracted from query", detail=query)

    with client.session() as db:
        rows = (
            db.query(Chunk, Document.source)
            .join(Document, Chunk.document_id == Document.id)
            .all()
        )

    scored: list[SearchResult] = []
    for chunk, source in rows:
        chunk_morphemes = _tokenize(chunk.content)
        score = _jaccard(query_morphemes, chunk_morphemes)
        if score > 0:
            scored.append(
                SearchResult(
                    chunk_id=chunk.id,
                    document_id=chunk.document_id,
                    source=source,
                    content=chunk.content,
                    score=score,
                )
            )

    scored.sort(key=lambda r: r.score, reverse=True)
    return scored[:top_k]


def _tokenize(text: str) -> set[str]:
    try:
        from kiwipiepy import Kiwi
    except ImportError as e:
        raise SearchError("kiwipiepy is required: pip install kiwipiepy") from e

    kiwi = Kiwi()
    tokens = kiwi.tokenize(text)
    # Keep only content morphemes (nouns, verbs, adjectives)
    content_tags = {"NNG", "NNP", "VV", "VA", "XR"}
    return {token.form for token in tokens if token.tag in content_tags}


def _jaccard(a: set[str], b: set[str]) -> float:
    if not a or not b:
        return 0.0
    return len(a & b) / len(a | b)
