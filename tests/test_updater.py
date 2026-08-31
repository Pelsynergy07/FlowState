import threading
from unittest.mock import patch

import pytest

from flowstate.updater import UpdateCancelled, UpdateDownloadError, download_installer, launch_installer_and_exit


class _FakeResponse:
    def __init__(self, data: bytes, content_length: int | None = None):
        self._data = data
        self._pos = 0
        self.headers = {} if content_length is None else {"Content-Length": str(content_length)}

    def read(self, n: int) -> bytes:
        chunk = self._data[self._pos : self._pos + n]
        self._pos += len(chunk)
        return chunk

    def __enter__(self):
        return self

    def __exit__(self, *exc_info):
        return False


@pytest.fixture(autouse=True)
def isolated_app_data(tmp_path, monkeypatch):
    monkeypatch.setattr("flowstate.updater.paths.app_data_dir", lambda: tmp_path)
    return tmp_path


def test_download_installer_writes_full_content(tmp_path):
    payload = b"fake installer bytes" * 100
    with patch("flowstate.updater.urllib.request.urlopen", return_value=_FakeResponse(payload, len(payload))):
        result = download_installer("https://example.com/FlowStateSetup.exe", "0.2.0")

    assert result.name == "FlowStateSetup-0.2.0.exe"
    assert result.read_bytes() == payload
    assert not result.with_name(result.name + ".part").exists()


def test_download_installer_reports_progress(tmp_path):
    payload = b"x" * (600 * 1024)  # a few chunks at the 256KB chunk size
    seen = []
    with patch("flowstate.updater.urllib.request.urlopen", return_value=_FakeResponse(payload, len(payload))):
        download_installer("https://example.com/FlowStateSetup.exe", "0.2.0", on_progress=lambda d, t: seen.append((d, t)))

    assert seen[-1] == (len(payload), len(payload))
    assert all(total == len(payload) for _done, total in seen)


def test_download_installer_raises_on_length_mismatch(tmp_path):
    payload = b"short"
    with patch("flowstate.updater.urllib.request.urlopen", return_value=_FakeResponse(payload, 999)):
        with pytest.raises(UpdateDownloadError, match="incomplete"):
            download_installer("https://example.com/FlowStateSetup.exe", "0.2.0")

    updates_dir = tmp_path / "updates"
    assert list(updates_dir.glob("*.part")) == []
    assert list(updates_dir.glob("FlowStateSetup-0.2.0.exe")) == []


def test_download_installer_raises_on_empty_response(tmp_path):
    with patch("flowstate.updater.urllib.request.urlopen", return_value=_FakeResponse(b"", None)):
        with pytest.raises(UpdateDownloadError, match="empty"):
            download_installer("https://example.com/FlowStateSetup.exe", "0.2.0")


def test_download_installer_respects_cancellation(tmp_path):
    payload = b"x" * (600 * 1024)
    cancel_event = threading.Event()
    cancel_event.set()  # already cancelled before the first chunk is even read
    with patch("flowstate.updater.urllib.request.urlopen", return_value=_FakeResponse(payload, len(payload))):
        with pytest.raises(UpdateCancelled):
            download_installer("https://example.com/FlowStateSetup.exe", "0.2.0", cancel_event=cancel_event)

    updates_dir = tmp_path / "updates"
    assert list(updates_dir.glob("*")) == []


def test_download_installer_wraps_network_errors(tmp_path):
    with patch("flowstate.updater.urllib.request.urlopen", side_effect=OSError("connection refused")):
        with pytest.raises(UpdateDownloadError):
            download_installer("https://example.com/FlowStateSetup.exe", "0.2.0")


def test_launch_installer_and_exit_invokes_silent_install_flags(tmp_path):
    installer_path = tmp_path / "FlowStateSetup-0.2.0.exe"
    installer_path.write_bytes(b"stub")

    with patch("flowstate.updater.subprocess.Popen") as mock_popen:
        launch_installer_and_exit(installer_path)

    args, kwargs = mock_popen.call_args
    command = args[0]
    assert command[0] == str(installer_path)
    for flag in ("/VERYSILENT", "/SUPPRESSMSGBOXES", "/NORESTART", "/CLOSEAPPLICATIONS", "/RESTARTAPPLICATIONS"):
        assert flag in command
