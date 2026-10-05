"""Local statistics and an explicit, immediately applied sharing preference."""
from PySide6.QtCore import QTimer, Slot
from PySide6.QtWidgets import QFileDialog, QGridLayout, QHBoxLayout, QLabel, QMessageBox, QPushButton, QVBoxLayout, QWidget
import json

from ..usage import UsageStore, analytics_config
from .widgets import BrutalistCheckBox


class UsageStatsView(QWidget):
    def __init__(self, config_store, tracker=None):
        super().__init__()
        self.config_store, self.tracker = config_store, tracker
        self.store = tracker.store if tracker is not None else UsageStore(config_store._path.with_name("usage.sqlite3"))
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 20, 4, 8)
        layout.setSpacing(18)
        title = QLabel("Your voice, in numbers.")
        title.setStyleSheet("font-size: 22px; font-weight: 700;")
        layout.addWidget(title)
        note = QLabel("Lifetime totals on this PC. These survive app restarts and history clearing.")
        note.setWordWrap(True)
        note.setProperty("role", "muted")
        layout.addWidget(note)
        grid = QGridLayout()
        grid.setHorizontalSpacing(30)
        grid.setVerticalSpacing(18)
        self.values = {}
        for index, (key, name) in enumerate((("words", "WORDS TRANSCRIBED"), ("sessions", "DICTATION SESSIONS"),
                                           ("audio", "RECORDING MINUTES"), ("median", "MEDIAN TIME TO PASTE"))):
            block = QVBoxLayout()
            label = QLabel(name)
            label.setProperty("role", "eyebrow")
            value = QLabel("0")
            value.setStyleSheet("font-size: 30px; font-weight: 700;")
            block.addWidget(label)
            block.addWidget(value)
            self.values[key] = value
            grid.addLayout(block, index // 2, index % 2)
        layout.addLayout(grid)
        self.detail = QLabel()
        self.detail.setWordWrap(True)
        self.detail.setProperty("role", "muted")
        layout.addWidget(self.detail)
        self.week = QLabel()
        self.week.setWordWrap(True)
        layout.addWidget(self.week)
        sharing_title = QLabel("Help FlowState get better")
        sharing_title.setStyleSheet("font-size: 16px; font-weight: 700;")
        layout.addWidget(sharing_title)
        configured = tracker.configured if tracker is not None else bool(analytics_config()[0])
        self.sharing = BrutalistCheckBox("Share anonymous usage counts and processing times",
                                       checked=config_store.config.analytics.enabled is True and configured)
        self.sharing.setEnabled(configured)
        self.sharing.toggled.connect(self._set_consent)
        layout.addWidget(self.sharing)
        privacy = QLabel("Off by default. Applies immediately. No audio, text, screenshots, clipboard content, "
                         "account details, or error messages are shared. A random app ID lets us count returning installations. "
                         "Turning sharing off clears unsent events and resets that ID.")
        privacy.setWordWrap(True)
        privacy.setProperty("role", "muted")
        layout.addWidget(privacy)
        self.sync_status = QLabel()
        self.sync_status.setWordWrap(True)
        self.sync_status.setProperty("role", "muted")
        layout.addWidget(self.sync_status)
        row = QHBoxLayout()
        export = QPushButton("Export my stats")
        export.setProperty("role", "secondary")
        export.clicked.connect(self._export)
        reset = QPushButton("Reset local stats")
        reset.setProperty("role", "secondary")
        reset.clicked.connect(self._reset)
        row.addWidget(export)
        row.addWidget(reset)
        row.addStretch(1)
        layout.addLayout(row)
        layout.addStretch(1)
        self.timer = QTimer(self)
        self.timer.setInterval(2000)
        self.timer.timeout.connect(self._refresh_if_visible)
        self.timer.start()
        self.refresh()

    @Slot(bool)
    def _set_consent(self, enabled):
        self.config_store.config.analytics.enabled = enabled
        self.config_store.save()
        self.refresh()

    @Slot()
    def _refresh_if_visible(self):
        if self.isVisible():
            self.refresh()

    @Slot()
    def refresh(self):
        data = self.store.snapshot()
        self.values["words"].setText(f'{data["words"]:,}')
        self.values["sessions"].setText(f'{data["sessions"]:,}')
        self.values["audio"].setText(f'{data["audio_seconds"] / 60:,.1f}')
        self.values["median"].setText("—" if data["median_seconds"] is None else f'{data["median_seconds"]:.2f}s')
        p95 = "—" if data["p95_seconds"] is None else f'{data["p95_seconds"]:.2f}s'
        self.detail.setText(f'{data["successes"]:,} successful · {data["errors"]:,} failed · '
                            f'{data["empty"]:,} without speech · {data["active_days"]:,} active days\n'
                            f'95th-percentile time to paste: {p95}. Timing covers the latest 1,000 successful sessions.')
        if data["sessions"]:
            self.week.setText("RECENT ACTIVITY\n" + "\n".join(f"{day}    {words:,} words · {sessions:,} sessions"
                                                           for day, words, sessions in data["days"]))
        else:
            self.week.setText("Your first dictation will start these totals. Older recordings are not counted retroactively.")
        configured = self.tracker.configured if self.tracker is not None else bool(analytics_config()[0])
        if not configured:
            status = "Local stats are ready. Anonymous sharing is not available in this build."
        elif self.config_store.config.analytics.enabled is not True:
            status = "Sharing is off. Your statistics stay on this PC."
        elif self.tracker is not None and self.tracker.sync_error:
            status = "Offline or unable to sync. Anonymous counts will retry in the background."
        elif self.tracker is not None and self.tracker.last_sync is not None:
            status = "Anonymous counts last synced at " + self.tracker.last_sync.strftime("%H:%M") + "."
        else:
            status = "Sharing is on. New usage counts will sync in the background."
        self.sync_status.setText(status)

    def _export(self):
        filename, _ = QFileDialog.getSaveFileName(self, "Export local statistics", "FlowState-stats.json", "JSON (*.json)")
        if filename:
            try:
                from pathlib import Path
                Path(filename).write_text(json.dumps(self.store.snapshot(), indent=2), encoding="utf-8")
            except OSError:
                QMessageBox.warning(self, "FlowState", "Could not save the statistics file. Choose another location.")

    def _reset(self):
        if QMessageBox.question(self, "Reset local statistics?", "Clear this PC's counters? This does not delete recordings "
                                "or remove counts already shared.", QMessageBox.Yes | QMessageBox.No, QMessageBox.No) == QMessageBox.Yes:
            self.store.reset()
            self.refresh()
