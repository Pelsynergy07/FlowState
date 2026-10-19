"""Burns a highlight marker into a captured screenshot, matching the
reference app's "highlight baked into the PNG" behaviour."""

from __future__ import annotations

from PIL import Image, ImageDraw

HIGHLIGHT_COLOR = (87, 81, 224)  # FlowState's accent indigo
RING_WIDTH = 6
DEFAULT_RING_RADIUS = 90


def draw_circle_highlight(
    image: Image.Image,
    center_x: float,
    center_y: float,
    monitor_left: int = 0,
    monitor_top: int = 0,
    radius: float = DEFAULT_RING_RADIUS,
    scale: float = 1.0,
) -> Image.Image:
    """center_x/center_y are virtual-screen coordinates; monitor_left/top
    convert them into the captured image's local coordinate space and
    scale into its pixels (2 on a Retina display)."""
    annotated = image.copy()
    draw = ImageDraw.Draw(annotated)
    x = (center_x - monitor_left) * scale
    y = (center_y - monitor_top) * scale
    r = radius * scale
    bbox = [x - r, y - r, x + r, y + r]
    draw.ellipse(bbox, outline=HIGHLIGHT_COLOR, width=round(RING_WIDTH * scale))
    return annotated


def draw_rect_highlight(
    image: Image.Image,
    left: int,
    top: int,
    right: int,
    bottom: int,
    monitor_left: int = 0,
    monitor_top: int = 0,
    scale: float = 1.0,
) -> Image.Image:
    annotated = image.copy()
    draw = ImageDraw.Draw(annotated)
    bbox = [(left - monitor_left) * scale, (top - monitor_top) * scale,
            (right - monitor_left) * scale, (bottom - monitor_top) * scale]
    draw.rectangle(bbox, outline=HIGHLIGHT_COLOR, width=round(RING_WIDTH * scale))
    return annotated
