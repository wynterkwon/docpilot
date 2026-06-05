from __future__ import annotations

from collections.abc import Callable
from typing import TYPE_CHECKING

from docpilot.mapping.base import BaseLLMMapper, MappingResult, TemplateSection
from docpilot.search.models import SearchResult

if TYPE_CHECKING:
    from docpilot.ingestion.models import IngestedDocument

EmbedFn = Callable[[str], list[float]]


class RagMapper:
    """
    Wraps any BaseLLMMapper with retrieval-augmented generation.

    Retrieves relevant chunks from the indexed DB for the given sections,
    then delegates to the underlying mapper with the assembled context.

    embed_fn: if provided, uses vector similarity search.
              Falls back to morpheme search when omitted.
    top_k: number of chunks to retrieve per search.
    """

    def __init__(
        self,
        mapper: BaseLLMMapper,
        embed_fn: EmbedFn | None = None,
        top_k: int = 10,
    ) -> None:
        self._mapper = mapper
        self._embed_fn = embed_fn
        self._top_k = top_k

    def map(self, sections: list[TemplateSection], instructions: str | None = None) -> MappingResult:
        content = self.retrieve_content(sections)
        return self._mapper.map(content, sections, instructions)

    def retrieve_content(self, sections: list[TemplateSection]) -> str:
        """Retrieve and assemble relevant chunks for the given sections."""
        return _assemble(self._retrieve(sections))

    def _retrieve(self, sections: list[TemplateSection]) -> list[SearchResult]:
        query = _build_query(sections)

        if self._embed_fn is not None:
            from docpilot.search import embedding as emb_search
            return emb_search.search(query, self._embed_fn, top_k=self._top_k)

        from docpilot.search import morpheme as mor_search
        return mor_search.search(query, top_k=self._top_k)


def _build_query(sections: list[TemplateSection]) -> str:
    parts: list[str] = []
    for s in sections:
        parts.append(s.description if s.description else s.name)
    return " ".join(parts)


def _assemble(results: list[SearchResult]) -> str:
    # Group chunks by source, preserving retrieval order within each source
    seen: dict[str, list[str]] = {}
    for r in results:
        seen.setdefault(r.source, []).append(r.content)

    parts: list[str] = []
    for source, chunks in seen.items():
        from pathlib import Path
        label = f"[출처: {Path(source).name}]"
        parts.append(f"{label}\n" + "\n".join(chunks))

    return "\n\n".join(parts)
