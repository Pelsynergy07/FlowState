"""Application restart helper.

Spawns a new instance of FlowState detached from the current process,
allowing operating system handles to release cleanly before relaunching.
"""

from __future__ import annotations

import logging
import sys

from PySide6.QtWidgets import QApplication

from .. import platform

logger = logging.getLogger("flowstate.restart")


def restart_flowstate() -> None:
    """Relaunches FlowState and terminates the current process."""
    logger.info("Initiating FlowState restart...")
    platform.adapter("system").spawn_relaunch()

    app = QApplication.instance()
    if app:
        app.quit()
    else:
        sys.exit(0)
