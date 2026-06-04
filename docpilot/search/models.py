from __future__ import annotations

from dataclasses import dataclass


@dataclass
class SearchResult:
    chunk_id: int
    document_id: int
    source: str
    content: str
    score: float
