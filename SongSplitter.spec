# -*- mode: python ; coding: utf-8 -*-
from PyInstaller.utils.hooks import collect_all

datas = []
binaries = []
hiddenimports = []

# These packages ship dynamic libs / data files that PyInstaller's default
# analysis does not always pick up. Collect them fully.
for pkg in ("librosa", "soundfile", "imageio_ffmpeg"):
    d, b, h = collect_all(pkg)
    datas += d
    binaries += b
    hiddenimports += h

hiddenimports += ["lib", "lib.dataset", "lib.layers", "lib.nets", "lib.spec_utils"]

# Web assets + the pre-trained model so the friend needs no download.
datas += [
    ("templates", "templates"),
    ("static", "static"),
    ("models", "models"),
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
    excludes=[],
    noarchive=False,
)

pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="SongSplitter",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=False,
    disable_windowed_traceback=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=False,
    upx_exclude=[],
    name="SongSplitter",
)

app = BUNDLE(
    coll,
    name="SongSplitter.app",
    icon="assets/AppIcon.icns",
    bundle_identifier="com.songsplitter.app",
)