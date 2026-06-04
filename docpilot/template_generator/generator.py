from __future__ import annotations

import shutil
import zipfile
from pathlib import Path

from docpilot.exceptions import TemplateError
from docpilot.template_generator.analyzer import (
    AnalysisResult,
    DEFAULT_CONFIDENCE_THRESHOLD,
    analyze,
)

_NS_HP = "http://www.hancom.co.kr/hwpml/2012/paragraph"
_CONTENT_PATH = "Contents/content.hml"


def generate(
    samples: list[str | Path],
    output: str | Path,
    confidence_threshold: float = DEFAULT_CONFIDENCE_THRESHOLD,
    use_llm: bool | None = None,
    llm_mapper=None,
) -> Path:
    """
    Generate an HWPX template from sample documents.

    Flow:
      1. Analyze samples for common section structure.
      2. If confidence >= threshold → generate template directly.
      3. If confidence < threshold:
           - use_llm=True  → use LLM to infer sections, then generate
           - use_llm=False → raise TemplateError (caller should add more samples)
           - use_llm=None  → print confidence and raise (interactive use)

    Returns path to the generated template HWPX.
    """
    output = Path(output)
    result = analyze(samples, confidence_threshold)

    if result.confidence >= confidence_threshold:
        return _build_template(samples[0], result.common_sections, output)

    # Confidence too low
    msg = (
        f"공통 패턴 신뢰도: {result.confidence:.0%} "
        f"(임계값: {confidence_threshold:.0%}). "
        f"감지된 섹션: {result.common_sections or '없음'}"
    )

    if use_llm is None:
        raise TemplateError(
            msg,
            detail="use_llm=True로 LLM 보조를 활성화하거나 샘플을 추가하세요",
        )

    if not use_llm:
        raise TemplateError(msg, detail="샘플을 추가하거나 임계값을 낮추세요")

    # LLM-assisted mode
    sections = _infer_sections_with_llm(samples, result, llm_mapper)
    return _build_template(samples[0], sections, output)


def _infer_sections_with_llm(
    samples: list[str | Path],
    result: AnalysisResult,
    llm_mapper,
) -> list[str]:
    if llm_mapper is None:
        raise TemplateError(
            "LLM 보조 모드에는 llm_mapper가 필요합니다",
            detail="ClaudeMapper 또는 OpenAIMapper 인스턴스를 전달하세요",
        )

    from docpilot.mapping.base import TemplateSection

    all_headings = []
    for headings in result.per_document_sections.values():
        all_headings.extend(headings)

    content = (
        f"다음은 {result.total_documents}개 문서에서 추출한 제목 후보 목록입니다:\n"
        + "\n".join(f"- {h}" for h in sorted(set(all_headings)))
    )

    mapping = llm_mapper.map(
        content=content,
        sections=[
            TemplateSection(
                name="sections",
                description=(
                    "위 목록에서 문서 템플릿의 공통 섹션으로 적합한 항목을 골라 "
                    "JSON 배열 형태의 문자열로 반환하세요. 예: [\"서론\", \"본론\", \"결론\"]"
                ),
            )
        ],
    )

    import json
    raw = mapping.sections.get("sections", "[]")
    try:
        sections = json.loads(raw)
        if not isinstance(sections, list):
            raise ValueError
        return [str(s) for s in sections]
    except (json.JSONDecodeError, ValueError) as e:
        raise TemplateError("LLM이 유효한 섹션 목록을 반환하지 않았습니다", detail=raw) from e


def _build_template(
    base_hwpx: str | Path,
    sections: list[str],
    output: Path,
) -> Path:
    """
    Copy the first sample HWPX as a structural base, then inject
    {{section_name}} placeholders as new paragraphs at the end of the content.
    """
    try:
        from lxml import etree
    except ImportError as e:
        raise TemplateError("lxml is required: pip install lxml") from e

    import tempfile

    base_hwpx = Path(base_hwpx)
    output.parent.mkdir(parents=True, exist_ok=True)

    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)

        try:
            with zipfile.ZipFile(base_hwpx, "r") as zf:
                zf.extractall(tmp_path)
        except zipfile.BadZipFile as e:
            raise TemplateError("Invalid base HWPX file", detail=str(e)) from e

        content_file = tmp_path / _CONTENT_PATH
        if not content_file.exists():
            raise TemplateError("content.hml not found in base HWPX")

        tree = etree.parse(str(content_file))
        root = tree.getroot()

        _inject_placeholders(root, sections)

        tree.write(
            str(content_file),
            xml_declaration=True,
            encoding="UTF-8",
            pretty_print=False,
        )

        _pack(tmp_path, output)

    return output


def _inject_placeholders(root, sections: list[str]) -> None:
    from lxml import etree

    hp = _NS_HP
    body = root.find(f".//{{{hp}}}body")
    if body is None:
        body = root.find(f".//{{{hp}}}sec")
    if body is None:
        body = root  # fallback: append to root

    for section in sections:
        p = etree.SubElement(body, f"{{{hp}}}p")
        t = etree.SubElement(p, f"{{{hp}}}t")
        t.text = f"{{{{{section}}}}}"


def _pack(src: Path, output: Path) -> None:
    with zipfile.ZipFile(output, "w", zipfile.ZIP_DEFLATED) as zf:
        mimetype = src / "mimetype"
        if mimetype.exists():
            zf.write(mimetype, "mimetype", compress_type=zipfile.ZIP_STORED)
        for file in sorted(src.rglob("*")):
            if not file.is_file() or file.name == "mimetype":
                continue
            zf.write(file, file.relative_to(src))
