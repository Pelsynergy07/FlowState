"""First-run setup: a short welcome, then a one-time background preload
of the AI models. This is what makes every future recording fast instead
of stalling on the first real dictation while a model downloads/loads.

Reports real download percentage (not just an indeterminate spinner):
huggingface_hub doesn't expose a stable byte-progress callback across
versions, so instead of depending on an internal API, download_dir_with_
progress (asr/downloader.py) polls how many bytes have actually landed on
disk against the model's known approximate size. Without this, a fresh
install with a slow or flaky connection just showed a spinner with no way
to tell whether it was working or stuck -- which is exactly what happened
during testing on a second machine.
"""

from __future__ import annotations

from PySide6.QtCore import QObject, Qt, QThread, Signal
from PySide6.QtWidgets import QDialog, QLabel, QProgressBar, QPushButton, QVBoxLayout

from .. import paths
from .theme import build_stylesheet


class _PreloadWorker(QObject):
    status = Signal(str)
    progress = Signal(int)  # 0-100
    finished = Signal()
    failed = Signal(str)

    def __init__(self, controller):
        super().__init__()
        self._controller = controller

    def run(self) -> None:
        try:
            self._download_asr()
            self.status.emit("Loading the speech model...")
            self.progress.emit(0)
            self._controller._asr._load()  # fast now -- files are already on disk
            device = self._controller._asr.active_device
            model_id = self._controller._asr.active_model_id
            if device == "cuda":
                self.status.emit(f"Speech model ready -- using your GPU (CUDA, {model_id}) for fast transcription.")
            else:
                self.status.emit(
                    f"Speech model ready -- no compatible NVIDIA GPU/CUDA found, so FlowState is "
                    f"using a smaller, CPU-friendly model ({model_id}) instead. Transcription will "
                    "be noticeably slower than on a GPU, but still fully local and private. You can "
                    "check this again anytime in Settings -> Model."
                )
            self.progress.emit(100)

            self._download_formatter()
            self.status.emit("Loading the smart-formatting model...")
            self.progress.emit(0)
            self._controller._pipeline.preload()
            self.status.emit("Smart-formatting model ready.")
            self.progress.emit(100)
        except Exception as exc:
            self.failed.emit(str(exc))
            return
        self.finished.emit()

    def _download_asr(self) -> None:
        from huggingface_hub import snapshot_download

        from ..asr.downloader import download_dir_with_progress

        spec = self._controller._asr.resolve_target_model()
        target_dir = paths.models_dir() / spec.id
        expected_bytes = max(spec.approx_size_mb, 1) * 1024 * 1024
        self.status.emit(f"Step 1 of 2: downloading speech model -- {spec.display_name} (~{spec.approx_size_mb}MB)...")
        download_dir_with_progress(
            target_dir,
            expected_bytes,
            do_download=lambda: snapshot_download(repo_id=spec.ct2_repo, local_dir=str(target_dir)),
            on_progress=self.progress.emit,
        )

    def _download_formatter(self) -> None:
        from huggingface_hub import hf_hub_download

        from ..asr.downloader import download_dir_with_progress
        from ..text import formatter as formatter_mod

        target_dir = paths.models_dir() / "formatter"
        expected_bytes = formatter_mod.APPROX_SIZE_MB * 1024 * 1024
        self.status.emit(f"Step 2 of 2: downloading text-cleanup model (~{formatter_mod.APPROX_SIZE_MB}MB)...")
        download_dir_with_progress(
            target_dir,
            expected_bytes,
            do_download=lambda: hf_hub_download(
                formatter_mod.MODEL_REPO, formatter_mod.MODEL_FILE, local_dir=str(target_dir)
            ),
            on_progress=self.progress.emit,
        )


from PySide6.QtGui import QPainter
from PySide6.QtWidgets import QHBoxLayout

from .theme import LIME, build_stylesheet, paint_paper_background
from .widgets import StickerBadge


