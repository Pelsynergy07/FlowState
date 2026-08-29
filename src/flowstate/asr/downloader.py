"""Background model download for onboarding, with a real progress bar.

huggingface_hub's snapshot_download doesn't expose a stable byte-progress
callback across versions, so instead of depending on an internal API we
poll how many bytes have landed on disk against the model's known
approximate size. That's honest enough for a progress bar and won't break
if huggingface_hub's internals change.
"""

from __future__ import annotations

import logging
import threading
from pathlib import Path

from PySide6.QtCore import QObject, QThread, Signal

from . import models
from .. import paths

logger = logging.getLogger("flowstate.asr.downloader")


def _dir_size(path: Path) -> int:
    if not path.exists():
        return 0
    return sum(f.stat().st_size for f in path.rglob("*") if f.is_file())


def download_dir_with_progress(
    target_dir: Path,
    expected_bytes: int,
    do_download,
    on_progress=None,
) -> None:
    """Runs do_download() (a blocking, no-arg callable that downloads into
    target_dir) while polling target_dir's total size against
    expected_bytes to estimate percent complete, emitting to on_progress
    every 0.5s. Blocking -- call from a background thread, not the UI
    thread. Works regardless of exactly which filenames/temp-file scheme
    the download uses internally, since it sums everything under
    target_dir rather than watching one specific path."""
    target_dir.mkdir(parents=True, exist_ok=True)
    stop_event = threading.Event()

    def poll() -> None:
        while not stop_event.is_set():
            current = _dir_size(target_dir)
            pct = min(99, int(current / expected_bytes * 100)) if expected_bytes > 0 else 0
            if on_progress:
                on_progress(pct)
            stop_event.wait(0.5)

    poll_thread = threading.Thread(target=poll, daemon=True)
    poll_thread.start()
    try:
        do_download()
    finally:
        stop_event.set()
        poll_thread.join(timeout=1)
    if on_progress:
        on_progress(100)


class ModelDownloadWorker(QObject):
    progress = Signal(int)  # 0-100, estimated
    finished = Signal(str)  # local directory the model was downloaded into
    failed = Signal(str)  # error message

    def __init__(self, model_id: str):
        super().__init__()
        self._model_id = model_id

    def run(self) -> None:
        from huggingface_hub import snapshot_download

        spec = models.get_model_spec(self._model_id)
        target_dir = paths.models_dir() / spec.id
        target_dir.mkdir(parents=True, exist_ok=True)
        expected_bytes = max(spec.approx_size_mb, 1) * 1024 * 1024

        stop_event = threading.Event()

        def poll() -> None:
            while not stop_event.is_set():
                current = _dir_size(target_dir)
                pct = min(99, int(current / expected_bytes * 100))
                self.progress.emit(pct)
                stop_event.wait(0.5)

        poll_thread = threading.Thread(target=poll, daemon=True)
        poll_thread.start()

        try:
            local_path = snapshot_download(repo_id=spec.ct2_repo, local_dir=str(target_dir))
        except Exception as exc:
            stop_event.set()
            logger.error("Model download failed for %s: %s", spec.id, exc, exc_info=True)
            self.failed.emit(str(exc))
            return

        stop_event.set()
        self.progress.emit(100)
        self.finished.emit(local_path)


def download_model_async(model_id: str) -> tuple[QThread, ModelDownloadWorker]:
    """Starts the download on a background QThread and returns (thread,
    worker). The caller must keep both alive and connect to the worker's
    signals; the thread quits itself on finished/failed."""
    thread = QThread()
    worker = ModelDownloadWorker(model_id)
    worker.moveToThread(thread)
    thread.started.connect(worker.run)
    worker.finished.connect(thread.quit)
    worker.failed.connect(thread.quit)
    thread.start()
    return thread, worker
