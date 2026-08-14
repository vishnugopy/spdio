#!/bin/bash
set -e
cd "$(dirname "$0")"

echo "==> Building slim SongSplitter for Linux ..."
python3 -m PyInstaller --noconfirm SongSplitter.spec

if find dist/SongSplitter -iname '*torch*' | grep -q .; then
  echo "ERROR: torch leaked into the slim bundle" >&2
  exit 1
fi

OUT=SongSplitter-linux-x64.tar.gz
rm -f "$OUT"
tar -C dist -czf "$OUT" SongSplitter

if command -v appimagetool >/dev/null 2>&1; then
  echo "==> Building AppImage ..."
  APPDIR=dist/SongSplitter.AppDir
  rm -rf "$APPDIR"
  mkdir -p "$APPDIR/usr/bin"
  cp -a dist/SongSplitter/. "$APPDIR/usr/bin/"
  cp assets/AppIcon.png "$APPDIR/songsplitter.png"
  cat > "$APPDIR/SongSplitter.desktop" <<EOF
[Desktop Entry]
Type=Application
Name=Song Splitter
Exec=SongSplitter
Icon=songsplitter
Categories=AudioVideo;Audio;
EOF
  printf '%s\n' '#!/bin/sh' 'exec "$(dirname "$0")/usr/bin/SongSplitter" "$@"' > "$APPDIR/AppRun"
  chmod +x "$APPDIR/AppRun"
  appimagetool "$APPDIR" dist/SongSplitter.AppImage
fi

echo "==> Done:"
ls -lh "$OUT" dist/SongSplitter.AppImage 2>/dev/null || ls -lh "$OUT"
