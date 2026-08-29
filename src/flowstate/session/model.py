from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path


@dataclass
class Session:
    """One dictation session: audio in, cleaned transcript (and any circled
    screenshots) out. Lives on disk as a folder under paths.sessions_dir()."""

    id: str  # "YYYYMMDD-HHMMSS-xxxxxx"
    created_at: datetime
    folder: Path
    transcript: str = ""
    image_paths: list[Path] = field(default_factory=list)
    source_app: str | None = None  # foreground window title at capture time

    @property
    def transcript_path(self) -> Path:
        return self.folder / "transcript.txt"

    @property
    def context_md_path(self) -> Path:
        return self.folder / "context.md"
