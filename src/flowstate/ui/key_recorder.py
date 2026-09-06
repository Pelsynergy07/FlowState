"""Interactive key recorder widget for capturing shortcut combinations.

Provides a tactile Neo-Brutalist interface allowing users to simply click
and press keys on their physical keyboard rather than typing raw strings.
"""

from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QKeyEvent, QMouseEvent
from PySide6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from .theme import FONT_FAMILY_MONO


def _format_token_badge(token: str) -> str:
    token = token.strip().lower()
    mapping = {
        "ctrl": "CTRL",
        "ctrl_l": "L-CTRL",
        "ctrl_r": "R-CTRL",
        "alt": "ALT",
        "alt_l": "L-ALT",
        "alt_r": "R-ALT (ALT GR)",
        "shift": "SHIFT",
        "shift_l": "L-SHIFT",
        "shift_r": "R-SHIFT",
        "cmd": "WIN",
        "cmd_l": "L-WIN",
        "cmd_r": "R-WIN",
        "space": "SPACE",
        "enter": "ENTER",
        "return": "RETURN",
        "backspace": "BACKSPACE",
        "tab": "TAB",
        "escape": "ESC",
    }
    return mapping.get(token, token.upper())


class KeyRecorderWidget(QWidget):
    """Neo-Brutalist key combination recorder.

    Displays keys as tactile physical badges. When clicked or activated,
    enters recording mode and listens for the next key combination or modifier tap.
    """

    keyChanged = Signal(str)
    textChanged = Signal(str)

    def __init__(self, current_combo: str = "", parent: QWidget | None = None):
        super().__init__(parent)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self._combo: str = current_combo.strip()
        self._is_recording: bool = False
        self._pending_modifier: str | None = None

        self.setFixedHeight(54)
        self._setup_ui()
        self._render_combo()

    def sizeHint(self):
        from PySide6.QtCore import QSize
        return QSize(400, 54)

    def minimumSizeHint(self):
        from PySide6.QtCore import QSize
        return QSize(250, 54)

    def _setup_ui(self) -> None:
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(6)

        # Container card
        self._container = QWidget()
        self._container.setObjectName("keyRecorderBox")
        self._container.setCursor(Qt.CursorShape.PointingHandCursor)

        box_layout = QHBoxLayout(self._container)
        box_layout.setContentsMargins(12, 10, 12, 10)
        box_layout.setSpacing(8)

        # Badge display area
        self._chips_container = QWidget()
        self._chips_layout = QHBoxLayout(self._chips_container)
        self._chips_layout.setContentsMargins(0, 0, 0, 0)
        self._chips_layout.setSpacing(6)
        box_layout.addWidget(self._chips_container, 1)

        # Status / prompt label (hidden when not recording)
        self._prompt_label = QLabel("[ PRESS ANY KEY COMBINATION... ]")
        self._prompt_label.setStyleSheet(
            f"font-family: {FONT_FAMILY_MONO}; font-size: 11px; font-weight: 900; color: #FFFFFF;"
        )
        self._prompt_label.setVisible(False)
        box_layout.addWidget(self._prompt_label, 1)

        # Tactile Action Buttons
        self._record_btn = QPushButton("RECORD")
        self._record_btn.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self._record_btn.setStyleSheet(
            f"""
            QPushButton {{
                background-color: #000000;
                color: #FFFFFF;
                border: 2px solid #000000;
                border-radius: 0px;
                font-family: {FONT_FAMILY_MONO};
                font-size: 10px;
                font-weight: 900;
                padding: 6px 12px;
            }}
            QPushButton:hover {{
                background-color: #222222;
            }}
            """
        )
        self._record_btn.clicked.connect(self.start_recording)
        box_layout.addWidget(self._record_btn)

        self._clear_btn = QPushButton("CLEAR")
        self._clear_btn.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self._clear_btn.setStyleSheet(
            f"""
            QPushButton {{
                background-color: #FFFFFF;
                color: #000000;
                border: 2px solid #000000;
                border-radius: 0px;
                font-family: {FONT_FAMILY_MONO};
                font-size: 10px;
                font-weight: 800;
                padding: 6px 10px;
            }}
            QPushButton:hover {{
                background-color: #EEEEEE;
            }}
            """
        )
        self._clear_btn.clicked.connect(self.clear_combo)
        box_layout.addWidget(self._clear_btn)

        main_layout.addWidget(self._container)

        self._update_container_style()

    def _update_container_style(self) -> None:
        if self._is_recording:
            self._container.setStyleSheet(
                """
                #keyRecorderBox {
                    background-color: #000000;
                    border: 2px solid #000000;
                    border-radius: 0px;
                }
                """
            )
            self._chips_container.setVisible(False)
            self._prompt_label.setVisible(True)
            self._record_btn.setText("STOP")
            self._record_btn.setStyleSheet(
                f"""
                QPushButton {{
                    background-color: #FFFFFF;
                    color: #000000;
                    border: 2px solid #FFFFFF;
                    font-family: {FONT_FAMILY_MONO};
                    font-size: 10px;
                    font-weight: 900;
                    padding: 6px 12px;
                }}
                """
            )
        else:
            self._container.setStyleSheet(
                """
                #keyRecorderBox {
                    background-color: #FFFFFF;
                    border: 2px solid #000000;
                    border-radius: 0px;
                }
                #keyRecorderBox:hover {
                    background-color: #FAFAFA;
                }
                """
            )
            self._chips_container.setVisible(True)
            self._prompt_label.setVisible(False)
            self._record_btn.setText("RECORD")
            self._record_btn.setStyleSheet(
                f"""
                QPushButton {{
                    background-color: #000000;
                    color: #FFFFFF;
                    border: 2px solid #000000;
                    font-family: {FONT_FAMILY_MONO};
                    font-size: 10px;
                    font-weight: 900;
                    padding: 6px 12px;
                }}
                QPushButton:hover {{
                    background-color: #222222;
                }}
                """
            )

    def _render_combo(self) -> None:
        # Clear existing chips
        while self._chips_layout.count():
            item = self._chips_layout.takeAt(0)
            widget = item.widget()
            if widget:
                widget.deleteLater()

        tokens = [t.strip() for t in self._combo.split("+") if t.strip()]
        if not tokens:
            empty_lbl = QLabel("NONE CONFIGURED (CLICK RECORD)")
            empty_lbl.setStyleSheet(
                f"font-family: {FONT_FAMILY_MONO}; font-size: 10px; font-weight: 700; color: #777777;"
            )
            self._chips_layout.addWidget(empty_lbl)
            self._chips_layout.addStretch(1)
            return

        for i, token in enumerate(tokens):
            if i > 0:
                plus_lbl = QLabel("+")
                plus_lbl.setStyleSheet(
                    f"font-family: {FONT_FAMILY_MONO}; font-size: 12px; font-weight: 900; color: #000000;"
                )
                self._chips_layout.addWidget(plus_lbl)

            badge = QLabel(_format_token_badge(token))
            badge.setStyleSheet(
                f"""
                background-color: #F0F0F0;
                color: #000000;
                border: 2px solid #000000;
                border-radius: 0px;
                font-family: {FONT_FAMILY_MONO};
                font-size: 11px;
                font-weight: 900;
                padding: 4px 10px;
                """
            )
            self._chips_layout.addWidget(badge)

        self._chips_layout.addStretch(1)

    def text(self) -> str:
        """Compatibility with QLineEdit.text()."""
        return self._combo

    def setText(self, value: str) -> None:
        """Compatibility with QLineEdit.setText()."""
        clean = value.strip().lower()
        if clean != self._combo:
            self._combo = clean
            self._render_combo()
            self.textChanged.emit(self._combo)
            self.keyChanged.emit(self._combo)

    def key_combination(self) -> str:
        return self._combo

    def set_key_combination(self, combo: str) -> None:
        self.setText(combo)

    def clear_combo(self) -> None:
        self.stop_recording()
        self.setText("")

    def start_recording(self) -> None:
        if self._is_recording:
            self.stop_recording()
            return
        self._is_recording = True
        self._pending_modifier = None
        self._update_container_style()
        self.setFocus()
        self.grabKeyboard()

    def stop_recording(self) -> None:
        if self._is_recording:
            self._is_recording = False
            self.releaseKeyboard()
            self._update_container_style()

    def mousePressEvent(self, event: QMouseEvent) -> None:
        if not self._is_recording:
            self.start_recording()
        super().mousePressEvent(event)

    def keyPressEvent(self, event: QKeyEvent) -> None:
        if not self._is_recording:
            super().keyPressEvent(event)
            return

        key = event.key()
        vk = event.nativeVirtualKey()

        # Escape cancels recording
        if key == Qt.Key.Key_Escape:
            self.stop_recording()
            return

        # Check for Win32 side-specific modifier keys
        # VK_RMENU = 0xA5 (Right Alt), VK_LMENU = 0xA4 (Left Alt)
        # VK_RCONTROL = 0xA3, VK_LCONTROL = 0xA2
        # VK_RSHIFT = 0xA1, VK_LSHIFT = 0xA0
        # VK_LWIN = 0x5B, VK_RWIN = 0x5C
        modifier_token: str | None = None
        if vk == 0xA5:
            modifier_token = "alt_r"
        elif vk == 0xA4:
            modifier_token = "alt_l"
        elif vk == 0xA3:
            modifier_token = "ctrl_r"
        elif vk == 0xA2:
            modifier_token = "ctrl_l"
        elif vk == 0xA1:
            modifier_token = "shift_r"
        elif vk == 0xA0:
            modifier_token = "shift_l"
        elif key == Qt.Key.Key_Control:
            modifier_token = "ctrl"
        elif key == Qt.Key.Key_Alt:
            modifier_token = "alt"
        elif key == Qt.Key.Key_Shift:
            modifier_token = "shift"
        elif key == Qt.Key.Key_Meta:
            modifier_token = "cmd"

        if modifier_token is not None:
            # Standalone modifier pressed -- save as pending in case it's a tap
            self._pending_modifier = modifier_token
            # Display live feedback
            self._prompt_label.setText(f"[ DETECTED: {_format_token_badge(modifier_token)} + ... ]")
            return

        # A non-modifier key was pressed along with any held modifiers
        mods = event.modifiers()
        parts: list[str] = []

        if mods & Qt.KeyboardModifier.ControlModifier:
            parts.append("ctrl")
        if mods & Qt.KeyboardModifier.AltModifier:
            parts.append("alt")
        if mods & Qt.KeyboardModifier.ShiftModifier:
            parts.append("shift")
        if mods & Qt.KeyboardModifier.MetaModifier:
            parts.append("cmd")

        # Resolve primary key name
        key_name = self._resolve_key_name(event)
        if key_name and key_name not in parts:
            parts.append(key_name)

        if parts:
            combo_str = "+".join(parts)
            self.stop_recording()
            self.setText(combo_str)

    def keyReleaseEvent(self, event: QKeyEvent) -> None:
        if not self._is_recording:
            super().keyReleaseEvent(event)
            return

        # If a standalone modifier was pressed and now released without other keys, accept it
        if self._pending_modifier:
            mod = self._pending_modifier
            self._pending_modifier = None
            self.stop_recording()
            self.setText(mod)
            return

        super().keyReleaseEvent(event)

    def _resolve_key_name(self, event: QKeyEvent) -> str:
        key = event.key()

        if Qt.Key.Key_A <= key <= Qt.Key.Key_Z:
            return chr(key).lower()
        if Qt.Key.Key_0 <= key <= Qt.Key.Key_9:
            return chr(key)
        if Qt.Key.Key_F1 <= key <= Qt.Key.Key_F24:
            return f"f{key - Qt.Key.Key_F1 + 1}"

        special_map = {
            Qt.Key.Key_Space: "space",
            Qt.Key.Key_Return: "enter",
            Qt.Key.Key_Enter: "enter",
            Qt.Key.Key_Tab: "tab",
            Qt.Key.Key_Backspace: "backspace",
            Qt.Key.Key_Delete: "delete",
            Qt.Key.Key_Insert: "insert",
            Qt.Key.Key_Home: "home",
            Qt.Key.Key_End: "end",
            Qt.Key.Key_PageUp: "pageup",
            Qt.Key.Key_PageDown: "pagedown",
            Qt.Key.Key_Up: "up",
            Qt.Key.Key_Down: "down",
            Qt.Key.Key_Left: "left",
            Qt.Key.Key_Right: "right",
            Qt.Key.Key_Print: "printscreen",
            Qt.Key.Key_Pause: "pause",
            Qt.Key.Key_CapsLock: "capslock",
        }
        if key in special_map:
            return special_map[key]

        text = event.text().strip().lower()
        if text and len(text) == 1 and text.isascii() and text.isalnum():
            return text

        return ""
