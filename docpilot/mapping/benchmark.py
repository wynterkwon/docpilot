from __future__ import annotations

from dataclasses import dataclass, field

from docpilot.mapping.base import BaseLLMMapper, MappingResult, TemplateSection


@dataclass
class BenchmarkResult:
    model: str
    elapsed_seconds: float
    input_tokens: int
    output_tokens: int
    total_tokens: int
    sections: dict[str, str]
    error: str | None = field(default=None)


def run(
    content: str,
    sections: list[TemplateSection],
    mappers: dict[str, BaseLLMMapper],
) -> list[BenchmarkResult]:
    """
    Run the same mapping task across multiple mappers and return results.

    mappers: {"claude": ClaudeMapper(...), "openai": OpenAIMapper(...)}
    Failed mappers are recorded with an error message instead of raising.
    """
    results: list[BenchmarkResult] = []
    for name, mapper in mappers.items():
        try:
            result: MappingResult = mapper.map(content, sections)
            results.append(
                BenchmarkResult(
                    model=name,
                    elapsed_seconds=result.elapsed_seconds,
                    input_tokens=result.input_tokens,
                    output_tokens=result.output_tokens,
                    total_tokens=result.total_tokens,
                    sections=result.sections,
                )
            )
        except Exception as e:
            results.append(
                BenchmarkResult(
                    model=name,
                    elapsed_seconds=0.0,
                    input_tokens=0,
                    output_tokens=0,
                    total_tokens=0,
                    sections={},
                    error=str(e),
                )
            )
    return results


def report(results: list[BenchmarkResult]) -> str:
    """Return a plain-text comparison table of benchmark results."""
    if not results:
        return "No results."

    col_w = 18
    header = (
        f"{'모델':<{col_w}}"
        f"{'처리시간(s)':>12}"
        f"{'입력토큰':>10}"
        f"{'출력토큰':>10}"
        f"{'총토큰':>10}"
        f"  상태"
    )
    separator = "-" * len(header)

    rows = [header, separator]
    for r in results:
        status = f"  오류: {r.error}" if r.error else "  OK"
        rows.append(
            f"{r.model:<{col_w}}"
            f"{r.elapsed_seconds:>12.2f}"
            f"{r.input_tokens:>10}"
            f"{r.output_tokens:>10}"
            f"{r.total_tokens:>10}"
            f"{status}"
        )

    rows.append(separator)

    successful = [r for r in results if not r.error]
    if not successful:
        rows.append("\n모든 LLM 호출이 실패했습니다.")
        return "\n".join(rows)

    rows.append("\n## 섹션별 내용 비교\n")
    all_sections = successful[0].sections.keys()
    for section in all_sections:
        rows.append(f"### {section}")
        for r in successful:
            rows.append(f"[{r.model}]")
            rows.append(r.sections.get(section, "(없음)"))
            rows.append("")

    return "\n".join(rows)
