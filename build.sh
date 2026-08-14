#!/bin/bash
set -e
cd "$(dirname "$0")"

echo "==> Building slim Song Splitter.app ..."
./venv/bin/pyinstaller --noconfirm SongSplitter.spec

if find dist/SongSplitter.app -iname '*torch*' | grep -q .; then
  echo "ERROR: torch leaked into the slim bundle" >&2
  find dist/SongSplitter.app -iname '*torch*' >&2
  exit 1
fi

IDENTITY=$(security find-identity -v -p codesigning | grep -oE '[A-F0-9]{40}' | head -1)
if [ -n "$IDENTITY" ]; then
  echo "==> Signing with Developer ID ..."
  codesign --force --deep --options runtime \
    --entitlements entitlements.plist \
    --sign "$IDENTITY" \
    dist/SongSplitter.app
  codesign --verify --deep --strict dist/SongSplitter.app && echo "    signature OK"
else
  echo "==> No code-signing certificate found - skipping sign."
fi

if [ -n "${APPLE_ID:-}" ] && [ -n "${APP_PASSWORD:-}" ] && [ -n "${TEAM_ID:-}" ]; then
  echo "==> Notarizing ..."
  rm -f /tmp/songsplitter-notarize.zip
  ditto -c -k --keepParent dist/SongSplitter.app /tmp/songsplitter-notarize.zip
  xcrun notarytool submit /tmp/songsplitter-notarize.zip \
    --apple-id "$APPLE_ID" \
    --password "$APP_PASSWORD" \
    --team-id "$TEAM_ID" \
    --wait
  xcrun stapler staple dist/SongSplitter.app
else
  echo "==> Skipping notarize (set APPLE_ID, APP_PASSWORD, TEAM_ID to enable)."
fi

echo "==> Creating disk image ..."
rm -f dist/SongSplitter.dmg SongSplitter-mac.zip
hdiutil create -volname "Song Splitter" -srcfolder dist/SongSplitter.app \
  -ov -format UDZO dist/SongSplitter.dmg
ditto -c -k --keepParent --sequesterRsrc dist/SongSplitter.app SongSplitter-mac.zip

if [ -n "$IDENTITY" ]; then
  codesign --force --sign "$IDENTITY" dist/SongSplitter.dmg || true
fi

echo "==> Done:"
ls -lh dist/SongSplitter.dmg SongSplitter-mac.zip
