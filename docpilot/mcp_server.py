from __future__ import annotations

import os

from mcp.server.fastmcp import FastMCP

_pilot = None


def _get_pilot():
    global _pilot
    if _pilot is None:
        from docpilot import DocPilot
        _pilot = DocPilot(
            llm=os.environ.get("DOCPILOT_LLM", "claude"),
            api_key=os.environ.get("ANTHROPIC_API_KEY"),
            model=os.environ.get("DOCPILOT_MODEL") or None,
            database_url=os.environ.get("DOCPILOT_DATABASE_URL") or None,
        )
    return _pilot


mcp = FastMCP(
    "docpilot",
    instructions=(
        "docpilot는 데이터 폴더와 템플릿으로 HWPX / PDF / DOCX 문서를 자동 생성합니다. "
        "내장 템플릿: report(일반 보고서), gonmun(공문), minutes(회의록), proposal(제안서). "
        "사용 전 ANTHROPIC_API_KEY 환경 변수가 설정되어 있어야 합니다."
    ),
)


@mcp.tool()
def generate(
    data_folder: str,
    template: str,
    output: str,
    reindex: bool = False,
    extra_instructions: str | None = None,
    instructions_doc: str | None = None,
) -> str:
    """데이터 폴더와 템플릿으로 문서를 생성합니다.

    Args:
        data_folder: 데이터 파일이 있는 폴더 경로 (절대 경로 권장)
        template: 템플릿 파일 경로 또는 내장 템플릿 이름 (report / gonmun / minutes / proposal)
        output: 출력 파일 경로 — 확장자가 출력 형식을 결정합니다 (.hwpx / .pdf / .docx)
        reindex: True이면 데이터 폴더를 강제로 재인덱싱합니다 (기본값: False)
        extra_instructions: LLM 프롬프트에 추가할 작성 지침 문자열
        instructions_doc: 작성 지침으로 사용할 파일 경로 (RFP·제안요청서 등). 파일 내용이 자동으로 지침에 추가됩니다.
    """
    result = _get_pilot().generate(
        data_folder=data_folder,
        template=template,
        output=output,
        reindex=reindex,
        extra_instructions=extra_instructions,
        instructions_doc=instructions_doc,
    )
    return (
        f"문서 생성 완료: {result.path}\n"
        f"모델: {result.model} | "
        f"입력 {result.input_tokens:,} + 출력 {result.output_tokens:,} = "
        f"총 {result.total_tokens:,} 토큰 | "
        f"소요 {result.elapsed_seconds:.1f}초"
    )


@mcp.tool()
def generate_template(
    samples: list[str],
    output: str,
    use_llm: bool | None = None,
) -> str:
    """샘플 HWPX 문서들을 분석하여 재사용 가능한 템플릿을 생성합니다.

    Args:
        samples: 분석할 샘플 HWPX 파일 경로 목록 (2개 이상 권장)
        output: 생성할 템플릿 파일 경로 (.hwpx)
        use_llm: LLM 보조 사용 여부 (None이면 공통 구조 신뢰도에 따라 자동 결정)
    """
    result_path = _get_pilot().generate_template(
        samples=samples,
        output=output,
        use_llm=use_llm,
    )
    return f"템플릿 생성 완료: {result_path}"


@mcp.tool()
def estimate_cost(
    data_folder: str,
    template: str,
) -> str:
    """문서 생성 전 예상 API 토큰 비용을 추정합니다. 실제 문서는 생성하지 않습니다.

    데이터 폴더 인덱싱과 RAG 검색까지는 수행하지만, LLM 완성 호출 없이
    token-counting API만 사용하므로 비용이 거의 발생하지 않습니다.

    Args:
        data_folder: 데이터 파일이 있는 폴더 경로
        template: 템플릿 파일 경로 또는 내장 템플릿 이름
    """
    return _get_pilot().estimate_cost(
        data_folder=data_folder,
        template=template,
    )


def main() -> None:
    mcp.run()


if __name__ == "__main__":
    main()
