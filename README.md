# docpilot

데이터 폴더와 템플릿을 입력하면 LLM이 내용을 파악해 완성된 문서를 생성하는 파이썬 라이브러리입니다.

## 특징

- **다양한 입력 소스** — TXT, MD, RST, CSV, PDF (OCR 폴백 포함), PPTX, 이미지(JPG/PNG 등)
- **다양한 출력 포맷** — HWPX, DOCX, PDF
- **LLM 교체 가능** — Claude · OpenAI · Gemini · Grok · Ollama, 동일 인터페이스
- **벡터 + 형태소 검색** — sqlite-vec 임베딩 검색 (기본), pgvector (선택), kiwipiepy 형태소 검색
- **템플릿 자동 생성** — 샘플 HWPX 문서에서 공통 섹션 구조 추출
- **LLM 벤치마크** — 여러 LLM의 매핑 결과를 나란히 비교

## 설치

```bash
pip install docpilot
```

기본 설치에 **Claude(Anthropic)가 포함**됩니다. 다른 LLM을 사용하려면 extras를 추가하세요.

```bash
pip install "docpilot[openai]"    # OpenAI GPT 사용
pip install "docpilot[gemini]"    # Google Gemini 사용
pip install "docpilot[postgres]"  # PostgreSQL + pgvector 사용 (대용량)
pip install "docpilot[openai,gemini,postgres]"  # 복합 설치
```

