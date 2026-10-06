"""First-run setup: hardware detection, crisp system status, and one-time
background model preload with continuous activity spinner and live ETA.
"""

from __future__ import annotations

import logging
import shutil
from pathlib import Path
from PySide6.QtCore import QObject, QPointF, QRectF, QSize, Qt, QThread, QTimer, Signal
from PySide6.QtGui import QColor, QFont, QPainter, QPen
from PySide6.QtWidgets import (
    QApplication,
    QComboBox,
    QDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QProgressBar,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from .. import paths
from .fonts import make_font
from .theme import (
    BORDER,
    FONT_FAMILY,
    FONT_FAMILY_DISPLAY,
    FONT_FAMILY_MONO,
    FONT_FAMILY_STICKER,
    INK,
    LIME,
    MUTED_TEXT,
    PAPER,
    PAPER_ALT,
    PAPER_RAISED,
    build_stylesheet,
    paint_paper_background,
    setup_brutalist_combobox,
)
from .widgets import ActivitySpinner, GeometricMotif, StickerBadge

logger = logging.getLogger("flowstate.onboarding")


def _cpu_name() -> str:
    """Readable processor name, e.g. "Intel(R) Core(TM) i7-9750H CPU @ 2.60GHz"."""
    try:
        import winreg

        with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, r"HARDWARE\DESCRIPTION\System\CentralProcessor\0") as key:
            return " ".join(str(winreg.QueryValueEx(key, "ProcessorNameString")[0]).split())
    except Exception:
        import platform

        return platform.processor() or "Your processor"


def _detect_hardware_summary() -> tuple[str, str, bool, int]:
    """Returns (hardware_title, detail_text, is_gpu, core_count).

    Asks the NVIDIA driver directly (milliseconds) rather than importing
    the CUDA runtime (seconds): the window must appear immediately. The
    models themselves still verify CUDA when they load.
    """
    import os
    from ..text import llm

    cores = os.cpu_count() or 4
    gpu = llm.cuda_device_name()
    if gpu:
        return gpu, "NVIDIA graphics card", True, cores
    return _cpu_name(), f"Processor ({cores} threads)", False, cores


def _missing_download_mb(controller, is_gpu: bool) -> int:
    """Approximate size of the models this machine still has to download."""
    total = 0
    try:
        from ..asr.engine import _find_model_dir

        spec = controller._asr.resolve_target_model(cuda_available=is_gpu)
        if _find_model_dir(paths.models_dir() / spec.id) is None:
            total += spec.approx_size_mb
    except Exception:
        pass
    try:
        from ..text import llm

        model = controller._pipeline._formatter.target_model(cuda_available=is_gpu)
        if not llm.is_cached(model):
            total += model.approx_size_mb
    except Exception:
        pass
    return total


