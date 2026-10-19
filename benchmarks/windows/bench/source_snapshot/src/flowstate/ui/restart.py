"""Application restart helper.

Spawns a new instance of FlowState detached from the current process,
allowing operating system handles to release cleanly before relaunching.
"""

from __future__ import annotations

import logging
import subprocess
import sys

from PySide6.QtWidgets import QApplication

logger = logging.getLogger("flowstate.restart")


def restart_flowstate() -> None:
    """Relaunches FlowState and terminates the current process."""
    logger.info("Initiating FlowState restart...")

    if getattr(sys, "frozen", False):
        exe = sys.executable
        cmd = f'ping 127.0.0.1 -n 2 > nul & start "" "{exe}"'
    else:
        exe = sys.executable
        cmd = f'ping 127.0.0.1 -n 2 > nul & start "" "{exe}" -m flowstate'

    subprocess.Popen(
        cmd,
        shell=True,
        creationflags=subprocess.DETACHED_PROCESS | subprocess.CREATE_NEW_PROCESS_GROUP,
        close_fds=True,
    )

    app = QApplication.instance()
    if app:
        app.quit()
    else:
        sys.exit(0)
