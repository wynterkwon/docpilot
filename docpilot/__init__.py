from __future__ import annotations

import atexit
import os
import re
import tempfile
import zipfile
from pathlib import Path

from dotenv import load_dotenv

from docpilot.exceptions import BuilderError, DocPilotError, MappingError

load_dotenv()

_PLACEHOLDER_RE = re.compile(r"\{\{(.+?)\}\}")

# Maps file extension → required extra (None = included in base install)
_EXT_EXTRAS: dict[str, str | None] = {
    ".txt":  None,
    ".md":   None,
    ".rst":  None,
    ".csv":  None,
    ".hwpx": None,
    ".pdf":  "pdf",
    ".pptx": "pptx",
    ".jpg":  "image",
    ".jpeg": "image",
    ".png":  "image",
    ".tiff": "image",
    ".tif":  "image",
    ".bmp":  "image",
    ".webp": "image",
}


def suggest_extras(folder: str | Path) -> dict:
    """
    Scan a data folder and suggest which docpilot extras to install.

    Returns a dict with:
      found          — {extension: file_count} for all files found
      unsupported    — {extension: file_count} for files docpilot cannot process
      required_extras — list of extras needed (e.g. ["pdf", "pptx"])
      install_command — ready-to-run pip command, or None if nothing extra needed
    """
    folder = Path(folder)
    if not folder.is_dir():
        raise DocPilotError("Not a directory", detail=str(folder))

    found: dict[str, int] = {}
    for file in folder.rglob("*"):
        if not file.is_file():
            continue
        ext = file.suffix.lower()
        found[ext] = found.get(ext, 0) + 1

    unsupported: dict[str, int] = {
        ext: count for ext, count in found.items() if ext not in _EXT_EXTRAS
    }

    required: list[str] = sorted({
        extra
        for ext in found
        if ext in _EXT_EXTRAS and (extra := _EXT_EXTRAS[ext]) is not None
    })

    install_command = (
        f'pip install "docpilot[{",".join(required)}]"' if required else None
    )

    return {
        "found": found,
        "unsupported": unsupported,
        "required_extras": required,
        "install_command": install_command,
    }
_BUILTIN_TEMPLATES = Path(__file__).parent / "templates"

_BUILTIN_METADATA: dict[str, str] = {
    "report":   "일반 보고서 — 보고서 제목, 섹션 본문, 결론",
    "gonmun":   "공문 — 수신자, 제목, 본문, 기관 정보",
    "minutes":  "회의록 — 제목, 일시, 참석자, 안건, 논의, 결정 사항",
    "proposal": "제안서 — 사업 개요, 추진 배경, 추진 근거",
}

_ASSEMBLED_CACHE: dict[str, Path] = {}


def _assemble_builtin_hwpx(name: str) -> Path:
    """Assemble a built-in HWPX template from base + per-template XML sources."""
    if name in _ASSEMBLED_CACHE:
        return _ASSEMBLED_CACHE[name]

    base_dir = _BUILTIN_TEMPLATES / "base"
    overlay_dir = _BUILTIN_TEMPLATES / name

    if not base_dir.exists() or not overlay_dir.exists():
        raise DocPilotError(
            f"Built-in template '{name}' not found",
            detail=f"Expected source at {overlay_dir}",
        )

    tmp = tempfile.NamedTemporaryFile(suffix=f"_{name}.hwpx", delete=False)
    tmp.close()
    tmp_path = Path(tmp.name)

    with zipfile.ZipFile(tmp_path, "w", zipfile.ZIP_DEFLATED) as zf:
        mimetype = base_dir / "mimetype"
        if mimetype.exists():
            zf.write(mimetype, "mimetype", compress_type=zipfile.ZIP_STORED)

        for file in sorted(base_dir.rglob("*")):
            if not file.is_file() or file.name == "mimetype":
                continue
            arcname = file.relative_to(base_dir)
            # overlay_dir files are named header.xml / section0.xml — placed in Contents/
            override = overlay_dir / file.name
            source = override if override.exists() else file
            zf.write(source, arcname.as_posix())

    _ASSEMBLED_CACHE[name] = tmp_path
    atexit.register(lambda p=tmp_path: p.unlink(missing_ok=True))
    return tmp_path


def _m(model: str | None) -> dict:
    return {"model": model} if model else {}


def _b(base_url: str | None) -> dict:
    return {"base_url": base_url} if base_url else {}


def _extract_placeholders(template_path: Path) -> list[str]:
    """Extract {{section}} placeholder names from a template file."""
    suffix = template_path.suffix.lower()

    if suffix == ".hwpx":
        with zipfile.ZipFile(template_path, "r") as zf:
            names = zf.namelist()
            candidates = [n for n in names if n.endswith("content.hml")]
            if not candidates:
                candidates = [n for n in names if n.endswith("section0.xml")]
            if not candidates:
                return []
            text = "".join(
                zf.read(c).decode("utf-8", errors="ignore") for c in candidates
            )
    elif suffix == ".docx":
        with zipfile.ZipFile(template_path, "r") as zf:
            text = zf.read("word/document.xml").decode("utf-8", errors="ignore")
    elif suffix == ".pdf":
        try:
            import pdfplumber
            with pdfplumber.open(template_path) as pdf:
                text = "\n".join(p.extract_text() or "" for p in pdf.pages)
        except Exception:
            return []
    else:
        return []

    seen: dict[str, None] = {}
    for match in _PLACEHOLDER_RE.finditer(text):
        seen[match.group(1)] = None
    return list(seen)


