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

if [ -f .env ]; then
  set -a
  # shellcheck disable=SC1091
  . ./.env
  set +a
fi
APP_PASSWORD="${APP_PASSWORD:-${APPLE_APP_SPECIFIC_PASSWORD:-}}"
TEAM_ID="${TEAM_ID:-${APPLE_TEAM_ID:-}}"

DEV_ID_LINE=$(security find-identity -v -p codesigning | grep "Developer ID Application" | head -1 || true)
if [ -n "$DEV_ID_LINE" ]; then
  IDENTITY=$(printf '%s\n' "$DEV_ID_LINE" | grep -oE '[A-F0-9]{40}' | head -1)
else
  IDENTITY=""
fi
if [ -z "$IDENTITY" ]; then
  FALLBACK=$(security find-identity -v -p codesigning | grep -oE '[A-F0-9]{40}' | head -1 || true)
else
  FALLBACK=""
fi

if [ -n "$IDENTITY" ]; then
  echo "==> Signing with Developer ID Application ..."
  codesign --force --deep --options runtime --timestamp \
    --entitlements entitlements.plist \
    --sign "$IDENTITY" \
    dist/SongSplitter.app
  codesign --verify --deep --strict dist/SongSplitter.app && echo "    signature OK"
elif [ -n "$FALLBACK" ]; then
  echo "==> Signing with local development certificate (not notarizable)."
  echo "    Create a 'Developer ID Application' certificate in your Apple Developer account to notarize."
  IDENTITY="$FALLBACK"
  codesign --force --deep --options runtime \
    --entitlements entitlements.plist \
    --sign "$IDENTITY" \
    dist/SongSplitter.app
  codesign --verify --deep --strict dist/SongSplitter.app && echo "    signature OK"
else
  echo "==> No code-signing certificate found - skipping sign."
fi

if [ -n "${APPLE_ID:-}" ] && [ -n "${APP_PASSWORD:-}" ] && [ -n "${TEAM_ID:-}" ]; then
  if ! security find-identity -v -p codesigning | grep -q "Developer ID Application"; then
    echo "==> Skipping notarize: no Developer ID Application certificate in the keychain."
    echo "    Apple Development certificates cannot be notarized."
    echo "    Create one: https://developer.apple.com/account/resources/certificates/add"
    echo "    Choose 'Developer ID Application', install the .cer, then re-run ./build.sh"
  else
  echo "==> Notarizing ..."
  rm -f /tmp/songsplitter-notarize.zip
  ditto -c -k --keepParent dist/SongSplitter.app /tmp/songsplitter-notarize.zip
  xcrun notarytool submit /tmp/songsplitter-notarize.zip \
    --apple-id "$APPLE_ID" \
    --password "$APP_PASSWORD" \
    --team-id "$TEAM_ID" \
    --wait
  xcrun stapler staple dist/SongSplitter.app
  fi
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
