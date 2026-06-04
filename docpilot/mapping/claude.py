from __future__ import annotations

import os
import time

from docpilot.exceptions import MappingError
from docpilot.mapping.base import BaseLLMMapper, MappingResult, TemplateSection

DEFAULT_MODEL = "claude-sonnet-4-6"


class ClaudeMapper(BaseLLMMapper):
    def __init__(
        self,
        api_key: str | None = None,
        model: str = DEFAULT_MODEL,
        max_tokens: int = 8096,
    ) -> None:
        self._model = model
        self._max_tokens = max_tokens
        self._api_key = api_key or os.environ.get("ANTHROPIC_API_KEY")
        if not self._api_key:
            raise MappingError(
                "Anthropic API key not provided",
                detail="Pass api_key or set ANTHROPIC_API_KEY env var",
            )

    def map(self, content: str, sections: list[TemplateSection]) -> MappingResult:
        try:
            import anthropic
        except ImportError as e:
            raise MappingError("anthropic SDK required: pip install anthropic") from e

        client = anthropic.Anthropic(api_key=self._api_key)
        prompt = self._build_prompt(content, sections)

        start = time.perf_counter()
        try:
            response = client.messages.create(
                model=self._model,
                max_tokens=self._max_tokens,
                messages=[{"role": "user", "content": prompt}],
            )
        except Exception as e:
            raise MappingError("Claude API call failed", detail=str(e)) from e
        elapsed = time.perf_counter() - start

        raw = response.content[0].text
        mapped = self._parse_response(raw, sections)

        return MappingResult(
            sections=mapped,
            model=self._model,
            input_tokens=response.usage.input_tokens,
            output_tokens=response.usage.output_tokens,
            elapsed_seconds=elapsed,
        )
