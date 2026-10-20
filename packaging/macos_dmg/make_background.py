"""Draws the FlowState disk-image window background: drag-to-install at the
top, and the first-launch steps for an app macOS can't verify yet below.

Writes background.png (1x) and background@2x.png next to this file;
build_macos.sh combines them into a Retina-ready background.tiff.

The layout is coordinated with dmg_settings.py: the window is 660x460
points, the app icon sits at (170, 150) and Applications at (490, 150).
"""

from __future__ import annotations

import sys
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

HERE = Path(__file__).resolve().parent
FONTS = HERE.parents[1] / "src" / "flowstate" / "resources" / "fonts"

W, H = 660, 460
APP_X, APPS_X, ICON_Y, ICON = 170, 490, 150, 112

PAPER = (246, 242, 236)
CARD = (255, 255, 255)
INK = (26, 26, 26)
MUTED = (92, 87, 81)
LINE = (216, 210, 198)
LIME = (214, 255, 56)
# Finder writes icon names in black (Light Mode) or white (Dark Mode); a
# mid grey keeps either readable.
LABEL_PILL = (112, 112, 112)


def font(name: str, size: float, scale: int) -> ImageFont.FreeTypeFont:
    return ImageFont.truetype(str(FONTS / name), round(size * scale))


def draw(scale: int) -> Image.Image:
    s = scale
    img = Image.new("RGB", (W * s, H * s), PAPER)
    d = ImageDraw.Draw(img)

    title = font("InstrumentSerif-Regular.ttf", 30, s)
    d.text((W * s / 2, 34 * s), "Drag FlowState into Applications", font=title, fill=INK, anchor="mt")

    # Arrow from the app to Applications.
    y = ICON_Y * s
    x0, x1 = (APP_X + ICON / 2 + 24) * s, (APPS_X - ICON / 2 - 24) * s
    d.line([(x0, y), (x1 - 14 * s, y)], fill=INK, width=3 * s)
    d.polygon([(x1, y), (x1 - 18 * s, y - 10 * s), (x1 - 18 * s, y + 10 * s)], fill=INK)

    # Pills under the two icon names.
    for cx in (APP_X, APPS_X):
        top = (ICON_Y + ICON / 2 + 4) * s
        d.rounded_rectangle([(cx - 62) * s, top, (cx + 62) * s, top + 22 * s], radius=11 * s, fill=LABEL_PILL)

    # First-launch steps.
    card = [24 * s, 266 * s, (W - 24) * s, (H - 22) * s]
    d.rounded_rectangle(card, radius=8 * s, fill=CARD, outline=LINE, width=max(1, s))
    eyebrow = font("SpaceMono-Bold.ttf", 11, s)
    d.text((44 * s, 284 * s), "THE FIRST TIME YOU OPEN IT", font=eyebrow, fill=MUTED)

    body = font("Manrope-Regular.ttf", 14, s)
    bold = font("Manrope-Bold.ttf", 14, s)
    number = font("SpaceMono-Bold.ttf", 13, s)
    steps = [
        [("Open FlowState from ", body), ("Applications", bold), (". macOS can't verify it yet: click ", body),
         ("Done", bold), (".", body)],
        [("Open ", body), ("System Settings → Privacy & Security", bold), (", scroll down, click ", body),
         ("Open Anyway", bold), (".", body)],
        [("Click ", body), ("Open Anyway", bold), (" again and confirm. macOS won't ask again.", body)],
    ]
    for i, parts in enumerate(steps):
        top = (312 + i * 38) * s
        d.rounded_rectangle([44 * s, top, 70 * s, top + 26 * s], radius=4 * s, fill=LIME, outline=INK, width=max(1, s))
        d.text((57 * s, top + 13 * s), str(i + 1), font=number, fill=INK, anchor="mm")
        x = 84 * s
        for text, f in parts:
            d.text((x, top + 13 * s), text, font=f, fill=INK if f is bold else MUTED, anchor="lm")
            x += d.textlength(text, font=f)
    return img


def main() -> None:
    out = Path(sys.argv[1]) if len(sys.argv) > 1 else HERE
    out.mkdir(parents=True, exist_ok=True)
    draw(1).save(out / "background.png")
    draw(2).save(out / "background@2x.png")


if __name__ == "__main__":
    main()
