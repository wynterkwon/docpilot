from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from docpilot.exceptions import SearchError
from docpilot.search.models import SearchResult


def _make_chunk(chunk_id=1, doc_id=1, source="file.txt", content="테스트 내용", score=0.9):
    chunk = MagicMock()
    chunk.id = chunk_id
    chunk.document_id = doc_id
    chunk.content = content
    return chunk, source


class TestExactSearch:
    def test_returns_results(self):
        from tests.mocks.db_mock import mock_db_session
        from docpilot.search import exact

        chunk, source = _make_chunk(content="사업 계획 핵심 내용")
        with mock_db_session(rows=[(chunk, source)]):
            results = exact.search("사업 계획")

        assert len(results) == 1
        assert results[0].source == source
        assert results[0].content == "사업 계획 핵심 내용"

    def test_empty_query_raises(self):
        from docpilot.search import exact
        with pytest.raises(SearchError, match="empty"):
            exact.search("   ")

    def test_score_positive_for_match(self):
        from docpilot.search.exact import _score
        assert _score("사업 계획 내용", "사업 계획") > 0

    def test_score_zero_for_no_match(self):
        from docpilot.search.exact import _score
        assert _score("전혀 다른 내용", "사업 계획") == 0.0


class TestEmbeddingSearch:
    def test_calls_embed_fn(self):
        from docpilot.search import embedding

        embed_fn = MagicMock(return_value=[0.1] * 1536)
        mock_row = MagicMock()
        mock_row.chunk_id = 1
        mock_row.document_id = 1
        mock_row.source = "file.txt"
        mock_row.content = "내용"
        mock_row.score = 0.9

        with (
            patch("docpilot.db.client.is_sqlite", return_value=False),
            patch("docpilot.db.client.session") as mock_session,
        ):
            ctx = MagicMock()
            ctx.__enter__ = MagicMock(return_value=MagicMock(
                execute=MagicMock(return_value=MagicMock(fetchall=MagicMock(return_value=[mock_row])))
            ))
            ctx.__exit__ = MagicMock(return_value=False)
            mock_session.return_value = ctx

            results = embedding.search("쿼리", embed_fn=embed_fn, top_k=5)

        embed_fn.assert_called_once_with("쿼리")
        assert len(results) == 1

    def test_empty_query_raises(self):
        from docpilot.search import embedding
        with pytest.raises(SearchError, match="empty"):
            embedding.search("", embed_fn=lambda x: [])


class TestMorphemeSearch:
    def test_jaccard_similarity(self):
        from docpilot.search.morpheme import _jaccard
        assert _jaccard({"사업", "계획"}, {"사업", "목표"}) == pytest.approx(1 / 3)
        assert _jaccard(set(), {"사업"}) == 0.0
        assert _jaccard({"사업"}, {"사업"}) == pytest.approx(1.0)

    def test_empty_query_raises(self):
        from docpilot.search import morpheme
        with pytest.raises(SearchError, match="empty"):
            morpheme.search("")
