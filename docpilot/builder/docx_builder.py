from __future__ import annotations

from pathlib import Path

from docpilot.builder.base import BaseBuilder, PLACEHOLDER_RE
from docpilot.exceptions import BuilderError


class DocxBuilder(BaseBuilder):
    def build(
        self,
        template: str | Path,
        sections: dict[str, str],
        output: str | Path,
    ) -> Path:
        template, output = self._validate_paths(template, output)

        if template.suffix.lower() != ".docx":
            raise BuilderError(f"Expected .docx template, got '{template.suffix}'")

        try:
            import docx
        except ImportError as e:
            raise BuilderError("python-docx is required: pip install python-docx") from e

        try:
            doc = docx.Document(str(template))
        except Exception as e:
            raise BuilderError("Failed to open DOCX template", detail=str(e)) from e

        for para in doc.paragraphs:
            _replace_in_paragraph(para, sections)

        for table in doc.tables:
            for row in table.rows:
                for cell in row.cells:
                    for para in cell.paragraphs:
                        _replace_in_paragraph(para, sections)

        try:
            doc.save(str(output))
        except Exception as e:
            raise BuilderError("Failed to save DOCX", detail=str(e)) from e

        return output


def _replace_in_paragraph(para, sections: dict[str, str]) -> None:
    full_text = "".join(run.text for run in para.runs)
    match = PLACEHOLDER_RE.search(full_text)
    if not match:
        return

    key = match.group(1)
    if key not in sections:
        return

    replacement = PLACEHOLDER_RE.sub(sections[key], full_text)

    # Preserve formatting of first run, clear the rest
    if para.runs:
        para.runs[0].text = replacement
        for run in para.runs[1:]:
            run.text = ""
