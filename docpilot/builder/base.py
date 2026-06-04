from __future__ import annotations

import re
from abc import ABC, abstractmethod
from pathlib import Path

PLACEHOLDER_RE = re.compile(r"\{\{(.+?)\}\}")


class BaseBuilder(ABC):
    """
    Abstract document builder.

    Templates use {{섹션명}} placeholders in their text content.
    The builder finds each placeholder and replaces it with mapped content.
    """

    @abstractmethod
    def build(
        self,
        template: str | Path,
        sections: dict[str, str],
        output: str | Path,
    ) -> Path:
        """
        Generate a document from a template and mapped section content.

        Returns the path of the generated file.
        """

    def _validate_paths(
        self, template: str | Path, output: str | Path
    ) -> tuple[Path, Path]:
        from docpilot.exceptions import BuilderError

        template = Path(template)
        output = Path(output)

        if not template.exists():
            raise BuilderError("Template file not found", detail=str(template))

        output.parent.mkdir(parents=True, exist_ok=True)
        return template, output
