from __future__ import annotations

import json
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from docpilot.ingestion.models import IngestedDocument


@dataclass
class TemplateSection:
    name: str
    description: str = ""


@dataclass
class MappingResult:
    sections: dict[str, str]
    model: str
    input_tokens: int
    output_tokens: int
    elapsed_seconds: float
    metadata: dict = field(default_factory=dict)

    @property
    def total_tokens(self) -> int:
        return self.input_tokens + self.output_tokens


def merge_documents(docs: list[IngestedDocument]) -> str:
    """Combine multiple IngestedDocuments into a single labelled string."""
    parts: list[str] = []
    for doc in docs:
        label = f"[출처: {doc.source.name}]"
        parts.append(f"{label}\n{doc.content.strip()}")
    return "\n\n".join(parts)


class BaseLLMMapper(ABC):
    """Abstract interface for LLM-based content-to-template mappers."""

    @abstractmethod
    def map(
        self,
        content: str | list[IngestedDocument],
        sections: list[TemplateSection],
    ) -> MappingResult:
        """
        Map source content into template sections.

        content: plain text string, or a list of IngestedDocuments to merge automatically
        sections: list of template sections to fill
        Returns: MappingResult with generated content per section
        """

    def _resolve_content(self, content: str | list[IngestedDocument]) -> str:
        if isinstance(content, str):
            return content
        return merge_documents(content)

    def _build_prompt(self, content: str, sections: list[TemplateSection]) -> str:
        section_list = "\n".join(
            f'- "{s.name}": {s.description}' if s.description else f'- "{s.name}"'
            for s in sections
        )
        section_keys = json.dumps([s.name for s in sections], ensure_ascii=False)
        example_obj = json.dumps(
            {"sections": {s.name: "..." for s in sections}},
            ensure_ascii=False,
            indent=2,
        )
        return f"""다음 소스 데이터를 읽고, 주어진 모든 섹션에 들어갈 내용을 한국어로 작성하세요.

## 소스 데이터
{content}

## 작성 규칙
- 아래 섹션 목록의 모든 항목을 빠짐없이 채워야 합니다.
- 소스 데이터가 여러 출처로 구성된 경우, 모든 출처를 종합하여 작성하세요.
- 소스 데이터에 해당 섹션의 내용이 불충분하면, 문맥상 가장 적절한 내용으로 작성하세요.
- 각 섹션 내용은 완성된 문장으로 작성하세요.

## 채워야 할 섹션
{section_list}

## 출력 형식
반드시 아래 JSON 형식으로만 응답하세요. JSON 앞뒤로 다른 텍스트를 포함하지 마세요.
섹션 키는 다음 목록과 정확히 일치해야 합니다: {section_keys}

{example_obj}"""

    def _parse_response(self, raw: str, sections: list[TemplateSection]) -> dict[str, str]:
        from docpilot.exceptions import MappingError

        try:
            start = raw.index("{")
            end = raw.rindex("}") + 1
            data = json.loads(raw[start:end])
            result = data.get("sections", {})
        except (ValueError, json.JSONDecodeError) as e:
            raise MappingError("Failed to parse LLM response as JSON", detail=raw[:200]) from e

        missing = [s.name for s in sections if s.name not in result]
        if missing:
            raise MappingError(
                "LLM response missing sections",
                detail=", ".join(missing),
            )

        return {s.name: result[s.name] for s in sections}
