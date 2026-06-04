from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from docpilot.exceptions import IngestionError
from docpilot.ingestion import text as text_ing
from docpilot.ingestion import pptx as pptx_ing
from docpilot.ingestion.models import IngestedDocument


class TestTextIngestion:
    def test_basic(self, sample_txt: Path):
        doc = text_ing.ingest(sample_txt)
        assert isinstance(doc, IngestedDocument)
        assert "사업 계획서" in doc.content
        assert doc.mime_type == "text/plain"
        assert doc.source == sample_txt

    def test_file_not_found(self, tmp_path: Path):
        with pytest.raises(IngestionError, match="File not found"):
            text_ing.ingest(tmp_path / "missing.txt")

    def test_unsupported_extension(self, tmp_path: Path):
        bad = tmp_path / "file.xyz"
        bad.write_text("data")
        with pytest.raises(IngestionError, match="Unsupported extension"):
            text_ing.ingest(bad)

    def test_metadata_size(self, sample_txt: Path):
        doc = text_ing.ingest(sample_txt)
        assert doc.metadata["size_bytes"] == sample_txt.stat().st_size


class TestPdfIngestion:
    def test_text_based_pdf(self, tmp_path: Path):
        from docpilot.ingestion import pdf as pdf_ing

        mock_page = MagicMock()
        mock_page.extract_text.return_value = "A" * 200

        mock_pdf = MagicMock()
        mock_pdf.__enter__ = lambda s: s
        mock_pdf.__exit__ = MagicMock(return_value=False)
        mock_pdf.pages = [mock_page]

        path = tmp_path / "sample.pdf"
        path.write_bytes(b"%PDF-1.4 fake")

        with patch("pdfplumber.open", return_value=mock_pdf):
            doc = pdf_ing.ingest(path)

        assert doc.content == "A" * 200
        assert doc.metadata["ocr"] is False

    def test_file_not_found(self, tmp_path: Path):
        from docpilot.ingestion import pdf as pdf_ing
        with pytest.raises(IngestionError, match="File not found"):
            pdf_ing.ingest(tmp_path / "missing.pdf")

    def test_wrong_extension(self, tmp_path: Path):
        from docpilot.ingestion import pdf as pdf_ing
        bad = tmp_path / "file.txt"
        bad.write_text("x")
        with pytest.raises(IngestionError, match="Expected .pdf"):
            pdf_ing.ingest(bad)


class TestImageIngestion:
    def test_ocr(self, tmp_path: Path):
        from docpilot.ingestion import image as image_ing

        mock_image = MagicMock()
        mock_image.width = 800
        mock_image.height = 600
        mock_image.mode = "RGB"

        path = tmp_path / "sample.png"
        path.write_bytes(b"\x89PNG fake")

        with (
            patch("PIL.Image.open", return_value=mock_image),
            patch("pytesseract.image_to_string", return_value="추출된 텍스트"),
        ):
            doc = image_ing.ingest(path)

        assert doc.content == "추출된 텍스트"
        assert doc.metadata["width"] == 800

    def test_unsupported_extension(self, tmp_path: Path):
        from docpilot.ingestion import image as image_ing
        bad = tmp_path / "file.gif"
        bad.write_bytes(b"GIF fake")
        with pytest.raises(IngestionError, match="Unsupported image format"):
            image_ing.ingest(bad)


class TestPptxIngestion:
    def test_basic(self, sample_pptx: Path):
        doc = pptx_ing.ingest(sample_pptx)
        assert "[슬라이드 1]" in doc.content
        assert "2025 사업 계획" in doc.content
        assert doc.metadata["slide_count"] == 1

    def test_wrong_extension(self, tmp_path: Path):
        bad = tmp_path / "file.ppt"
        bad.write_bytes(b"fake")
        with pytest.raises(IngestionError, match="Expected .pptx"):
            pptx_ing.ingest(bad)
