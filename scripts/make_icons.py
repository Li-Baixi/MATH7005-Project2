"""Render the PWA launcher icons (PNG 192/512) from the AccessHK design.

Mirrors app/static/icon.svg: cream rounded square, rose ring, wheelchair
glyph.  Some Android Chrome builds only show the install prompt for PNG
icons, so the manifest lists these alongside the SVG.

Usage (from the project root):

    python scripts/make_icons.py
"""
import os

from PIL import Image, ImageDraw, ImageFont

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(BASE, "app", "static")

CREAM = (244, 241, 234, 255)
ROSE = (185, 138, 135, 255)
INK = (74, 69, 61, 255)

FONT_CANDIDATES = [
    r"C:\Windows\Fonts\seguisym.ttf",   # Segoe UI Symbol
    r"C:\Windows\Fonts\segoeui.ttf",
    "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
]


def _font(size: int):
    for path in FONT_CANDIDATES:
        if os.path.exists(path):
            try:
                return ImageFont.truetype(path, size)
            except OSError:
                continue
    return ImageFont.load_default()


def render(px: int) -> Image.Image:
    img = Image.new("RGBA", (px, px), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    radius = int(px * 42 / 192)
    d.rounded_rectangle([0, 0, px - 1, px - 1], radius=radius, fill=CREAM)
    ring_w = max(4, int(px * 10 / 192))
    d.ellipse([px * 0.175, px * 0.175, px * 0.825, px * 0.825],
              outline=ROSE, width=ring_w)

    font = _font(int(px * 78 / 192))
    text = "\u267F"                      # wheelchair symbol
    bbox = d.textbbox((0, 0), text, font=font)
    w, h = bbox[2] - bbox[0], bbox[3] - bbox[1]
    d.text(((px - w) / 2 - bbox[0], (px - h) / 2 - bbox[1]), text,
           font=font, fill=INK)
    return img


if __name__ == "__main__":
    for size in (192, 512):
        out = os.path.join(OUT, f"icon-{size}.png")
        render(size).save(out)
        print("wrote", out)