class _PreloadWorker(QObject):
    progress = Signal(int)
    telemetry = Signal(str)
    status = Signal(str)
    finished = Signal()
    failed = Signal(str)

    def __init__(self, controller, hw_name: str, is_gpu: bool, cores: int):
        super().__init__()
        self._controller = controller
        self._hw_name = hw_name
        self._is_gpu = is_gpu
        self._cores = cores
        # Each download fills its own slice of one continuous 0-100% bar.
        self._range = (0, 100)

    def run(self) -> None:
        import threading
        import time

        try:
            if getattr(self._controller, "_is_preview", False):
                import time

                steps = [
                    (15, "Step 1 of 2: Preparing Whisper Turbo speech engine...", "Verifying voice recognition models..."),
                    (45, "Step 1 of 2: Initializing speech engine...", f"Loading voice models on {self._hw_name}..."),
                    (75, "Step 2 of 2: Preparing text formatting model...", "Loading smart thought formatter..."),
                    (100, "✓ System setup complete!", "Voice recognition and thought formatting ready."),
                ]
                for p, s, t in steps:
                    time.sleep(0.4)
                    self.progress.emit(p)
                    self.status.emit(s)
                    self.telemetry.emit(t)
                time.sleep(0.3)
                self.finished.emit()
                return

            # 1. Download Whisper Turbo speech model
            self._range = (0, 45)
            self._download_asr()

            # 2. Compile Whisper weights into memory/VRAM with real-time heartbeat
            est_time = "5–12s" if self._is_gpu else "15–25s"
            dev_type = "GPU VRAM" if self._is_gpu else "System RAM"
            self.status.emit(f"Setting up speech recognition engine...")
            self.telemetry.emit(f"Initializing voice models on {self._hw_name} (est. ~{est_time})...")
            self.progress.emit(47)

            stop_compile = threading.Event()

            def _compile_heartbeat():
                elapsed = 0
                while not stop_compile.is_set():
                    time.sleep(1.0)
                    elapsed += 1
                    self.telemetry.emit(
                        f"Preparing speech engine • {elapsed}s elapsed (est. ~{est_time})..."
                    )

            hb_thread = threading.Thread(target=_compile_heartbeat, daemon=True)
            hb_thread.start()
            try:
                self._controller._asr._load()
            finally:
                stop_compile.set()
                hb_thread.join(timeout=1.0)

            device = self._controller._asr.active_device
            model_id = self._controller._asr.active_model_id
            dev_label = "CUDA Accelerated" if device == "cuda" else "CPU AVX2"
            self.status.emit(f"✓ Speech engine ready ({dev_label}).")
            self.telemetry.emit(f"Voice recognition initialized successfully.")

            # 3. Download Qwen 1.5B text-formatting model
            self._range = (50, 92)
            self.progress.emit(50)
            self._download_formatter()

            # 4. Initialize formatting model into memory
            self.status.emit("Setting up smart text formatting...")
            self.telemetry.emit("Loading smart text formatter into memory...")
            self.progress.emit(95)

            stop_fmt = threading.Event()

            def _fmt_heartbeat():
                elapsed = 0
                while not stop_fmt.is_set():
                    time.sleep(1.0)
                    elapsed += 1
                    self.telemetry.emit(
                        f"Finalizing AI text formatting • {elapsed}s elapsed..."
                    )

            hb_fmt = threading.Thread(target=_fmt_heartbeat, daemon=True)
            hb_fmt.start()
            try:
                self._controller._pipeline.preload()
            finally:
                stop_fmt.set()
                hb_fmt.join(timeout=1.0)

            self.status.emit("✓ FlowState is ready to use!")
            self.telemetry.emit("Ready for instant offline dictation • Private on your PC.")
            self.progress.emit(100)
        except Exception as exc:
            logger.error("Preload worker failed", exc_info=True)
            self.failed.emit(str(exc))
            return
        self.finished.emit()

    def _on_download_progress(self, pct, current_bytes=0, total_bytes=0, speed=0.0, eta=None):
        low, high = self._range
        self.progress.emit(low + pct * (high - low) // 100)
        if total_bytes > 0:
            mb_cur = current_bytes / (1024 * 1024)
            mb_tot = total_bytes / (1024 * 1024)
            speed_mb = speed / (1024 * 1024)
            if eta is not None and eta > 0:
                mins, secs = divmod(eta, 60)
                eta_str = f"{mins}m {secs}s" if mins > 0 else f"{secs}s"
                self.telemetry.emit(f"{mb_cur:.1f} MB / {mb_tot:.1f} MB ({pct}%) • {speed_mb:.1f} MB/s • ETA: ~{eta_str} remaining")
            else:
                self.telemetry.emit(f"{mb_cur:.1f} MB / {mb_tot:.1f} MB ({pct}%) • {speed_mb:.1f} MB/s")
        else:
            self.telemetry.emit(f"Downloading... ({pct}%)")

    def _download_asr(self) -> None:
        from huggingface_hub import snapshot_download
        from ..asr.downloader import download_dir_with_progress

        spec = self._controller._asr.resolve_target_model()
        target_dir = paths.models_dir() / spec.id
        expected_bytes = max(spec.approx_size_mb, 1) * 1024 * 1024
        self.status.emit(f"Step 1 of 2: Downloading speech model ({spec.display_name})...")
        download_dir_with_progress(
            target_dir,
            expected_bytes,
            do_download=lambda: snapshot_download(repo_id=spec.ct2_repo, local_dir=str(target_dir)),
            on_progress=self._on_download_progress,
        )

    def _download_formatter(self) -> None:
        from ..asr.downloader import download_dir_with_progress
        from ..text import llm

        # GPU machines download only the GPU model; CPU-only machines only
        # the CPU one.
        model = self._controller._pipeline._formatter.target_model()
        if llm.is_cached(model):
            return
        target_dir = llm.model_dir(model)
        expected_bytes = model.approx_size_mb * 1024 * 1024
        self.status.emit(f"Step 2 of 2: Downloading text formatting model ({model.display_name})...")
        download_dir_with_progress(
            target_dir,
            expected_bytes,
            do_download=lambda: llm.download(model),
            on_progress=self._on_download_progress,
        )


class OnboardingDialog(QDialog):
    def __init__(self, controller):
        super().__init__()
        self._controller = controller
        self.setWindowTitle("FlowState Setup")
        self.setStyleSheet(build_stylesheet())
        self.resize(580, 680)
        self.setMinimumSize(540, 640)
        self.setMaximumWidth(600)
        self.setWindowFlags(self.windowFlags() & ~Qt.WindowContextHelpButtonHint)

        cfg = controller.config_store.config
        self.hw_name, self.hw_detail, self.is_gpu, self.cores = _detect_hardware_summary()
        self.skipped = False
        # True once both models are downloaded and loaded; otherwise the app
        # finishes preparing them in the background after this dialog.
        self.models_ready = False

        outer = QVBoxLayout(self)
        outer.setContentsMargins(24, 20, 24, 18)
        outer.setSpacing(11)

        # 1. Header with sticker badges and subtle geometric star motif
        header_row = QHBoxLayout()
        header_left = QVBoxLayout()
        header_left.setSpacing(4)
        eyebrow_row = QHBoxLayout()
        eyebrow_row.setSpacing(6)
        eyebrow_star = GeometricMotif("star", size=11, color=INK)
        eyebrow = QLabel("FLOWSTATE / GETTING STARTED")
        eyebrow.setProperty("role", "eyebrow")
        eyebrow_row.addWidget(eyebrow_star)
        eyebrow_row.addWidget(eyebrow)
        eyebrow_row.addStretch(1)

        headline = QLabel("Speak your mind.\nFlowState handles the rest.")
        headline.setProperty("role", "headline")
        headline.setFont(make_font(FONT_FAMILY_DISPLAY, 30))
        header_left.addLayout(eyebrow_row)
        header_left.addWidget(headline)
        header_row.addLayout(header_left, 1)
        outer.addLayout(header_row)

        rule = QFrame()
        rule.setProperty("role", "rule")
        outer.addWidget(rule)

        # 2. Hardware detection readout card with subtle architectural crosshair
        hw_card = QFrame()
        hw_card.setProperty("role", "card")
        hw_layout = QHBoxLayout(hw_card)
        hw_layout.setContentsMargins(16, 12, 16, 12)
        hw_icon = GeometricMotif("star", size=22)
        hw_icon.setFont(make_font(FONT_FAMILY, 16))
        hw_texts = QVBoxLayout()
        hw_texts.setSpacing(2)
        hw_lbl = QLabel(f"HARDWARE DETECTED: {self.hw_name.upper()}")
        hw_lbl.setFont(make_font(FONT_FAMILY_MONO, 9, bold=True))
        hw_lbl.setWordWrap(True)

        if self.is_gpu:
            hw_desc = "Dictation runs on your graphics card for the fastest results."
        else:
            hw_desc = ("No NVIDIA graphics card found, so FlowState uses a smaller speech model on your "
                       "processor. It works fully offline; formatting just takes a little longer.")

        hw_sub = QLabel(hw_desc)
        hw_sub.setFont(make_font(FONT_FAMILY, 9))
        hw_sub.setStyleSheet("color: #5C5751;")
        hw_sub.setWordWrap(True)
        hw_texts.addWidget(hw_lbl)
        hw_texts.addWidget(hw_sub)
        hw_layout.addWidget(hw_icon)
        hw_layout.addLayout(hw_texts, 1)
        outer.addWidget(hw_card)

        # 2b. Microphone input selector card
        mic_card = QFrame()
        mic_card.setProperty("role", "card")
        mic_layout = QVBoxLayout(mic_card)
        mic_layout.setContentsMargins(16, 10, 16, 10)
        mic_layout.setSpacing(6)

        mic_head = QHBoxLayout()
        mic_head.setSpacing(8)
        mic_icon = GeometricMotif("dot_grid", size=18)
        mic_icon.setFont(make_font(FONT_FAMILY, 14))
        mic_lbl = QLabel("YOUR MICROPHONE")
        mic_lbl.setFont(make_font(FONT_FAMILY_MONO, 8.5, bold=True))
        mic_head.addWidget(mic_icon)
        mic_head.addWidget(mic_lbl)
        mic_head.addStretch(1)
        mic_layout.addLayout(mic_head)

        self.mic_combo = QComboBox()
        self.mic_combo.setFixedHeight(34)
        self.mic_combo.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self.mic_combo.setSizeAdjustPolicy(QComboBox.AdjustToMinimumContentsLengthWithIcon)
        self.mic_combo.setMinimumContentsLength(10)
        setup_brutalist_combobox(self.mic_combo)
        self.mic_combo.addItem("System Default", None)
        try:
            from ..audio.devices import list_input_devices

            for d in list_input_devices():
                self.mic_combo.addItem(d.name, d.name)
        except Exception:
            logger.warning("Could not enumerate audio devices in onboarding", exc_info=True)

        current_mic = cfg.general.microphone_device
        idx = self.mic_combo.findData(current_mic)
        self.mic_combo.setCurrentIndex(idx if idx >= 0 else 0)
        self.mic_combo.currentIndexChanged.connect(self._on_mic_changed)
        mic_layout.addWidget(self.mic_combo)

        outer.addWidget(mic_card)

        # 3. Core features with fun, energetic neo-brutalist copy
        features_card = QFrame()
        features_card.setProperty("role", "card")
        features_card.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Minimum)
        f_layout = QVBoxLayout(features_card)
        f_layout.setSizeConstraint(QVBoxLayout.SetMinimumSize)
        f_layout.setContentsMargins(18, 12, 18, 12)
        f_layout.setSpacing(6)

        def _make_bullet(index_str: str, bold_prefix: str, desc: str) -> QHBoxLayout:
            row = QHBoxLayout()
            row.setSizeConstraint(QHBoxLayout.SetMinimumSize)
            row.setSpacing(12)
            idx = QLabel(index_str)
            idx.setFont(make_font(FONT_FAMILY_MONO, 8.5, bold=True))
            idx.setStyleSheet(
                "color: #1A1A1A; background-color: #EFE8DC; border: 1.5px solid #1A1A1A; border-radius: 3px; padding: 2px 4px;"
            )
            idx.setFixedWidth(52)
            idx.setFixedHeight(22)
            idx.setAlignment(Qt.AlignCenter)
            txt = QLabel(f"<b>{bold_prefix}</b> {desc}")
            txt.setFont(make_font(FONT_FAMILY, 9.5))
            txt.setFixedHeight(20)
            row.addWidget(idx)
            row.addWidget(txt, 1)
            return row

        f_layout.addLayout(
            _make_bullet("[ 01 ]", f"Hold to Talk ({cfg.shortcuts.push_to_talk}):", "Speak and release to paste.")
        )
        f_layout.addLayout(
            _make_bullet("[ 02 ]", f"Hands-Free ({cfg.shortcuts.toggle}):", "Tap to speak, tap again to paste.")
        )
        capture_hint = {"drag": ("Screenshot (Ctrl+Drag):", "Select any area while you speak."),
                        "circle": ("Screenshot (circle it):", "Draw a loop around anything while you speak.")}
        if cfg.capture.mode in capture_hint:
            f_layout.addLayout(_make_bullet("[ 03 ]", *capture_hint[cfg.capture.mode]))
        f_layout.addLayout(_make_bullet(f"[ 0{f_layout.count() + 1} ]", "Smart formatting:",
                                        "Punctuation, emails and lists, in your own words."))
        outer.addWidget(features_card)

        # 4. Status & Telemetry section
        status_card = QFrame()
        status_card.setProperty("role", "card")
        status_card.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Minimum)
        s_layout = QVBoxLayout(status_card)
        s_layout.setSizeConstraint(QVBoxLayout.SetMinimumSize)
        s_layout.setContentsMargins(18, 12, 18, 12)
        s_layout.setSpacing(7)

        status_header_row = QHBoxLayout()
        self.spinner = ActivitySpinner(size=20, color=INK)
        self.spinner.hide()
        status_header_row.addWidget(self.spinner)

        self.status_label = QLabel(self._intro_text(controller, self.is_gpu))
        self.status_label.setFont(make_font(FONT_FAMILY, 10, bold=True))
        self.status_label.setWordWrap(True)
        status_header_row.addWidget(self.status_label, 1)
        s_layout.addLayout(status_header_row)

        self.progress = QProgressBar()
        self.progress.setFixedHeight(22)
        self.progress.setRange(0, 100)
        self.progress.setValue(0)
        self.progress.hide()
        s_layout.addWidget(self.progress)

        self.telemetry_label = QLabel("")
        self.telemetry_label.setFont(make_font(FONT_FAMILY_MONO, 8.5))
        self.telemetry_label.setStyleSheet("color: #5C5751;")
        self.telemetry_label.setWordWrap(True)
        self.telemetry_label.hide()
        s_layout.addWidget(self.telemetry_label)

        outer.addWidget(status_card)
        outer.addStretch(1)

        # 5. Action Buttons with Skip Option pinned at bottom
        btn_bar = QWidget()
        btn_row = QHBoxLayout(btn_bar)
        btn_row.setContentsMargins(0, 4, 0, 0)
        btn_row.setSpacing(10)

        self.skip_btn = QPushButton("Skip for Now")
        self.skip_btn.setProperty("role", "secondary")
        self.skip_btn.setMinimumWidth(115)
        self.skip_btn.setFixedHeight(44)
        self.skip_btn.setCursor(Qt.PointingHandCursor)
        self.skip_btn.clicked.connect(self._skip_onboarding)
        btn_row.addWidget(self.skip_btn)

        self.start_btn = QPushButton("Prepare FlowState →")
        self.start_btn.setFixedHeight(44)
        self.start_btn.setProperty("role", "primary")
        self.start_btn.setCursor(Qt.PointingHandCursor)
        self.start_btn.clicked.connect(self._start_setup)
        btn_row.addWidget(self.start_btn, 1)

        outer.addWidget(btn_bar)

        self._thread: QThread | None = None
        self._worker: _PreloadWorker | None = None

    def paintEvent(self, event):
        painter = QPainter(self)
        paint_paper_background(painter, self.rect())

    @staticmethod
    def _intro_text(controller, is_gpu: bool) -> str:
        """Say what will be downloaded before anything is."""
        needed_mb = _missing_download_mb(controller, is_gpu)
        if not needed_mb:
            return "Click below to load the speech and formatting models and start."
        text = (f"FlowState will download its speech and formatting models (about {needed_mb / 1024:.1f} GB) "
                "from Hugging Face. This happens once; after that everything runs offline.")
        try:
            free_mb = shutil.disk_usage(paths.models_dir()).free // (1024 * 1024)
            if free_mb < needed_mb + 500:
                text += f" Only {free_mb / 1024:.1f} GB is free on this drive, so please make room first."
        except OSError:
            pass
        return text

    def _sync_window_size(self) -> None:
        """Automatically expand dialog height if dynamic contents need more space."""
        self.updateGeometry()
        QApplication.processEvents()
        hint = self.sizeHint()
        needed_h = max(self.height(), hint.height())
        if needed_h > self.height():
            self.resize(self.width(), needed_h + 8)

    def _on_mic_changed(self) -> None:
        new_mic = self.mic_combo.currentData()
        self._controller.config_store.config.general.microphone_device = new_mic
        self._controller.config_store.save()
        if hasattr(self._controller, "switch_microphone"):
            self._controller.switch_microphone(new_mic)
        elif hasattr(self._controller, "apply_config_change"):
            self._controller.apply_config_change()
        logger.info("Microphone updated in onboarding: %r", new_mic)

    def _skip_onboarding(self) -> None:
        self.skipped = True
        logger.info("User skipped onboarding.")
        self.accept()

    def _on_telemetry_update(self, text: str) -> None:
        self.telemetry_label.setText(text)
        self._sync_window_size()

    def _on_status_update(self, text: str) -> None:
        self.status_label.setText(text)
        self._sync_window_size()

    def _start_setup(self) -> None:
        # A retry must actually retry, not replay the previous failure.
        for component in (getattr(self._controller, "_asr", None),
                          getattr(getattr(self._controller, "_pipeline", None), "_formatter", None)):
            if component is not None and hasattr(component, "clear_load_failure"):
                component.clear_load_failure()
        self.start_btn.setEnabled(False)
        self.start_btn.setText("Setting Things Up...")
        self.skip_btn.setEnabled(False)
        self.spinner.show()
        self.progress.setValue(0)
        self.progress.show()
        self.telemetry_label.setText("Preparing model download...")
        self.telemetry_label.show()
        self._sync_window_size()

        self._thread = QThread()
        self._worker = _PreloadWorker(self._controller, self.hw_name, self.is_gpu, self.cores)
        self._worker.moveToThread(self._thread)
        self._thread.started.connect(self._worker.run)
        self._worker.status.connect(self._on_status_update)
        self._worker.telemetry.connect(self._on_telemetry_update)
        self._worker.progress.connect(self.progress.setValue)
        self._worker.finished.connect(self._on_finished)
        self._worker.failed.connect(self._on_failed)
        self._worker.finished.connect(self._thread.quit)
        self._worker.failed.connect(self._thread.quit)
        self._thread.start()

    def _on_finished(self) -> None:
        self.models_ready = True
        self.spinner.hide()
        self.status_label.setText("FlowState is ready for instant dictation!")
        self.telemetry_label.setText("Everything is installed and ready to go.")
        self.progress.setValue(100)
        self._sync_window_size()
        self.start_btn.setText("Open FlowState && Start Tutorial →")
        self.start_btn.setEnabled(True)
        # Nothing left to skip; it would only skip the tutorial.
        self.skip_btn.hide()
        self.start_btn.clicked.disconnect()
        self.start_btn.clicked.connect(self.accept)

    def _on_failed(self, message: str) -> None:
        self.spinner.hide()
        self.progress.hide()
        network = any(marker in message for marker in (
            "Connection", "Timeout", "Max retries", "getaddrinfo", "NameResolution", "internet connection"))
        if network:
            self.status_label.setText("Setup couldn't finish: FlowState couldn't reach the model download "
                                      "server. Check your internet connection and try again.")
        else:
            self.status_label.setText("Setup couldn't finish preparing the models. Try again, or continue "
                                      "and FlowState will keep trying in the background.")
        self.telemetry_label.setText(f"Details: {message}")
        self._sync_window_size()
        self.start_btn.setText("Try Again")
        self.start_btn.setEnabled(True)
        self.start_btn.clicked.disconnect()
        self.start_btn.clicked.connect(self._start_setup)
        self.skip_btn.setText("Continue Without It")
        self.skip_btn.setEnabled(True)

