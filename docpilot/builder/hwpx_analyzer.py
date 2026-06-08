"""HWPX 템플릿에서 플레이스홀더별 스타일 컨텍스트를 추출한다."""
from __future__ import annotations

import zipfile
from pathlib import Path
from typing import Optional

from docpilot.builder.base import PLACEHOLDER_RE

_CONTENT_CANDIDATES = ["Contents/content.hml", "Contents/section0.xml"]
_HEADER_PATH = "Contents/header.xml"

_HP_NS_VARIANTS = [
    "http://www.hancom.co.kr/hwpml/2011/paragraph",
    "http://www.hancom.co.kr/hwpml/2012/paragraph",
]
_HH_NS = "http://www.hancom.co.kr/hwpml/2011/head"

# HWPUNIT → mm 변환 상수 (1mm ≈ 283.46 HWPUNIT)
_HWP_PER_MM = 283.46
# HWPUNIT → pt 변환 상수 (1pt = 100 HWPUNIT)
_HWP_PER_PT = 100


def extract_style_hints(template_path: Path) -> dict[str, str]:
    """HWPX 템플릿을 분석해 플레이스홀더별 자연어 스타일 힌트를 반환한다.

    Returns:
        {"섹션명": "10pt 바탕, JUSTIFY, 표 셀 너비 120mm"} 형식의 dict
        스타일 정보를 추출할 수 없으면 빈 dict 반환
    """
    if template_path.suffix.lower() != ".hwpx":
        return {}

    try:
        content_xml, header_xml = _read_zip_contents(template_path)
    except Exception:
        return {}

    if content_xml is None:
        return {}

    try:
        from lxml import etree
        content_root = etree.fromstring(content_xml)
    except Exception:
        return {}

    header_root = None
    if header_xml is not None:
        try:
            from lxml import etree
            header_root = etree.fromstring(header_xml)
        except Exception:
            pass

    hp_ns = _detect_hp_ns(content_root)
    char_shapes = _parse_char_shapes(header_root) if header_root is not None else {}
    para_shapes = _parse_para_shapes(header_root) if header_root is not None else {}

    hp_p = f"{{{hp_ns}}}p"
    hp_t = f"{{{hp_ns}}}t"
    hp_run = f"{{{hp_ns}}}run"
    hp_tc = f"{{{hp_ns}}}tc"
    hp_cellsz = f"{{{hp_ns}}}cellSz"

    hints: dict[str, str] = {}

    for para in content_root.iter(hp_p):
        t_elements = para.findall(f".//{hp_t}")
        if not t_elements:
            continue
        full_text = "".join((el.text or "") for el in t_elements)
        match = PLACEHOLDER_RE.search(full_text)
        if not match:
            continue

        key = match.group(1)
        if key in hints:
            continue

        char_pr_id = _find_char_pr_id(para, hp_run, hp_t)
        para_pr_id = para.get("paraPrIDRef")

        parts: list[str] = []

        if char_pr_id is not None and char_pr_id in char_shapes:
            cs = char_shapes[char_pr_id]
            height_raw = cs.get("height")
            if height_raw:
                pt = int(height_raw) / _HWP_PER_PT
                pt_str = f"{pt:g}pt"
                font = cs.get("font_hangul", "")
                parts.append(f"{pt_str} {font}".strip() if font else pt_str)
            if cs.get("bold"):
                parts.append("볼드")
            if cs.get("italic"):
                parts.append("이탤릭")

        if para_pr_id is not None and para_pr_id in para_shapes:
            align = para_shapes[para_pr_id].get("align", "")
            if align:
                parts.append(align)

        tc = _find_ancestor(para, hp_tc)
        if tc is not None:
            csz = tc.find(hp_cellsz)
            if csz is not None:
                width_hw = csz.get("width")
                if width_hw:
                    width_mm = int(width_hw) / _HWP_PER_MM
                    parts.append(f"표 셀 너비 {width_mm:.0f}mm")

        hints[key] = ", ".join(parts) if parts else ""

    return hints


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _read_zip_contents(path: Path) -> tuple[Optional[bytes], Optional[bytes]]:
    with zipfile.ZipFile(path, "r") as zf:
        names = zf.namelist()
        content_name = next((c for c in _CONTENT_CANDIDATES if c in names), None)
        content_xml = zf.read(content_name) if content_name else None
        header_xml = zf.read(_HEADER_PATH) if _HEADER_PATH in names else None
    return content_xml, header_xml


def _detect_hp_ns(root) -> str:
    for ns in _HP_NS_VARIANTS:
        if ns in root.nsmap.values():
            return ns
    return root.nsmap.get("hp", _HP_NS_VARIANTS[0])


def _parse_char_shapes(header_root) -> dict[str, dict]:
    """header.xml에서 charPr(글자 서식) 정의를 파싱한다."""
    hh = _HH_NS
    shapes: dict[str, dict] = {}
    for el in header_root.iter(f"{{{hh}}}charPr"):
        cid = el.get("id")
        if cid is None:
            continue
        font_ref = el.find(f"{{{hh}}}fontRef")
        shapes[cid] = {
            "height": el.get("height"),
            "font_hangul": font_ref.get("hangul", "") if font_ref is not None else "",
            "bold": el.find(f"{{{hh}}}bold") is not None,
            "italic": el.find(f"{{{hh}}}italic") is not None,
        }
    return shapes


def _parse_para_shapes(header_root) -> dict[str, dict]:
    """header.xml에서 paraPr(문단 서식) 정의를 파싱한다."""
    hh = _HH_NS
    shapes: dict[str, dict] = {}
    for el in header_root.iter(f"{{{hh}}}paraPr"):
        pid = el.get("id")
        if pid is None:
            continue
        shapes[pid] = {"align": el.get("align", "")}
    return shapes


def _find_char_pr_id(para, hp_run: str, hp_t: str) -> Optional[str]:
    """플레이스홀더 텍스트를 포함하는 run의 charPrIDRef를 반환한다."""
    for run in para.iter(hp_run):
        for t in run.findall(hp_t):
            if t.text and PLACEHOLDER_RE.search(t.text):
                return run.get("charPrIDRef")
    # fallback: 첫 번째 run의 charPrIDRef
    for run in para.iter(hp_run):
        cpr = run.get("charPrIDRef")
        if cpr is not None:
            return cpr
    return None


def _find_ancestor(element, tag: str):
    """tag에 해당하는 가장 가까운 조상 element를 반환한다."""
    parent = element.getparent()
    while parent is not None:
        if parent.tag == tag:
            return parent
        parent = parent.getparent()
    return None
