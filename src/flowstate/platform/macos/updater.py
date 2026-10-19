"""Installs a downloaded FlowState-macOS.zip over the running FlowState.app.

The running app cannot replace its own bundle, so a small detached shell
script waits for this process to exit, swaps the bundles (keeping the old
one until the new one is in place), clears the download quarantine flag
and reopens FlowState.
"""

from __future__ import annotations

import os
import shlex
import subprocess
from pathlib import Path

from .system import app_bundle

_SCRIPT = """
pid={pid}; archive={archive}; target={target}
while kill -0 "$pid" 2>/dev/null; do sleep 0.2; done
work=$(mktemp -d) || exit 1
/usr/bin/ditto -x -k "$archive" "$work" || exit 1
new=$(/usr/bin/find "$work" -maxdepth 2 -name "*.app" -type d | head -n 1)
[ -n "$new" ] || exit 1
rm -rf "$target.previous"
if mv "$target" "$target.previous" && /usr/bin/ditto "$new" "$target"; then
  rm -rf "$target.previous"
else
  rm -rf "$target"; mv "$target.previous" "$target"
fi
/usr/bin/xattr -dr com.apple.quarantine "$target" 2>/dev/null
rm -rf "$work"
/usr/bin/open "$target"
"""


def install_and_relaunch(archive: Path) -> None:
    bundle = app_bundle()
    if bundle is None:
        raise OSError("Updates install automatically only in the packaged FlowState.app")
    script = _SCRIPT.format(pid=os.getpid(), archive=shlex.quote(str(archive)), target=shlex.quote(str(bundle)))
    subprocess.Popen(["/bin/sh", "-c", script], start_new_session=True, close_fds=True)