class OnboardingDialog(QDialog):
    def __init__(self, controller):
        super().__init__()
        self._controller = controller
        self.setWindowTitle("Welcome to FlowState")
        self.setStyleSheet(build_stylesheet())
        self.setFixedSize(520, 420)
        self.setWindowFlags(self.windowFlags() & ~Qt.WindowContextHelpButtonHint)

        cfg = controller.config_store.config

        layout = QVBoxLayout(self)
        layout.setContentsMargins(36, 32, 36, 30)
        layout.setSpacing(14)

        # Header with sticker chips
        header_row = QHBoxLayout()
        badge_step = StickerBadge("SYS.01 // SETUP", bg_color="#0D0D0D", text_color="#FFFFFF")
        badge_local = StickerBadge("100% LOCAL", bg_color=LIME, text_color="#0D0D0D", is_pill=True)
        header_row.addWidget(badge_step)
        header_row.addWidget(badge_local)
        header_row.addStretch(1)
        layout.addLayout(header_row)

        headline = QLabel("Let's get set up")
        headline.setProperty("role", "headline")
        body = QLabel(
            f"Default shortcuts: {cfg.shortcuts.toggle} to start/stop hands-free, "
            f"or hold {cfg.shortcuts.push_to_talk} for push-to-talk.\n\n"
            "FlowState downloads its speech & formatting AI models once "
            "(~1.3-2.7GB total), then runs completely offline with zero telemetry. "
            "Microphone, capture sensitivity, and hotkeys can be changed anytime in Settings."
        )
        body.setProperty("role", "muted")
        body.setWordWrap(True)

        self.status_label = QLabel("Ready to initialize models.")
        self.status_label.setProperty("role", "muted")
        self.status_label.setWordWrap(True)

        self.progress = QProgressBar()
        self.progress.setFixedHeight(22)
        self.progress.setRange(0, 100)
        self.progress.setValue(0)
        self.progress.hide()

        self.start_btn = QPushButton("Initialize & Preload Models")
        self.start_btn.setFixedHeight(44)
        self.start_btn.clicked.connect(self._start_setup)

        layout.addWidget(headline)
        layout.addWidget(body)
        layout.addStretch(1)
        layout.addWidget(self.status_label)
        layout.addWidget(self.progress)
        layout.addWidget(self.start_btn)

        self._thread: QThread | None = None
        self._worker: _PreloadWorker | None = None

    def paintEvent(self, event):
        painter = QPainter(self)
        paint_paper_background(painter, self.rect())


    def _start_setup(self) -> None:
        self.start_btn.setEnabled(False)
        self.progress.setValue(0)
        self.progress.show()

        self._thread = QThread()
        self._worker = _PreloadWorker(self._controller)
        self._worker.moveToThread(self._thread)
        self._thread.started.connect(self._worker.run)
        self._worker.status.connect(self.status_label.setText)
        self._worker.progress.connect(self.progress.setValue)
        self._worker.finished.connect(self._on_finished)
        self._worker.failed.connect(self._on_failed)
        self._worker.finished.connect(self._thread.quit)
        self._worker.failed.connect(self._thread.quit)
        self._thread.start()

    def _on_finished(self) -> None:
        paths.first_run_flag_path().write_text("done", encoding="utf-8")
        self.status_label.setText("All set! FlowState is ready.")
        self.progress.hide()
        self.start_btn.setText("Done")
        self.start_btn.setEnabled(True)
        self.start_btn.clicked.disconnect()
        self.start_btn.clicked.connect(self.accept)

    def _on_failed(self, message: str) -> None:
        paths.first_run_flag_path().write_text("done", encoding="utf-8")
        self.status_label.setText(
            f"Setup hit a snag, but FlowState will still work (just slower on first use): {message}"
        )
        self.progress.hide()
        self.start_btn.setText("Continue Anyway")
        self.start_btn.setEnabled(True)
        self.start_btn.clicked.disconnect()
        self.start_btn.clicked.connect(self.accept)
