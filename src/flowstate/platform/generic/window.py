"""Qt's own window flags are all this platform gets."""

from __future__ import annotations


def make_overlay(widget, *, click_through: bool = False, exclude_from_capture: bool = False) -> None:
    pass


def bring_to_front(widget) -> None:
    widget.raise_()
    widget.activateWindow()


def global_to_logical(x: float, y: float) -> tuple[int, int]:
    return (round(x), round(y))
