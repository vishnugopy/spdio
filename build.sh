#!/bin/bash
set -e
cd "$(dirname "$0")"

echo "==> Building Song Splitter.app ..."
./venv/bin/pyinstaller --noconfirm SongSplitter.spec

IDENTITY=$(security find-identity -v -p codesigning | grep -oE '[A-F0-9]{40}' | head -1)
if [ -n "$IDENTITY" ]; then
  echo "==> Signing with certificate ..."
  codesign --force --deep --sign "$IDENTITY" dist/SongSplitter.app
  codesign --verify --deep --strict dist/SongSplitter.app && echo "    signature OK"
else
  echo "==> No code-signing certificate found - skipping sign."
fi

echo "==> Creating SongSplitter-mac.zip ..."
rm -f SongSplitter-mac.zip
ditto -c -k --keepParent --sequesterRsrc dist/SongSplitter.app SongSplitter-mac.zip

echo "==> Done:"
ls -lh SongSplitter-mac.zip