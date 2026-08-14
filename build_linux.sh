#!/bin/bash
set -e
cd "$(dirname "$0")"

echo "==> Building slim Spdio for Linux ..."
python3 -m PyInstaller --noconfirm SongSplitter.spec

if find dist/Spdio -iname '*torch*' | grep -q .; then
  echo "ERROR: torch leaked into the slim bundle" >&2
  exit 1
fi

OUT=Spdio-linux-x64.tar.gz
rm -f "$OUT"
tar -C dist -czf "$OUT" Spdio

if command -v appimagetool >/dev/null 2>&1; then
  echo "==> Building AppImage ..."
  APPDIR=dist/Spdio.AppDir
  rm -rf "$APPDIR"
  mkdir -p "$APPDIR/usr/bin"
  cp -a dist/Spdio/. "$APPDIR/usr/bin/"
  cp assets/AppIcon.png "$APPDIR/spdio.png"
  cat > "$APPDIR/Spdio.desktop" <<EOF
[Desktop Entry]
Type=Application
Name=Spdio
Exec=Spdio
Icon=spdio
Categories=AudioVideo;Audio;
EOF
  printf '%s\n' '#!/bin/sh' 'exec "$(dirname "$0")/usr/bin/Spdio" "$@"' > "$APPDIR/AppRun"
  chmod +x "$APPDIR/AppRun"
  appimagetool "$APPDIR" dist/Spdio.AppImage
fi

echo "==> Done:"
ls -lh "$OUT" dist/Spdio.AppImage 2>/dev/null || ls -lh "$OUT"
