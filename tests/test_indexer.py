from __future__ import annotations

from docpilot.db.indexer import _split


class TestSplit:
    def test_empty_returns_empty(self):
        assert _split("", 100, 10) == []

    def test_whitespace_only_returns_empty(self):
        assert _split("   \n\n   ", 100, 10) == []

    def test_single_paragraph_fits(self):
        text = "짧은 문단입니다."
        assert _split(text, chunk_size=100, overlap=10) == [text]

    def test_two_paragraphs_fit_in_one_chunk(self):
        text = "첫 번째 문단.\n\n두 번째 문단."
        chunks = _split(text, chunk_size=100, overlap=10)
        assert len(chunks) == 1
        assert "첫 번째 문단." in chunks[0]
        assert "두 번째 문단." in chunks[0]

    def test_paragraph_never_split_mid_way(self):
        """각 청크는 완전한 문단 단위만 포함해야 한다."""
        paragraphs = [f"유니크문단{i}끝" for i in range(6)]  # ~8 chars each
        text = "\n\n".join(paragraphs)
        para_set = set(paragraphs)

        chunks = _split(text, chunk_size=25, overlap=0)

        for chunk in chunks:
            for unit in chunk.split("\n\n"):
                assert unit in para_set, f"잘린 문단 감지: {unit!r}"

    def test_oversized_paragraph_char_split_fallback(self):
        """chunk_size를 초과하는 단일 문단은 문자 단위로 분리된다."""
        long_para = "가" * 200
        chunks = _split(long_para, chunk_size=50, overlap=10)

        assert len(chunks) > 1
        for chunk in chunks:
            assert len(chunk) <= 50

    def test_overlap_carries_previous_paragraph(self):
        """overflow 시 overlap 범위 내 이전 문단이 다음 청크에 포함된다."""
        p1 = "짧."    # 2 chars
        p2 = "조금."  # 4 chars — overlap(5) 안에 들어감
        p3 = "세번째." # 5 chars
        text = f"{p1}\n\n{p2}\n\n{p3}"
        # p1+p2 = 2+2+4=8 ≤ 10, p1+p2+p3 = 8+2+5=15 > 10 → overflow after p2
        chunks = _split(text, chunk_size=10, overlap=5)

        assert len(chunks) == 2
        assert p2 in chunks[0]  # p2는 첫 번째 청크에 있고
        assert p2 in chunks[1]  # overlap으로 두 번째 청크에도 등장
        assert p3 in chunks[1]

    def test_chunks_cover_all_content(self):
        """모든 문단이 최소 하나의 청크에 포함된다."""
        paragraphs = [f"문단{i}" for i in range(10)]
        text = "\n\n".join(paragraphs)
        chunks = _split(text, chunk_size=20, overlap=5)

        all_content = "\n\n".join(chunks)
        for para in paragraphs:
            assert para in all_content, f"누락된 문단: {para!r}"
