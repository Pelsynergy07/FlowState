"""The dialog that runs after the user clicks "Update available" in the
tray: downloads the installer with a real progress bar (same QThread
worker pattern as onboarding.py's model downloads), then hands off to the
installer and closes. On any failure, offers the release page as a
fallback rather than leaving the user stuck.
"""

from __future__ import annotations

import logging
import os
import threading
from pathlib import Path

from PySide6.QtCore import Qt, QThread, QObject, Signal
from PySide6.QtWidgets import QDialog, QLabel, QMessageBox, QProgressBar, QPushButton, QVBoxLayout

from ..update_check import UpdateInfo
from ..updater import UpdateCancelled, UpdateDownloadError, download_installer, launch_installer_and_exit
from .theme import build_stylesheet

logger = logging.getLogger("flowstate.updater")


class _UpdateDownloadWorker(QObject):
    progress = Signal(int, int)  # bytes_done, total_bytes (0 = unknown)
    ready_to_launch = Signal(str)  # installer path
    failed = Signal(str)
    cancelled = Signal()

    def __init__(self, info: UpdateInfo):
        super().__init__()
        self._info = info
        self.cancel_event = threading.Event()

    def run(self) -> None:
        if not self._info.download_url:
            self.failed.emit("This release doesn't have a downloadable installer attached.")
            return
        try:
            installer_path = download_installer(
                self._info.download_url,
                self._info.version,
                on_progress=self.progress.emit,
                cancel_event=self.cancel_event,
            )
        except UpdateCancelled:
            self.cancelled.emit()
            return
        except UpdateDownloadError as exc:
            logger.warning("Update download failed: %s", exc)
            self.failed.emit(str(exc))
            return
        self.ready_to_launch.emit(str(installer_path))


class UpdateInstallDialog(QDialog):
    def __init__(self, info: UpdateInfo):
        super().__init__()
        self._info = info
        self.succeeded = False
        self.setWindowTitle("Updating FlowState")
        self.setStyleSheet(build_stylesheet())
        self.setFixedSize(420, 180)
        self.setWindowFlags(self.windowFlags() & ~Qt.WindowContextHelpButtonHint)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(30, 26, 30, 26)
        layout.setSpacing(14)

        headline = QLabel(f"Updating to v{info.version}")
        headline.setProperty("role", "headline")
        self.status_label = QLabel("Downloading update...")
        self.status_label.setProperty("role", "muted")
        self.status_label.setWordWrap(True)

        self.progress = QProgressBar()
        self.progress.setRange(0, 100)

        self.cancel_btn = QPushButton("Cancel")
        self.cancel_btn.setProperty("role", "secondary")
        self.cancel_btn.clicked.connect(self._cancel)

        layout.addWidget(headline)
        layout.addWidget(self.status_label)
        layout.addWidget(self.progress)
        layout.addStretch(1)
        layout.addWidget(self.cancel_btn)

        self._thread = QThread()
        self._worker = _UpdateDownloadWorker(info)
        self._worker.moveToThread(self._thread)
        self._thread.started.connect(self._worker.run)
        self._worker.progress.connect(self._on_progress)
        self._worker.ready_to_launch.connect(self._on_ready_to_launch)
        self._worker.failed.connect(self._on_failed)
        self._worker.cancelled.connect(self._on_cancelled)
        self._worker.ready_to_launch.connect(self._thread.quit)
        self._worker.failed.connect(self._thread.quit)
        self._worker.cancelled.connect(self._thread.quit)
        self._thread.start()

    def _on_progress(self, done: int, total: int) -> None:
        mb_done = done / (1024 * 1024)
        if total:
            self.progress.setRange(0, 100)
            self.progress.setValue(int(done / total * 100))
            self.status_label.setText(f"Downloading update... {mb_done:.0f}MB / {total / (1024 * 1024):.0f}MB")
        else:
            self.progress.setRange(0, 0)  # indeterminate -- server didn't report a size
            self.status_label.setText(f"Downloading update... {mb_done:.0f}MB")

    def _on_ready_to_launch(self, installer_path: str) -> None:
        self.status_label.setText("Starting installer -- FlowState will restart shortly...")
        self.progress.setRange(0, 0)
        self.cancel_btn.setEnabled(False)
        try:
            launch_installer_and_exit(Path(installer_path))
        except OSError as exc:
            logger.error("Failed to launch installer", exc_info=True)
            self._on_failed(f"Downloaded the update but couldn't start the installer: {exc}")
            return
        self.succeeded = True
        self.accept()

    def _on_failed(self, message: str) -> None:
        box = QMessageBox(self)
        box.setWindowTitle("FlowState")
        box.setIcon(QMessageBox.Warning)
        box.setText(f"Couldn't complete the update automatically:\n\n{message}")
        box.setInformativeText("You can download it manually from the release page instead.")
        open_btn = box.addButton("Open Release Page", QMessageBox.ActionRole)
        box.addButton(QMessageBox.Close)
        box.exec()
        if box.clickedButton() is open_btn:
            os.startfile(self._info.url)
        self.reject()

    def _on_cancelled(self) -> None:
        self.reject()

    def _cancel(self) -> None:
        self.status_label.setText("Cancelling...")
        self.cancel_btn.setEnabled(False)
        self._worker.cancel_event.set()

    def closeEvent(self, event) -> None:
        self._worker.cancel_event.set()
        self._thread.quit()
        self._thread.wait(2000)
        super().closeEvent(event)
