"""Generate all app icons: favicons, PWA icons, and the macOS .icns.

Run with the project venv:  ./venv/bin/python make_icons.py
"""
import os
import shutil
import subprocess
from pathlib import Path

from PIL import Image, ImageDraw

BASE = Path(__file__).resolve().parent
ICON_DIR = BASE / "static" / "icons"
ASSETS = BASE / "assets"

TOP = (124, 108, 240)
BOTTOM = (20, 17, 43)
WHITE = (255, 255, 255)

MASTER = 1024


def gradient(size):
    img = Image.new("RGBA", (size, size))
    d = ImageDraw.Draw(img)
    for y in range(size):
        t = y / (size - 1)
        d.line(
            [(0, y), (size, y)],
            fill=(
                int(TOP[0] + (BOTTOM[0] - TOP[0]) * t),
                int(TOP[1] + (BOTTOM[1] - TOP[1]) * t),
                int(TOP[2] + (BOTTOM[2] - TOP[2]) * t),
                255,
            ),
        )
    return img


def render(size, scale=1.0, cx=0.5, cy=0.5, rounded=True):
    s = scale * size / MASTER

    def P(x, y):
        return (cx * size + (x - MASTER / 2) * s, cy * size + (y - MASTER / 2) * s)

    img = gradient(size)
    if rounded:
        m = Image.new("L", (size, size), 0)
        ImageDraw.Draw(m).rounded_rectangle([0, 0, size - 1, size - 1], radius=size * 0.225, fill=255)
        img.putalpha(m)

    d = ImageDraw.Draw(img)

    def rrect(x0, y0, x1, y1, rad=None):
        if rad is None:
            rad = min(x1 - x0, y1 - y0) / 2
        d.rounded_rectangle([*P(x0, y0), *P(x1, y1)], radius=max(0.5, rad * s), fill=WHITE)

    # note head
    rrect(300, 530, 500, 690)
    # note stem
    rrect(472, 240, 512, 690)
    # note flag
    d.pieslice([*P(505, 190), *P(720, 380)], start=0, end=100, fill=WHITE)

    return img


def save(img, path):
    path.parent.mkdir(parents=True, exist_ok=True)
    img.save(str(path))
    print("wrote", path)


def make_icns():
    iconset = ASSETS / "AppIcon.iconset"
    if iconset.exists():
        shutil.rmtree(iconset)
    iconset.mkdir(parents=True)
    entries = {
        "icon_16x16.png": 16,
        "icon_16x16@2x.png": 32,
        "icon_32x32.png": 32,
        "icon_32x32@2x.png": 64,
        "icon_128x128.png": 128,
        "icon_128x128@2x.png": 256,
        "icon_256x256.png": 256,
        "icon_256x256@2x.png": 512,
        "icon_512x512.png": 512,
        "icon_512x512@2x.png": 1024,
    }
    for name, size in entries.items():
        render(size).save(str(iconset / name))
    icns = ASSETS / "AppIcon.icns"
    subprocess.run(
        ["iconutil", "-c", "icns", str(iconset), "-o", str(icns)], check=True
    )
    shutil.rmtree(iconset)
    print("wrote", icns, icns.stat().st_size, "bytes")


def main():
    ICON_DIR.mkdir(parents=True, exist_ok=True)
    save(render(16), ICON_DIR / "favicon-16.png")
    save(render(32), ICON_DIR / "favicon-32.png")
    save(render(180), ICON_DIR / "apple-touch-icon.png")
    save(render(192), ICON_DIR / "icon-192.png")
    save(render(512), ICON_DIR / "icon-512.png")
    save(render(512, scale=0.62, rounded=False), ICON_DIR / "icon-512-maskable.png")
    master = render(256)
    save(master, ASSETS / "AppIcon.png")
    ico = ASSETS / "AppIcon.ico"
    master.save(
        str(ico),
        sizes=[(16, 16), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)],
    )
    print("wrote", ico)
    if os.name == "posix" and shutil.which("iconutil"):
        make_icns()


if __name__ == "__main__":
    main()