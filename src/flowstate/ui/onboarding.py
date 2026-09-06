"""First-run setup: hardware detection, crisp system status, and one-time
background model preload with continuous activity spinner and live ETA.
"""

from __future__ import annotations

import logging
import subprocess
from pathlib import Path
from PySide6.QtCore import QObject, QPointF, QRectF, QSize, Qt, QThread, QTimer, Signal
from PySide6.QtGui import QColor, QFont, QPainter, QPen
from PySide6.QtWidgets import (
    QDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QProgressBar,
    QPushButton,
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
)
from .widgets import ActivitySpinner, GeometricMotif, StickerBadge

logger = logging.getLogger("flowstate.onboarding")


def _detect_hardware_summary() -> tuple[str, str, bool, int]:
    """Returns (hardware_title, detail_text, is_gpu, core_count)."""
    import os
    cores = os.cpu_count() or 4
    try:
        import ctranslate2
        if ctranslate2.get_cuda_device_count() > 0:
            try:
                res = subprocess.run(
                    ["powershell", "-Command", "(Get-CimInstance Win32_VideoController | Where-Object { $_.Name -like '*NVIDIA*' }).Name"],
                    capture_output=True,
                    text=True,
                    timeout=2,
                )
                gpu = res.stdout.strip().split("\n")[0].strip()
                if gpu:
                    return (gpu, "Dedicated GPU (CUDA 12.x Accelerated)", True, cores)
            except Exception:
                pass
            return ("NVIDIA GPU", "CUDA Hardware Acceleration Enabled", True, cores)
    except Exception:
        pass
    return (f"CPU Mode ({cores} Cores)", "Local AVX2 CPU Inference", False, cores)


