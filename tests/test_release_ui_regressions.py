import json
import threading
from unittest.mock import patch
import pytest
from PySide6.QtWidgets import QPlainTextEdit
from PySide6.QtTest import QTest
from flowstate.app import ControllerSignals
from flowstate.update_check import UpdateCheckError, UpdateInfo, _ReleaseInfo, check_for_update
from tests.test_history_workflow import history_ui, save, texts


def test_history_detects_completed_files_without_completion_callback(history_ui):
    app, root, window, _ = history_ui
    save(root, '20261005-191500-abcdef', 'Complete saved text with final words.')
    window._poll_history()
    app.processEvents()
    assert texts(window) == ['Complete saved text with final words.']
    editor = window._history_content.findChildren(QPlainTextEdit)[-1]
    window._poll_history()
    assert not editor.isHidden()


def test_real_worker_completion_refreshes_history_on_qt_thread(history_ui):
    app, root, window, _ = history_ui
    signals = ControllerSignals()
    signals.recording_finished.connect(window._on_recording_finished)
    save(root, '20261005-191500-abcdef', 'Saved by background transcription.')
    worker = threading.Thread(target=lambda: signals.recording_finished.emit('done'))
    worker.start(); worker.join()
    QTest.qWait(50)
    assert texts(window) == ['Saved by background transcription.']
    assert window._history_content.thread() == app.thread()


def test_manual_update_check_keeps_signals_and_shows_available_action(history_ui):
    app, _, window, _ = history_ui
    info = UpdateInfo('1.0.3-beta', 'https://github.com/Pelsynergy07/FlowState/releases/tag/v1.0.3-beta')
    reported = []
    window.update_checked.connect(reported.append)
    with patch('flowstate.ui.settings_window.check_for_update_async') as check:
        window._manual_check_updates()
        check.assert_called_once_with(window._update_signals, force=True)
        window._manual_check_updates()
        assert check.call_count == 1
    worker = threading.Thread(target=lambda: window._update_signals.checked.emit(info))
    worker.start(); worker.join(); QTest.qWait(50)
    assert window._header_download_btn.isVisible()
    assert '1.0.3-beta' in window._header_download_btn.text()
    assert reported == [info]
    assert window._check_update_btn.isEnabled()


def test_failed_update_check_does_not_claim_up_to_date(history_ui):
    _, _, window, _ = history_ui
    with patch('flowstate.ui.settings_window.check_for_update_async'):
        window._manual_check_updates()
    window._update_signals.failed.emit('Could not reach GitHub. Try again.')
    assert 'Could not reach GitHub' in window._update_status_lbl.text()
    assert window._check_update_btn.isEnabled()
    assert not window._update_check_running


def test_opening_application_rechecks_releases_without_stale_cache(history_ui):
    app, _, window, _ = history_ui
    window._on_update_requested = lambda info: None
    window.hide()
    with patch('flowstate.ui.settings_window.check_for_update_async') as check:
        window.show(); app.processEvents()
        check.assert_called_once_with(window._update_signals, force=True)


@pytest.mark.parametrize('cache', [[], {'checked_at':'broken'}, {'checked_at':float('inf')}])
def test_invalid_cache_does_not_disable_updates(tmp_path, cache):
    path=tmp_path/'cache.json'; path.write_text(json.dumps(cache))
    release=_ReleaseInfo('v1.0.3-beta', 'https://example.com/release',None,None)
    with patch('flowstate.update_check._fetch_latest_release',return_value=release):
        assert check_for_update(cache_path=path,current_version='1.0.1-beta').version == '1.0.3-beta'


def test_network_failure_can_be_reported_without_destroying_cached_update(tmp_path):
    path=tmp_path/'cache.json'
    path.write_text(json.dumps({'checked_at':0,'latest_tag':'v1.0.2-beta'}))
    with patch('flowstate.update_check._fetch_latest_release',side_effect=UpdateCheckError('Offline')):
        with pytest.raises(UpdateCheckError,match='Offline'):
            check_for_update(force=True,cache_path=path,raise_on_error=True)
        assert check_for_update(force=True,cache_path=path) is None
    assert json.loads(path.read_text())['latest_tag']=='v1.0.2-beta'
