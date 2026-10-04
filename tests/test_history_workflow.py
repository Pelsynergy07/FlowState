from types import SimpleNamespace
from datetime import datetime
from unittest.mock import patch

import pytest
from PySide6.QtCore import QCoreApplication, QEvent, QTimer
from PySide6.QtWidgets import QApplication, QPlainTextEdit, QPushButton

from flowstate.config import ConfigStore
from flowstate.session import store
from flowstate.session.model import Session
from flowstate.ui.settings_window import SettingsWindow


@pytest.fixture
def history_ui(tmp_path, monkeypatch):
    app = QApplication.instance() or QApplication([])
    root = tmp_path / "sessions"
    root.mkdir()
    monkeypatch.setattr(store.paths, "sessions_dir", lambda: root)
    monkeypatch.setattr("flowstate.ui.settings_window.list_input_devices", lambda: [])
    controller = SimpleNamespace(is_recording=False, is_processing=False)
    window = SettingsWindow(ConfigStore(path=tmp_path / "config.json"), controller=controller)
    window.show()
    window.tabs.setCurrentIndex(5)
    app.processEvents()
    yield app, root, window, controller
    window.close()
    window.deleteLater()
    QCoreApplication.sendPostedEvents(None, QEvent.DeferredDelete)


def save(root, identifier, text):
    folder = root / identifier
    folder.mkdir()
    session = Session(identifier, datetime.now(), folder, transcript=text)
    store.save_session(session)
    (folder / "raw_transcript.txt").write_text("raw speech", encoding="utf-8")
    (folder / "audio.wav").write_bytes(b"audio")
    (folder / "capture.png").write_bytes(b"image")
    return session


def texts(window):
    return [edit.toPlainText() for edit in window._history_content.findChildren(QPlainTextEdit)]


def test_new_recording_refreshes_open_history_and_copies_complete_text(history_ui):
    app, root, window, _ = history_ui
    full = "  Dear John,\n\n" + "Complete text 60 pages. " * 300 + "\n\nThanks\nPranav\n"
    save(root, "20261005-012000-aaaaaa", full)
    window.refresh_history()
    app.processEvents()
    assert texts(window) == [full]
    copy = next(btn for btn in window._history_content.findChildren(QPushButton) if btn.text() == "COPY TEXT")
    copy.click()
    assert app.clipboard().text() == full
    timer = copy.findChild(QTimer)
    assert timer.isActive()
    window.refresh_history()
    QCoreApplication.sendPostedEvents(None, QEvent.DeferredDelete)
    app.processEvents()
    assert texts(window) == [full]


def test_switching_tabs_loads_latest_completed_sessions_newest_first(history_ui):
    app, root, window, _ = history_ui
    window.tabs.setCurrentIndex(0)
    save(root, "20261005-012000-aaaaaa", "old")
    save(root, "20261005-012100-bbbbbb", "new")
    (root / "20261005-012200-cccccc").mkdir()  # recording not saved yet
    window.tabs.setCurrentIndex(5)
    app.processEvents()
    assert texts(window) == ["new", "old"]


def test_clear_history_removes_audio_images_and_transcripts_and_updates_ui(history_ui):
    app, root, window, _ = history_ui
    session = save(root, "20261005-012000-aaaaaa", "complete")
    window.refresh_history()
    cleared = []
    window.history_cleared.connect(lambda: cleared.append(True))
    with patch("flowstate.ui.settings_window.QMessageBox.information"):
        window._purge_history()
    QCoreApplication.sendPostedEvents(None, QEvent.DeferredDelete)
    app.processEvents()
    assert not session.folder.exists()
    assert texts(window) == []
    assert cleared == [True]


@pytest.mark.parametrize("activity", ["is_recording", "is_processing"])
def test_clear_history_during_active_work_keeps_session_folder(history_ui, activity):
    _, root, window, controller = history_ui
    session = save(root, "20261005-012000-aaaaaa", "still in use")
    setattr(controller, activity, True)
    with patch("flowstate.ui.settings_window.QMessageBox.information") as message:
        window._purge_history()
    assert session.folder.exists()
    assert "Finish recording and processing" in message.call_args.args[2]


def test_failed_purge_is_not_counted_as_deleted(history_ui):
    _, root, _, _ = history_ui
    session = save(root, "20261005-012000-aaaaaa", "locked")
    with patch("flowstate.session.store.shutil.rmtree"):
        assert store.purge_all_sessions() == []
    assert session.folder.exists()


def test_startup_purge_leaves_empty_history(history_ui):
    _, root, window, _ = history_ui
    save(root, "20261005-012000-aaaaaa", "previous run")
    assert len(store.purge_all_sessions()) == 1
    window._refresh_history_list()
    assert store.list_sessions() == []
    assert texts(window) == []