class DocPilot:
    """
    Main entry point for docpilot.

    pilot = DocPilot(llm="claude")
    pilot.index(data_folder="./data")
    pilot.generate(data_folder="./data", template="research_report", output="./out.hwpx")
    """

    def __init__(
        self,
        llm: str | None = None,
        api_key: str | None = None,
        model: str | None = None,
        base_url: str | None = None,
        database_url: str | None = None,
        embed_fn=None,
    ) -> None:
        self._llm = llm or os.environ.get("DOCPILOT_LLM", "claude")
        self._api_key = api_key
        self._embed_fn = embed_fn
        base_mapper = self._build_mapper(self._llm, api_key, model, base_url)

        from docpilot.mapping.rag import RagMapper
        self._mapper = base_mapper
        self._rag_mapper = RagMapper(base_mapper, embed_fn=embed_fn)

        from docpilot.db import client as db_client
        db_client.init(database_url)
        db_client.create_tables()

    def index(self, data_folder: str | Path) -> list[int]:
        """Ingest and index all supported files in a folder."""
        from docpilot.db import indexer
        return indexer.index_folder(data_folder, embed_fn=self._embed_fn)

    def generate(
        self,
        data_folder: str | Path,
        template: str | Path,
        output: str | Path,
        reindex: bool = False,
    ) -> Path:
        """
        Full pipeline: index → search → map → build.

        template: file path (.hwpx/.docx/.pdf) or built-in template name.
        output:   destination file path — extension determines builder.
        reindex:  re-index data_folder even if already indexed.
        """
        template_path = self._resolve_template(template)
        output_path = Path(output)

        from docpilot.db import indexer
        indexer.index_folder(data_folder, embed_fn=self._embed_fn, force=reindex)

        from docpilot.mapping.base import TemplateSection
        sections = [TemplateSection(name=s) for s in _extract_placeholders(template_path)]
        if not sections:
            raise DocPilotError(
                "No {{placeholders}} found in template",
                detail=str(template_path),
            )

        mapping_result = self._rag_mapper.map(sections)

        builder = self._build_builder(output_path)
        return builder.build(template_path, mapping_result.sections, output_path)

    def generate_template(
        self,
        samples: list[str | Path],
        output: str | Path,
        use_llm: bool | None = None,
    ) -> Path:
        """Generate an HWPX template from sample documents."""
        from docpilot.template_generator import generate
        return generate(
            samples=samples,
            output=output,
            use_llm=use_llm,
            llm_mapper=self._mapper if use_llm else None,
        )

    def benchmark(
        self,
        data_folder: str | Path,
        template: str | Path,
        output: str | Path,
        mappers: dict | None = None,
    ) -> str:
        """Run mapping benchmark across multiple LLM mappers and return report."""
        from docpilot.mapping import benchmark, ClaudeMapper, OpenAIMapper
        from docpilot.mapping.base import TemplateSection

        template_path = self._resolve_template(template)
        self.index(data_folder)

        template_sections = [TemplateSection(name=s) for s in _extract_placeholders(template_path)]
        content = self._rag_mapper.retrieve_content(template_sections)

        if mappers is None:
            mappers = {"claude": ClaudeMapper(api_key=self._api_key)}
            oai_key = os.environ.get("OPENAI_API_KEY")
            if oai_key:
                mappers["openai"] = OpenAIMapper(api_key=oai_key)

        results = benchmark.run(content, template_sections, mappers)
        return benchmark.report(results)

    def _resolve_template(self, template: str | Path) -> Path:
        path = Path(template)
        if path.exists():
            return path

        name = str(template)
        if name in _BUILTIN_METADATA:
            return _assemble_builtin_hwpx(name)

        for ext in (".hwpx", ".docx", ".pdf"):
            # 1) package built-ins
            candidate = _BUILTIN_TEMPLATES / f"{template}{ext}"
            if candidate.exists():
                return candidate
            # 2) project-local ./templates/ directory
            local = Path("templates") / f"{template}{ext}"
            if local.exists():
                return local

        raise DocPilotError("Template not found", detail=str(template))

    @staticmethod
    def list_templates() -> dict[str, str]:
        """Return built-in template names and their descriptions."""
        return dict(_BUILTIN_METADATA)

    @staticmethod
    def suggest_extras(folder: str | Path) -> dict:
        """Scan a data folder and suggest which docpilot extras to install."""
        return suggest_extras(folder)

    @staticmethod
    def _build_mapper(llm: str, api_key: str | None, model: str | None, base_url: str | None):
        from docpilot.mapping import ClaudeMapper, OpenAIMapper, GeminiMapper
        from docpilot.mapping.openai_compat import GrokMapper, OllamaMapper

        match llm.lower():
            case "claude":
                return ClaudeMapper(api_key=api_key, **(_m(model)))
            case "openai":
                return OpenAIMapper(api_key=api_key, **(_m(model)))
            case "gemini":
                return GeminiMapper(api_key=api_key, **(_m(model)))
            case "grok":
                return GrokMapper(api_key=api_key, **(_m(model)))
            case "ollama":
                return OllamaMapper(**(_m(model)), **(_b(base_url)))
            case _:
                raise MappingError(
                    f"Unknown LLM '{llm}'. "
                    "Supported: claude, openai, gemini, grok, ollama"
                )

    @staticmethod
    def _build_builder(output: Path):
        from docpilot.builder import HwpxBuilder, PdfBuilder, DocxBuilder

        match output.suffix.lower():
            case ".hwpx":
                return HwpxBuilder()
            case ".pdf":
                return PdfBuilder()
            case ".docx":
                return DocxBuilder()
            case _:
                raise BuilderError(
                    f"Unsupported output format '{output.suffix}'",
                    detail="Supported: .hwpx, .pdf, .docx",
                )