> **Note**: PDF OCR 기능은 시스템에 [Tesseract](https://github.com/tesseract-ocr/tesseract)와 [Poppler](https://poppler.freedesktop.org/)가 설치되어 있어야 합니다.

## LLM 제공자

docpilot은 5개 LLM 제공자를 지원합니다. `DocPilot(llm=...)` 또는 `DOCPILOT_LLM` 환경변수로 선택합니다.

| 제공자 | `llm=` 값 | 기본 모델 | 필요 환경변수 | 추가 패키지 |
|--------|-----------|-----------|--------------|-------------|
| Anthropic Claude | `"claude"` | `claude-sonnet-4-6` | `ANTHROPIC_API_KEY` | **기본 포함** |
| OpenAI | `"openai"` | `gpt-4o` | `OPENAI_API_KEY` | `[openai]` |
| Google Gemini | `"gemini"` | `gemini-2.0-flash` | `GEMINI_API_KEY` | `[gemini]` |
| xAI Grok | `"grok"` | `grok-3` | `XAI_API_KEY` | `[openai]` |
| Ollama (로컬) | `"ollama"` | `llama3.2` | 불필요 | `[openai]` |

### API 키 설정

프로젝트 루트에 `.env` 파일을 생성합니다 (`.env.example` 참고).

```bash
# 사용하는 LLM의 키만 설정하면 됩니다
ANTHROPIC_API_KEY=sk-ant-...
OPENAI_API_KEY=sk-...
GEMINI_API_KEY=AIza...
XAI_API_KEY=xai-...

# LLM 제공자 선택 (기본값: claude)
DOCPILOT_LLM=claude
```

코드에서 직접 전달하면 환경변수보다 우선합니다.

```python
pilot = DocPilot(llm="claude", api_key="sk-ant-...")
```

### 제공자별 사용 예시

```python
# Claude (기본 — 별도 패키지 설치 불필요)
pilot = DocPilot(llm="claude", api_key="sk-ant-...")

# OpenAI
pilot = DocPilot(llm="openai", api_key="sk-...")

# Gemini
pilot = DocPilot(llm="gemini", api_key="AIza...")

# Grok
pilot = DocPilot(llm="grok", api_key="xai-...")

# Ollama — 로컬 서버 사용, API 키 불필요
pilot = DocPilot(llm="ollama", model="llama3.2")
pilot = DocPilot(llm="ollama", model="mistral", base_url="http://192.168.0.10:11434/v1")
```

### 기본 모델 변경

```python
pilot = DocPilot(llm="claude", model="claude-opus-4-8")
pilot = DocPilot(llm="openai", model="gpt-4-turbo")
pilot = DocPilot(llm="gemini", model="gemini-1.5-pro")
pilot = DocPilot(llm="grok",   model="grok-3-mini")
pilot = DocPilot(llm="ollama", model="deepseek-r1:7b")
```

## 빠른 시작

```python
from docpilot import DocPilot

# ANTHROPIC_API_KEY 환경변수가 설정되어 있으면 인자 생략 가능
pilot = DocPilot()
pilot.index("./data")       # 데이터 폴더 인덱싱

pilot.generate(
    data_folder="./data",
    template="report",          # 내장 템플릿 이름 또는 파일 경로
    output="./output/report.hwpx",
)
```

## 데이터 인덱싱

지원 입력 파일 형식: `.txt`, `.md`, `.rst`, `.csv`, `.pdf`, `.pptx`, `.jpg`, `.png`, `.jpeg`, `.bmp`, `.tiff`

```python
pilot.index("./data")   # 폴더 내 모든 지원 파일을 재귀적으로 인덱싱
```

## 템플릿 작성 방법

HWPX / DOCX / PDF 템플릿에서 섹션 위치에 `{{섹션명}}` 플레이스홀더를 삽입합니다.

```
{{서론}}

{{연구 목적}}

{{결론}}
```

docpilot이 데이터 폴더의 내용을 읽어 각 섹션을 채웁니다.

## 내장 템플릿

설치 즉시 사용할 수 있는 한글(HWPX) 템플릿이 포함되어 있습니다. 이름으로 참조하면 됩니다.

| 이름 | 용도 | 주요 플레이스홀더 |
|------|------|-----------------|
| `report` | 일반 보고서 | 보고서 제목, 작성일, 작성자/부서, 섹션 제목, 본문 내용, 결론 |
| `gonmun` | 공문 | 기관명, 수신자, 경유, 제목, 본문1·2, 직위 성명, 시행번호 등 |
| `minutes` | 회의록 | 회의록 제목, 일시, 장소, 참석자, 안건, 논의, 결정 사항 |

```python
# 이름으로 내장 템플릿 사용
pilot.generate(
    data_folder="./data",
    template="report",        # 파일 경로 대신 이름 지정
    output="./output/report.hwpx",
)

# 사용 가능한 내장 템플릿 목록 확인
print(DocPilot.list_templates())
# {'report': '일반 보고서 — ...', 'gonmun': '공문 — ...', 'minutes': '회의록 — ...'}
```

## 템플릿 자동 생성

자신의 기존 문서에서 반복 구조를 분석해 새 템플릿을 생성할 수 있습니다. 여러 샘플 문서를 넣으면 공통 섹션 패턴을 추출해 `{{섹션명}}` 플레이스홀더가 삽입된 HWPX 템플릿을 만들어 줍니다.

```python
# 같은 형식의 기존 문서 여러 개를 분석해 나만의 템플릿 생성
pilot.generate_template(
    samples=["./archive/report_2023.hwpx", "./archive/report_2024.hwpx"],
    output="./templates/my_report.hwpx",   # 프로젝트 루트의 templates/ 폴더에 저장
)
```

`./templates/` 폴더에 저장하면 이후 파일 경로 없이 이름으로 바로 참조할 수 있습니다.

```python
# 이름으로 참조 (./templates/my_report.hwpx 자동 탐색)
pilot.generate(data_folder="./data", template="my_report", output="./out.hwpx")
```

> 템플릿 탐색 순서: 파일 경로 → 내장 이름(`report`/`gonmun`/`minutes`) → `./templates/` 폴더

공통 섹션 신뢰도가 낮으면 LLM 보조를 활성화해 더 정확하게 추출합니다.

```python
pilot.generate_template(samples=[...], output="./templates/my_report.hwpx", use_llm=True)
```

## 검색 방식

```python
from docpilot.search import exact, embedding, morpheme

# 키워드 정확 검색
results = exact.search("사업 계획")

# 벡터 유사도 검색 (OpenAI 임베딩 사용 예시)
from docpilot.search.embedding import openai_embed_fn  # pip install "docpilot[openai]" 필요
results = embedding.search("사업 계획", embed_fn=openai_embed_fn())

# 형태소 기반 검색 (kiwipiepy, 설치 패키지 추가 불필요)
results = morpheme.search("사업 계획")
```

## 데이터베이스 설정

기본값은 로컬 SQLite 파일입니다. 대용량 처리 시 PostgreSQL로 전환할 수 있습니다.

| 방식 | URL 형식 | 비고 |
|------|----------|------|
| SQLite (기본) | `sqlite:///./docpilot.db` | 서버 불필요, 로컬 파일 |
| PostgreSQL | `postgresql://user:pw@host:5432/dbname` | `pip install "docpilot[postgres]"` 필요 |

```python
pilot = DocPilot(
    llm="openai",
    api_key="sk-...",
    database_url="postgresql://user:pw@localhost:5432/docpilot",
)
```

## 벤치마크

동일한 데이터와 템플릿을 여러 LLM에 넣어 속도, 토큰 사용량, 섹션별 작성 내용을 나란히 비교합니다. `mappers`에 넣은 LLM 수만큼 실제 API가 호출되므로 각 LLM의 API 키와 패키지가 준비되어 있어야 합니다.

```python
from docpilot.mapping import ClaudeMapper, OpenAIMapper, GeminiMapper
from docpilot.mapping.openai_compat import GrokMapper, OllamaMapper

report = pilot.benchmark(
    data_folder="./data",
    template="./templates/report.hwpx",
    output="./output/result.hwpx",
    mappers={
        "claude": ClaudeMapper(),
        "openai": OpenAIMapper(),
        "gemini": GeminiMapper(),
        "grok":   GrokMapper(),
        "ollama": OllamaMapper(model="llama3.2"),
    },
)
print(report)
```

출력 예시:

```
모델                  처리시간(s)    입력토큰    출력토큰      총토큰  상태
--------------------------------------------------------------------
claude                      2.31      1200        400        1600  OK
openai                      1.85      1180        380        1560  OK
gemini                      0.00         0          0           0  오류: API key missing
--------------------------------------------------------------------

## 섹션별 내용 비교

### 결론
[claude]
본 보고서는 ...

[openai]
종합적으로 검토한 결과 ...
```

API 키 누락이나 호출 실패가 발생한 LLM은 오류 상태로 표시되고, 나머지 LLM의 결과는 정상 출력됩니다.

## 예외 처리

모든 예외는 `DocPilotError`를 상속합니다.

```python
from docpilot.exceptions import (
    DocPilotError,
    IngestionError,
    MappingError,
    BuilderError,
    SearchError,
    TemplateError,
)

try:
    pilot.generate(...)
except MappingError as e:
    print(e.detail)   # 상세 오류 메시지
except DocPilotError as e:
    print(e)
```

## 라이선스

MIT
