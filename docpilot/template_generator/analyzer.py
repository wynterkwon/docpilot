from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from docpilot.exceptions import TemplateError
from docpilot.template_generator.extractor import ParagraphInfo, extract

# Default threshold: at least 70% of sample documents must share a section
DEFAULT_CONFIDENCE_THRESHOLD = 0.7


@dataclass
class AnalysisResult:
    common_sections: list[str]
    confidence: float
    per_document_sections: dict[str, list[str]] = field(default_factory=dict)
    total_documents: int = 0


def analyze(
    samples: list[str | Path],
    confidence_threshold: float = DEFAULT_CONFIDENCE_THRESHOLD,
) -> AnalysisResult:
    """
    Analyze multiple HWPX sample documents to extract common section structure.

    confidence: fraction of documents that share each detected section heading.
    Only sections meeting the threshold are included in common_sections.
    """
    if not samples:
        raise TemplateError("At least one sample document is required")

    per_doc: dict[str, list[str]] = {}

    for path in samples:
        path = Path(path)
        paragraphs = extract(path)
        headings = [p.text for p in paragraphs if p.is_heading_candidate]
        per_doc[str(path)] = headings

    total = len(per_doc)
    heading_counts: dict[str, int] = {}

    for headings in per_doc.values():
        for h in set(headings):
            heading_counts[h] = heading_counts.get(h, 0) + 1

    common = [
        h for h, count in heading_counts.items()
        if count / total >= confidence_threshold
    ]

    if common:
        confidence = sum(heading_counts[h] for h in common) / (len(common) * total)
    elif heading_counts:
        best_count = max(heading_counts.values())
        confidence = best_count / total
    else:
        confidence = 0.0

    # Preserve document order for common sections
    ordered = _order_sections(common, per_doc)

    return AnalysisResult(
        common_sections=ordered,
        confidence=confidence,
        per_document_sections=per_doc,
        total_documents=total,
    )


def _order_sections(sections: list[str], per_doc: dict[str, list[str]]) -> list[str]:
    """Order sections by their average position across documents."""
    if not sections:
        return []

    section_set = set(sections)
    position_sum: dict[str, float] = {s: 0.0 for s in sections}
    count: dict[str, int] = {s: 0 for s in sections}

    for headings in per_doc.values():
        total = len(headings)
        for i, h in enumerate(headings):
            if h in section_set:
                position_sum[h] += i / max(total, 1)
                count[h] += 1

    avg_pos = {
        s: position_sum[s] / count[s] if count[s] else 0.0
        for s in sections
    }
    return sorted(sections, key=lambda s: avg_pos[s])
