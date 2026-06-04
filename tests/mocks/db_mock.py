from __future__ import annotations

from contextlib import contextmanager
from unittest.mock import MagicMock, patch


@contextmanager
def mock_db_session(rows=None):
    """
    Patch docpilot.db.client.session to yield a mock DB session.

    rows: list of objects that query().join().filter().all() returns.
    """
    session_mock = MagicMock()
    query_mock = session_mock.query.return_value
    query_mock.join.return_value = query_mock
    query_mock.filter.return_value = query_mock
    query_mock.limit.return_value = query_mock
    query_mock.all.return_value = rows or []
    query_mock.first.return_value = None

    @contextmanager
    def _session():
        yield session_mock

    with patch("docpilot.db.client.session", side_effect=_session):
        yield session_mock
