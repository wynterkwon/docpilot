from __future__ import annotations

import shutil
import tempfile
import zipfile
from pathlib import Path

from docpilot.builder.base import BaseBuilder, PLACEHOLDER_RE
from docpilot.exceptions import BuilderError

# Candidate content file paths inside the HWPX ZIP (tried in order)
_CONTENT_CANDIDATES = ["Contents/content.hml", "Contents/section0.xml"]


class HwpxBuilder(BaseBuilder):
    def build(
        self,
        template: str | Path,
        sections: dict[str, str],
        output: str | Path,
    ) -> Path:
        template, output = self._validate_paths(template, output)

        if template.suffix.lower() != ".hwpx":
            raise BuilderError(f"Expected .hwpx template, got '{template.suffix}'")

        try:
            from lxml import etree
        except ImportError as e:
            raise BuilderError("lxml is required: pip install lxml") from e

        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            _unpack(template, tmp_path)

            content_file = next(
                (tmp_path / cp for cp in _CONTENT_CANDIDATES if (tmp_path / cp).exists()),
                None,
            )
            if content_file is None:
                raise BuilderError(
                    "No content file found in HWPX (tried content.hml, section0.xml)",
                    detail=str(template),
                )

            tree = etree.parse(str(content_file))
            root = tree.getroot()

            _replace_placeholders(root, sections)

            tree.write(
                str(content_file),
                xml_declaration=True,
                encoding="UTF-8",
                pretty_print=False,
            )

            _pack(tmp_path, output)

        return output


def _unpack(hwpx: Path, dest: Path) -> None:
    try:
        with zipfile.ZipFile(hwpx, "r") as zf:
            zf.extractall(dest)
    except zipfile.BadZipFile as e:
        raise BuilderError("Invalid HWPX file (not a ZIP)", detail=str(e)) from e


def _pack(src: Path, output: Path) -> None:
    with zipfile.ZipFile(output, "w", zipfile.ZIP_DEFLATED) as zf:
        # mimetype must be first and uncompressed per OPC spec
        mimetype = src / "mimetype"
        if mimetype.exists():
            zf.write(mimetype, "mimetype", compress_type=zipfile.ZIP_STORED)

        for file in sorted(src.rglob("*")):
            if not file.is_file():
                continue
            if file.name == "mimetype":
                continue
            zf.write(file, file.relative_to(src))


def _replace_placeholders(root, sections: dict[str, str]) -> None:
    from lxml import etree

    # Detect hp namespace from document root (supports both 2011 and 2012 variants)
    hp_ns = root.nsmap.get("hp", "http://www.hancom.co.kr/hwpml/2012/paragraph")
    hp_t = f"{{{hp_ns}}}t"
    hp_p = f"{{{hp_ns}}}p"

    for para in root.iter(hp_p):
        t_elements = para.findall(f".//{hp_t}")
        if not t_elements:
            continue

        full_text = "".join((el.text or "") for el in t_elements)
        match = PLACEHOLDER_RE.search(full_text)
        if not match:
            continue

        key = match.group(1)
        if key not in sections:
            continue

        replacement = sections[key]

        # Put replacement in first t element, clear the rest
        t_elements[0].text = PLACEHOLDER_RE.sub(replacement, full_text, count=1)
        for el in t_elements[1:]:
            el.text = ""