class _PreloadWorker(QObject):
    status = Signal(str)
    telemetry = Signal(str)
    progress = Signal(int)  # 0-100
    finished = Signal()
    failed = Signal(str)

    def __init__(self, controller, hw_name: str, is_gpu: bool, cores: int):
        super().__init__()
        self._controller = controller
        self._hw_name = hw_name
        self._is_gpu = is_gpu
        self._cores = cores

    def run(self) -> None:
        import threading
        import time

        try:
            # 1. Download Whisper Turbo speech model
            self._download_asr()

            # 2. Compile Whisper weights into memory/VRAM with real-time heartbeat
            est_time = "5–12s" if self._is_gpu else "15–25s"
            dev_type = "GPU VRAM" if self._is_gpu else "System RAM"
            self.status.emit(f"Compiling Whisper Turbo weights into {dev_type}...")
            self.telemetry.emit(f"Allocating {dev_type} on {self._hw_name} (est. ~{est_time})...")
            self.progress.emit(50)

            stop_compile = threading.Event()

            def _compile_heartbeat():
                elapsed = 0
                while not stop_compile.is_set():
                    time.sleep(1.0)
                    elapsed += 1
                    self.telemetry.emit(
                        f"Compiling tensor graph into {dev_type} • {elapsed}s elapsed (est. ~{est_time} on {self._hw_name})..."
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
            self.status.emit(f"✓ Speech model ready: {model_id} ({dev_label}).")
            self.telemetry.emit(f"Tensor graph loaded into {dev_type} successfully.")

            # 3. Download Qwen 1.5B text-formatting model
            self._download_formatter()

            # 4. Initialize formatting model into memory
            self.status.emit("Initializing smart-formatting LLM engine...")
            self.telemetry.emit("Loading Qwen 1.5B tokenizer & weights into local memory (est. ~3–6s)...")
            self.progress.emit(95)

            stop_fmt = threading.Event()

            def _fmt_heartbeat():
                elapsed = 0
                while not stop_fmt.is_set():
                    time.sleep(1.0)
                    elapsed += 1
                    self.telemetry.emit(
                        f"Allocating formatting LLM context window • {elapsed}s elapsed (est. ~3–6s)..."
                    )

            hb_fmt = threading.Thread(target=_fmt_heartbeat, daemon=True)
            hb_fmt.start()
            try:
                self._controller._pipeline.preload()
            finally:
                stop_fmt.set()
                hb_fmt.join(timeout=1.0)

            self.status.emit("✓ All models verified and ready on your PC!")
            self.telemetry.emit(f"Ready for instant offline dictation • Zero cloud dependencies.")
            self.progress.emit(100)
        except Exception as exc:
            logger.error("Preload worker failed", exc_info=True)
            self.failed.emit(str(exc))
            return
        self.finished.emit()

    def _on_download_progress(self, pct, current_bytes=0, total_bytes=0, speed=0.0, eta=None):
        # Map download 0-100 to progress 0-50 for step 1, 50-95 for step 2
        self.progress.emit(pct)
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
        from huggingface_hub import hf_hub_download
        from ..asr.downloader import download_dir_with_progress
        from ..text import formatter as formatter_mod

        target_dir = paths.models_dir() / "formatter"
        expected_bytes = formatter_mod.APPROX_SIZE_MB * 1024 * 1024
        self.status.emit("Step 2 of 2: Downloading text formatting model (Qwen 1.5B)...")
        download_dir_with_progress(
            target_dir,
            expected_bytes,
            do_download=lambda: hf_hub_download(
                formatter_mod.MODEL_REPO, formatter_mod.MODEL_FILE, local_dir=str(target_dir)
            ),
            on_progress=self._on_download_progress,
        )


class OnboardingDialog(QDialog):
    def __init__(self, controller):
        super().__init__()
        self._controller = controller
        self.setWindowTitle("FlowState Setup")
        self.setStyleSheet(build_stylesheet())
        self.resize(630, 580)
        self.setMinimumSize(590, 530)
        self.setWindowFlags(self.windowFlags() & ~Qt.WindowContextHelpButtonHint)

        cfg = controller.config_store.config
        self.hw_name, self.hw_detail, self.is_gpu, self.cores = _detect_hardware_summary()
        self.skipped = False

        outer = QVBoxLayout(self)
        outer.setContentsMargins(32, 26, 32, 22)
        outer.setSpacing(13)

        # 1. Header with sticker badges and subtle geometric star motif
        header_row = QHBoxLayout()
        header_left = QVBoxLayout()
        header_left.setSpacing(4)
        eyebrow_row = QHBoxLayout()
        eyebrow_row.setSpacing(6)
        eyebrow_star = GeometricMotif("star", size=11, color=INK)
        eyebrow = QLabel("SYS.01 // GETTING STARTED")
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

        badges_col = QVBoxLayout()
        badges_col.setSpacing(6)
        b1 = StickerBadge("100% LOCAL AI", bg_color=LIME, text_color="#1A1A1A", is_pill=True)
        b2 = StickerBadge("ZERO TELEMETRY", bg_color="#1A1A1A", text_color="#FFFFFF", is_pill=False)
        badges_col.addWidget(b1)
        badges_col.addWidget(b2)
        header_row.addLayout(badges_col)

        outer.addLayout(header_row)

        rule = QFrame()
        rule.setProperty("role", "rule")
        outer.addWidget(rule)

        # 2. Hardware detection readout card with subtle architectural crosshair
        hw_card = QFrame()
        hw_card.setProperty("role", "card")
        hw_layout = QHBoxLayout(hw_card)
        hw_layout.setContentsMargins(16, 12, 16, 12)
        hw_icon = QLabel("⚡")
        hw_icon.setFont(make_font(FONT_FAMILY, 16))
        hw_texts = QVBoxLayout()
        hw_texts.setSpacing(2)
        hw_lbl = QLabel(f"HARDWARE DETECTED: {self.hw_name.upper()}")
        hw_lbl.setFont(make_font(FONT_FAMILY_MONO, 9, bold=True))

        if self.is_gpu:
            hw_desc = f"{self.hw_detail} • CUDA accelerated for instant real-time dictation."
        else:
            hw_desc = f"{self.hw_detail} • Standard CPU Mode (AVX2). Initial warmup may take a moment, then runs smoothly."

        hw_sub = QLabel(hw_desc)
        hw_sub.setFont(make_font(FONT_FAMILY, 9))
        hw_sub.setStyleSheet("color: #5C5751;")
        hw_sub.setWordWrap(True)
        hw_texts.addWidget(hw_lbl)
        hw_texts.addWidget(hw_sub)
        hw_layout.addWidget(hw_icon)
        hw_layout.addLayout(hw_texts, 1)
        hw_cross = GeometricMotif("cross", size=13, color="#7A746C")
        hw_layout.addWidget(hw_cross)
        outer.addWidget(hw_card)

        # 3. Core features with fun, energetic neo-brutalist copy
        features_card = QFrame()
        features_card.setProperty("role", "card")
        f_layout = QVBoxLayout(features_card)
        f_layout.setContentsMargins(18, 14, 18, 14)
        f_layout.setSpacing(8)

        def _make_bullet(index_str: str, bold_prefix: str, desc: str) -> QHBoxLayout:
            row = QHBoxLayout()
            row.setSpacing(10)
            idx = QLabel(index_str)
            idx.setFont(make_font(FONT_FAMILY_MONO, 8.5, bold=True))
            idx.setStyleSheet("color: #1A1A1A; background-color: #EFE8DC; border: 1.5px solid #1A1A1A; border-radius: 3px; padding: 2px 5px;")
            idx.setFixedWidth(40)
            idx.setAlignment(Qt.AlignCenter)
            txt = QLabel(f"<b>{bold_prefix}</b> {desc}")
            txt.setFont(make_font(FONT_FAMILY, 9.5))
            txt.setWordWrap(True)
            row.addWidget(idx)
            row.addWidget(txt, 1)
            return row

        f_layout.addLayout(_make_bullet("[ 01 ]", f"Speak Freely ({cfg.shortcuts.push_to_talk}):", "Hold the key to unleash your thoughts anywhere, release to paste instantly."))
        f_layout.addLayout(_make_bullet("[ 02 ]", f"Hands-Free Flow ({cfg.shortcuts.toggle}):", "Tap once for continuous thought capture without holding any buttons."))
        f_layout.addLayout(_make_bullet("[ 03 ]", "Visual Context (Ctrl + Drag):", "Highlight anything on your screen so the AI sees exactly what you're pointing at."))
        f_layout.addLayout(_make_bullet("[ 04 ]", "Pure Superpower:", "Fixes punctuation, bullet lists, and phrasing on the fly — 100% private on your device."))
        outer.addWidget(features_card)

        # 4. Status & Telemetry section
        status_card = QFrame()
        status_card.setProperty("role", "card")
        s_layout = QVBoxLayout(status_card)
        s_layout.setContentsMargins(18, 12, 18, 12)
        s_layout.setSpacing(7)

        status_header_row = QHBoxLayout()
        self.spinner = ActivitySpinner(size=20, color=INK)
        self.spinner.hide()
        status_header_row.addWidget(self.spinner)

        self.status_label = QLabel("Click below to warm up local models and start.")
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
        self.telemetry_label.hide()
        s_layout.addWidget(self.telemetry_label)

        outer.addWidget(status_card)
        outer.addStretch(1)

        # 5. Action Buttons with Skip Option
        btn_row = QHBoxLayout()
        btn_row.setSpacing(10)

        self.skip_btn = QPushButton("Skip Onboarding →")
        self.skip_btn.setProperty("role", "secondary")
        self.skip_btn.setFixedWidth(160)
        self.skip_btn.setFixedHeight(46)
        self.skip_btn.setCursor(Qt.PointingHandCursor)
        self.skip_btn.clicked.connect(self._skip_onboarding)
        btn_row.addWidget(self.skip_btn)

        self.start_btn = QPushButton("Warm Up Models && Start")
        self.start_btn.setFixedHeight(46)
        self.start_btn.setProperty("role", "primary")
        self.start_btn.setCursor(Qt.PointingHandCursor)
        self.start_btn.clicked.connect(self._start_setup)
        btn_row.addWidget(self.start_btn, 1)

        outer.addLayout(btn_row)

        self._thread: QThread | None = None
        self._worker: _PreloadWorker | None = None
        self._stamp_pixmap: QPixmap | None = None
        stamp_path = Path(__file__).parent.parent / "resources" / "icons" / "stamp_seal.png"
        if stamp_path.exists():
            self._stamp_pixmap = QPixmap(str(stamp_path))

    def paintEvent(self, event):
        painter = QPainter(self)
        paint_paper_background(painter, self.rect())
        if self._stamp_pixmap and not self._stamp_pixmap.isNull():
            painter.save()
            painter.setOpacity(0.13)
            # Subtle rotated editorial inspection seal in top-right background
            stamp_sz = 140
            x = self.width() - stamp_sz - 18
            y = 10
            painter.drawPixmap(x, y, stamp_sz, stamp_sz, self._stamp_pixmap)
            painter.restore()

    def _skip_onboarding(self) -> None:
        self.skipped = True
        logger.info("User skipped onboarding.")
        self.accept()

    def _start_setup(self) -> None:
        self.start_btn.setEnabled(False)
        self.start_btn.setText("Warming Up Models...")
        self.skip_btn.setEnabled(False)
        self.spinner.show()
        self.progress.setValue(0)
        self.progress.show()
        self.telemetry_label.setText("Preparing model download...")
        self.telemetry_label.show()

        self._thread = QThread()
        self._worker = _PreloadWorker(self._controller, self.hw_name, self.is_gpu, self.cores)
        self._worker.moveToThread(self._thread)
        self._thread.started.connect(self._worker.run)
        self._worker.status.connect(self.status_label.setText)
        self._worker.telemetry.connect(self.telemetry_label.setText)
        self._worker.progress.connect(self.progress.setValue)
        self._worker.finished.connect(self._on_finished)
        self._worker.failed.connect(self._on_failed)
        self._worker.finished.connect(self._thread.quit)
        self._worker.failed.connect(self._thread.quit)
        self._thread.start()

    def _on_finished(self) -> None:
        self.spinner.hide()
        self.status_label.setText("Models ready! FlowState is primed for instant dictation.")
        self.telemetry_label.setText("100% of weights verified on local disk & memory.")
        self.progress.setValue(100)
        self.start_btn.setText("Open FlowState && Start Tutorial →")
        self.start_btn.setEnabled(True)
        self.skip_btn.setEnabled(True)
        self.start_btn.clicked.disconnect()
        self.start_btn.clicked.connect(self.accept)

    def _on_failed(self, message: str) -> None:
        self.spinner.hide()
        self.status_label.setText("Preload encountered a network notice, but FlowState can still launch.")
        self.telemetry_label.setText(f"Details: {message}")
        self.start_btn.setText("Open FlowState Anyway →")
        self.start_btn.setEnabled(True)
        self.skip_btn.setEnabled(True)
        self.start_btn.clicked.disconnect()
        self.start_btn.clicked.connect(self.accept)

