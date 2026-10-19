"""macOS adapter logic that runs without macOS permissions: key mapping,
shortcut defaults and the config upgrade."""

import sys

import pytest

from flowstate.config import config_from_dict
from flowstate.hotkeys.manager import HotkeyManager

@pytest.fixture(scope="module")
def qapp():
    from PySide6.QtWidgets import QApplication

    return QApplication.instance() or QApplication([])


mac = pytest.mark.skipif(sys.platform != "darwin", reason="macOS adapter")


@mac
def test_fn_key_and_modifiers_map_to_shared_tokens():
    from flowstate.platform.macos.keyboard import keycode_to_tokens, modifier_is_down

    assert keycode_to_tokens(0x3F) == {"fn"}
    assert keycode_to_tokens(0x3D) == {"alt_r", "alt"}
    assert keycode_to_tokens(0x31) == {"space"}
    assert modifier_is_down(0x3F, 0x00800000) is True
    assert modifier_is_down(0x3F, 0) is False


@mac
def test_mac_defaults_are_fn_shift_space_and_shift_drag():
    from flowstate import platform

    assert platform.default_shortcuts() == ("fn+shift+space", "alt_r")
    assert platform.drag_modifier_token() == "shift"


@mac
def test_old_mac_toggle_default_is_upgraded_but_custom_ones_kept():
    assert config_from_dict({"shortcuts": {"toggle": "ctrl+shift+space"}}).shortcuts.toggle == "fn+shift+space"
    assert config_from_dict({"shortcuts": {"toggle": "ctrl+alt+d"}}).shortcuts.toggle == "ctrl+alt+d"


def test_fn_shift_space_toggles_and_swallows_only_the_chord():
    calls = []
    mgr = HotkeyManager(lambda: calls.append("toggle"), lambda: calls.append("ptt"), lambda: calls.append("stop"),
                        toggle_spec="fn+shift+space", push_to_talk_spec="alt_r")
    assert mgr._on_keydown({"fn"}) is False
    assert mgr._on_keydown({"shift_l", "shift"}) is False  # Shift alone still types and drags
    assert mgr._on_keydown({"space"}) is True
    assert calls == ["toggle"]
    for key in ({"space"}, {"shift_l", "shift"}, {"fn"}):
        mgr._on_keyup(key)
    mgr._on_keydown({"fn"})
    mgr._on_keydown({"shift_l", "shift"})
    mgr._on_keydown({"space"})
    assert calls == ["toggle", "toggle"]


def test_screenshot_step_is_short_numbered_steps(qapp):
    from flowstate.ui.onboarding import OnboardingDialog
    from tests.test_onboarding import DummyController

    dlg = OnboardingDialog(DummyController())
    page = dlg.stack.widget(dlg.pages.index("capture")).widget()
    from PySide6.QtWidgets import QLabel

    texts = [label.text() for label in page.findChildren(QLabel)]
    assert [t for t in texts if t in ("1", "2", "3", "4")] == ["1", "2", "3", "4"]
    assert all(len(t) < 140 for t in texts)
    dlg.close()


@mac
def test_dock_icon_follows_settings_windows_not_the_recording_bar(qapp):
    from PySide6.QtCore import Qt
    from PySide6.QtWidgets import QDialog, QWidget

    from flowstate.platform.macos.system import _is_app_window

    settings = QDialog()
    hud = QWidget()
    hud.setWindowFlags(Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint | Qt.Tool)
    settings.show()
    hud.show()
    assert _is_app_window(settings) is True
    assert _is_app_window(hud) is False
    settings.hide()
    assert _is_app_window(settings) is False
    hud.close()
