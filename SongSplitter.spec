# -*- mode: python ; coding: utf-8 -*-
import sys
from pathlib import Path

from PyInstaller.utils.hooks import collect_all

sys.path.insert(0, str(Path(globals().get("SPECPATH", Path.cwd()))))
from engine_stdlib import ENGINE_STDLIB

datas = []
binaries = []
hiddenimports = []

d, b, h = collect_all("webview")
datas += d
binaries += b
hiddenimports += h

hiddenimports += [
    "app_paths",
    "audio_sniff",
    "engine_bootstrap",
    "desktop",
    "version",
    "lib",
    "lib.dataset",
    "lib.layers",
    "lib.nets",
    "lib.spec_utils",
]
hiddenimports += list(ENGINE_STDLIB)

datas += [
    ("templates", "templates"),
    ("static", "static"),
    ("engine_manifest.json", "."),
]

excludes = [
    "torch",
    "torchvision",
    "torchaudio",
    "numpy",
    "scipy",
    "librosa",
    "soundfile",
    "imageio_ffmpeg",
    "numba",
    "llvmlite",
    "sklearn",
    "matplotlib",
    "pandas",
]

a = Analysis(
    ["app.py"],
    pathex=[],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=excludes,
    noarchive=False,
)

pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="Spdio",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=False,
    disable_windowed_traceback=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon="assets/AppIcon.ico",
)

coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=False,
    upx_exclude=[],
    name="Spdio",
)

app = BUNDLE(
    coll,
    name="Spdio.app",
    icon="assets/AppIcon.icns",
    bundle_identifier="com.vishnugopy.spdio",
)
