"""Downloads a FlowState installer and launches it to perform a self-update.

Deliberately Qt-free so the download/launch logic is unit-testable without
a QApplication; ui/update_installer.py wraps this in a QThread worker with
progress reporting for the actual "click Update" flow.
"""

from __future__ import annotations

import logging
import subprocess
import threading
import urllib.error
import urllib.request
from pathlib import Path
from typing import Callable

from . import paths

logger = logging.getLogger("flowstate.updater")

_CHUNK_SIZE = 256 * 1024


class UpdateDownloadError(Exception):
    pass


class UpdateCancelled(Exception):
    pass


def updates_dir() -> Path:
    path = paths.app_data_dir() / "updates"
    path.mkdir(parents=True, exist_ok=True)
    return path


def download_installer(
    url: str,
    version: str,
    on_progress: Callable[[int, int], None] | None = None,
    cancel_event: threading.Event | None = None,
) -> Path:
    """Streams the installer into app_data/updates/. Downloads to a .part
    file and only renames to the final name once the byte count matches
    the server's declared Content-Length (when it sent one) -- a half
    finished download can never be mistaken for a complete installer, and
    a stale one from a previous failed attempt is overwritten, not
    silently reused."""
    destination = updates_dir() / f"FlowStateSetup-{version}.exe"
    partial = destination.with_name(destination.name + ".part")

    request = urllib.request.Request(url, headers={"User-Agent": "FlowState-Updater"})
    downloaded = 0
    try:
        with urllib.request.urlopen(request, timeout=15) as response:
            total = int(response.headers.get("Content-Length") or 0)
            with open(partial, "wb") as f:
                while True:
                    if cancel_event is not None and cancel_event.is_set():
                        raise UpdateCancelled()
                    chunk = response.read(_CHUNK_SIZE)
                    if not chunk:
                        break
                    f.write(chunk)
                    downloaded += len(chunk)
                    if on_progress:
                        on_progress(downloaded, total)
    except UpdateCancelled:
        partial.unlink(missing_ok=True)
        raise
    except (urllib.error.URLError, TimeoutError, OSError) as exc:
        partial.unlink(missing_ok=True)
        raise UpdateDownloadError(str(exc)) from exc

    if downloaded == 0:
        partial.unlink(missing_ok=True)
        raise UpdateDownloadError("Downloaded file was empty")
    if total and downloaded != total:
        partial.unlink(missing_ok=True)
        raise UpdateDownloadError(f"Download incomplete: got {downloaded} of {total} bytes")

    partial.replace(destination)
    return destination


def launch_installer_and_exit(installer_path: Path) -> None:
    """Starts the installer silently, detached from this process, so it
    can overwrite this app's own files once this process has exited.
    installer.iss declares AppMutex against this app's own single-instance
    mutex and its [Run] entry has no skipifsilent, so Setup will close and
    relaunch FlowState around the file replacement even if this process is
    slow to exit on its own."""
    args = [
        str(installer_path),
        "/VERYSILENT",
        "/SUPPRESSMSGBOXES",
        "/NORESTART",
        "/SP-",
        "/CLOSEAPPLICATIONS",
        "/RESTARTAPPLICATIONS",
    ]
    subprocess.Popen(
        args,
        close_fds=True,
        creationflags=subprocess.DETACHED_PROCESS | subprocess.CREATE_NEW_PROCESS_GROUP,
    )
