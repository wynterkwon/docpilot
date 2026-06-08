"""
docpilot 빠른 테스트 스크립트

사용법:
  1. DATA_FOLDER  — 인덱싱할 문서/이미지 폴더 경로
  2. SAMPLES      — 템플릿 생성에 쓸 샘플 HWPX 파일 목록 (없으면 내장 템플릿 사용)
  3. OUTPUT       — 결과 파일 경로
  4. LLM / API_KEY 설정 후 실행: python run.py
"""

import os
from pathlib import Path
from docpilot import DocPilot

# ── 설정 ──────────────────────────────────────────────
DATA_FOLDER = "./data"          # 문서·이미지가 있는 폴더
OUTPUT      = "./output/result.hwpx"

# 샘플 HWPX가 있으면 템플릿 자동 생성, 없으면 내장 템플릿(report) 사용
SAMPLES = [
    # "./samples/report_2023.hwpx",
    # "./samples/report_2024.hwpx",
]

LLM     = os.environ.get("DOCPILOT_LLM", "claude")
API_KEY = os.environ.get("ANTHROPIC_API_KEY")   # 다른 LLM이면 해당 키로 변경

# 작성 지침 문서 (RFP·제안요청서 등) — 파일 내용이 자동으로 LLM 지침에 추가됨
# 문자열로 직접 지침을 쓰려면 EXTRA_INSTRUCTIONS 사용
INSTRUCTIONS_DOC = None   # 예: "./첨부+3.hwpx"
EXTRA_INSTRUCTIONS = None # 예: "경어체로 작성하세요."
# ──────────────────────────────────────────────────────


def main():
    Path(OUTPUT).parent.mkdir(parents=True, exist_ok=True)

    from docpilot import suggest_extras
    check = suggest_extras(DATA_FOLDER)
    if check["required_extras"]:
        print(f"[필요 패키지] {check['install_command']}")
    if check["unsupported"]:
        exts = ", ".join(f"{e}({n}개)" for e, n in check["unsupported"].items())
        print(f"[경고] 처리 불가 파일 형식 무시됨: {exts}")

    print(f"[1/3] DocPilot 초기화 (llm={LLM})")
    pilot = DocPilot(llm=LLM, api_key=API_KEY)

    # 템플릿 결정
    if SAMPLES:
        print(f"[2/3] 샘플 {len(SAMPLES)}개에서 템플릿 생성 중...")
        Path("./templates").mkdir(exist_ok=True)
        template = pilot.generate_template(
            samples=SAMPLES,
            output="./templates/my_template.hwpx",
        )
        print(f"      → 템플릿 저장: {template}")
        template_arg = "my_template"
    else:
        print("[2/3] 샘플 없음 — 내장 템플릿 'report' 사용")
        template_arg = "report"

    print(f"[3/3] 문서 생성 중... (데이터: {DATA_FOLDER})")
    output = pilot.generate(
        data_folder=DATA_FOLDER,
        template=template_arg,
        output=OUTPUT,
        extra_instructions=EXTRA_INSTRUCTIONS,
        instructions_doc=INSTRUCTIONS_DOC,
    )
    print(f"\n완료: {output}")


if __name__ == "__main__":
    main()
