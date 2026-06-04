from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class IngestedDocument:
    source: Path
    content: str
    mime_type: str
    metadata: dict = field(default_factory=dict)
