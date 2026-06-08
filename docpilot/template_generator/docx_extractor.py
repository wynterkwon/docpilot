"""DOCX 파일에서 문단 정보를 추출한다 (HWPX extractor와 동일한 인터페이스)."""
from __future__ import annotations

from pathlib import Path

from docpilot.exceptions import TemplateError
from docpilot.template_generator.extractor import ParagraphInfo

# pt → 1/100 pt (HWPX 단위와 통일)
_PT_TO_HWP = 100
_HEADING_PT_THRESHOLD = 14.0


def extract_docx(path: str | Path) -> list[ParagraphInfo]:
    """Extract paragraph info from a DOCX file."""
    path = Path(path)

    if not path.exists():
        raise TemplateError("File not found", detail=str(path))

    try:
        import docx as python_docx
    except ImportError as e:
        raise TemplateError("python-docx is required: pip install python-docx") from e

    try:
        doc = python_docx.Document(str(path))
    except Exception as e:
        raise TemplateError("Failed to open DOCX", detail=str(e)) from e

    results: list[ParagraphInfo] = []

    for para in doc.paragraphs:
        text = para.text.strip()
        if not text:
            continue

        style_name = para.style.name if para.style else ""

        font_size_pt: float | None = None
        bold = False

        for run in para.runs:
            if run.font.size is not None and font_size_pt is None:
                font_size_pt = run.font.size.pt
            if run.bold:
                bold = True

        # 스타일 체인에서 폰트 크기 상속 탐색
        if font_size_pt is None:
            s = para.style
            while s is not None:
                if s.font.size is not None:
                    font_size_pt = s.font.size.pt
                    break
                s = s.base_style

        # 1/100 pt 단위로 변환 (ParagraphInfo.is_heading_candidate 기준과 일치)
        font_size_hwp = int(font_size_pt * _PT_TO_HWP) if font_size_pt else None

        results.append(
            ParagraphInfo(
                text=text,
                style_id=style_name,
                font_size=font_size_hwp,
                bold=bold,
                indent_level=0,
            )
        )

    return results
