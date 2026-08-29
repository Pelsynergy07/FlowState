"""First-run setup: a short welcome, then a one-time background preload
of the AI models. This is what makes every future recording fast instead
of stalling on the first real dictation while a model downloads/loads."""

from __future__ import annotations

from PySide6.QtCore import QObject, Qt, QThread, Signal
from PySide6.QtWidgets import QDialog, QLabel, QProgressBar, QPushButton, QVBoxLayout

from .. import paths
from .theme import build_stylesheet


class _PreloadWorker(QObject):
    status = Signal(str)
    finished = Signal()
    failed = Signal(str)

    def __init__(self, controller):
        super().__init__()
        self._controller = controller

    def run(self) -> None:
        try:
            self.status.emit("Downloading and loading the speech model (first time only)...")
            self._controller._asr._load()
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

            self.status.emit("Loading the smart-formatting model (can take a moment the first time)...")
            self._controller._pipeline.preload()
            self.status.emit("Smart-formatting model ready.")
        except Exception as exc:
            self.failed.emit(str(exc))
            return
        self.finished.emit()


class OnboardingDialog(QDialog):
    def __init__(self, controller):
        super().__init__()
        self._controller = controller
        self.setWindowTitle("Welcome to FlowState")
        self.setStyleSheet(build_stylesheet())
        self.setFixedSize(480, 340)
        self.setWindowFlags(self.windowFlags() & ~Qt.WindowContextHelpButtonHint)

        cfg = controller.config_store.config

        layout = QVBoxLayout(self)
        layout.setContentsMargins(36, 34, 36, 34)
        layout.setSpacing(16)

        eyebrow = QLabel("FLOWSTATE / FIRST RUN")
        eyebrow.setProperty("role", "eyebrow")
        headline = QLabel("Let's get set up")
        headline.setProperty("role", "headline")
        body = QLabel(
            f"Default shortcut: {cfg.shortcuts.toggle} to start/stop hands-free, "
            f"or hold {cfg.shortcuts.push_to_talk} to push-to-talk.\n\n"
            "FlowState downloads its AI models once (a few hundred MB to a "
            "couple GB depending on your setup), then runs fully offline. "
            "You can change the microphone and shortcuts anytime from the "
            "tray icon's Settings."
        )
        body.setProperty("role", "muted")
        body.setWordWrap(True)

        self.status_label = QLabel("Ready to set up.")
        self.status_label.setProperty("role", "muted")
        self.status_label.setWordWrap(True)

        self.progress = QProgressBar()
        self.progress.setRange(0, 0)
        self.progress.hide()

        self.start_btn = QPushButton("Set Up FlowState")
        self.start_btn.clicked.connect(self._start_setup)

        layout.addWidget(eyebrow)
        layout.addWidget(headline)
        layout.addWidget(body)
        layout.addStretch(1)
        layout.addWidget(self.status_label)
        layout.addWidget(self.progress)
        layout.addWidget(self.start_btn)

        self._thread: QThread | None = None
        self._worker: _PreloadWorker | None = None

    def _start_setup(self) -> None:
        self.start_btn.setEnabled(False)
        self.progress.show()

        self._thread = QThread()
        self._worker = _PreloadWorker(self._controller)
        self._worker.moveToThread(self._thread)
        self._thread.started.connect(self._worker.run)
        self._worker.status.connect(self.status_label.setText)
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
