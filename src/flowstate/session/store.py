"""Session folders on disk, and the 7-day / 500 MB retention sweep.

Timestamps here are local time, not UTC: the folder name doubles as a
user-visible identifier in the History tab, and showing it in UTC while
the app's own log file uses local time was confusing enough to be a
reported bug. A 7-day retention cutoff doesn't need UTC precision.
"""

from __future__ import annotations

import shutil
from datetime import datetime, timedelta
from pathlib import Path
from uuid import uuid4

from .. import paths
from .model import Session

RETENTION_DAYS = 7
MAX_TOTAL_BYTES = 500 * 1024 * 1024


def create_session(source_app: str | None = None) -> Session:
    now = datetime.now()
    session_id = f"{now.strftime('%Y%m%d-%H%M%S')}-{uuid4().hex[:6]}"
    folder = paths.sessions_dir() / session_id
    folder.mkdir(parents=True, exist_ok=False)
    return Session(id=session_id, created_at=now, folder=folder, source_app=source_app)


def save_session(session: Session) -> None:
    session.transcript_path.write_text(session.transcript, encoding="utf-8")
    lines = [
        f"# FlowState session {session.id}",
        "",
        f"- Created: {session.created_at.isoformat()}",
        f"- Source app: {session.source_app or 'unknown'}",
        f"- Images: {len(session.image_paths)}",
        "",
        "## Transcript",
        "",
        session.transcript,
    ]
    session.context_md_path.write_text("\n".join(lines), encoding="utf-8")


def list_sessions() -> list[Path]:
    """Session folders, newest first."""
    root = paths.sessions_dir()
    folders = [p for p in root.iterdir() if p.is_dir()]
    return sorted(folders, key=lambda p: p.name, reverse=True)


def _folder_size(path: Path) -> int:
    return sum(f.stat().st_size for f in path.rglob("*") if f.is_file())


def _parse_created(folder: Path) -> datetime | None:
    try:
        date_part, time_part, _ = folder.name.split("-", 2)
        return datetime.strptime(date_part + time_part, "%Y%m%d%H%M%S")
    except (ValueError, IndexError):
        return None


def enforce_retention(now: datetime | None = None) -> list[Path]:
    """Delete sessions older than RETENTION_DAYS, then, if the sessions
    folder is still over MAX_TOTAL_BYTES, delete oldest-first until it
    fits under the cap. Returns the folders that were deleted."""
    now = now or datetime.now()
    cutoff = now - timedelta(days=RETENTION_DAYS)
    deleted: list[Path] = []

    kept: list[Path] = []
    for folder in list_sessions():  # newest first
        created = _parse_created(folder)
        if created is not None and created < cutoff:
            shutil.rmtree(folder, ignore_errors=True)
            deleted.append(folder)
        else:
            kept.append(folder)

    total = sum(_folder_size(f) for f in kept)
    while total > MAX_TOTAL_BYTES and kept:
        oldest = kept.pop()  # kept is newest-first, so the tail is oldest
        total -= _folder_size(oldest)
        shutil.rmtree(oldest, ignore_errors=True)
        deleted.append(oldest)

    return deleted
