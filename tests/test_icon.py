from PySide6.QtWidgets import QApplication
from flowstate.ui.icon import build_app_icon, build_tray_icon


def test_build_tray_icon_idle_and_recording():
    app = QApplication.instance() or QApplication([])
    idle = build_tray_icon(recording=False)
    assert not idle.isNull()

    rec = build_tray_icon(recording=True)
    assert not rec.isNull()


def test_build_app_icon():
    app = QApplication.instance() or QApplication([])
    icon = build_app_icon()
    assert not icon.isNull()
