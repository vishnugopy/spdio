#!/bin/bash
set -euo pipefail
cd "$(dirname "$0")"

echo "==> Building slim Spdio.app ..."
./venv/bin/pyinstaller --noconfirm SongSplitter.spec

if find dist/Spdio.app -iname '*torch*' | grep -q .; then
  echo "ERROR: torch leaked into the slim bundle" >&2
  find dist/Spdio.app -iname '*torch*' >&2
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
REQUIRE_NOTARIZATION="${REQUIRE_NOTARIZATION:-1}"

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
    dist/Spdio.app
  codesign --verify --deep --strict dist/Spdio.app && echo "    signature OK"
elif [ -n "$FALLBACK" ]; then
  if [ "$REQUIRE_NOTARIZATION" = "1" ]; then
    echo "ERROR: only an Apple Development certificate was found." >&2
    echo "       Published Mac builds need a Developer ID Application certificate and notarization." >&2
    exit 1
  fi
  echo "==> Signing with local development certificate (not notarizable)."
  echo "    Create a 'Developer ID Application' certificate in your Apple Developer account to notarize."
  IDENTITY="$FALLBACK"
  codesign --force --deep --options runtime \
    --entitlements entitlements.plist \
    --sign "$IDENTITY" \
    dist/Spdio.app
  codesign --verify --deep --strict dist/Spdio.app && echo "    signature OK"
else
  if [ "$REQUIRE_NOTARIZATION" = "1" ]; then
    echo "ERROR: no Developer ID Application certificate found." >&2
    exit 1
  fi
  echo "==> No code-signing certificate found - skipping sign."
fi

if [ -n "${APPLE_ID:-}" ] && [ -n "${APP_PASSWORD:-}" ] && [ -n "${TEAM_ID:-}" ]; then
  if ! security find-identity -v -p codesigning | grep -q "Developer ID Application"; then
    if [ "$REQUIRE_NOTARIZATION" = "1" ]; then
      echo "ERROR: notarization credentials are present, but no Developer ID Application certificate is installed." >&2
      exit 1
    fi
    echo "==> Skipping notarize: no Developer ID Application certificate in the keychain."
    echo "    Apple Development certificates cannot be notarized."
    echo "    Create one: https://developer.apple.com/account/resources/certificates/add"
    echo "    Choose 'Developer ID Application', install the .cer, then re-run ./build.sh"
  else
  echo "==> Notarizing ..."
  rm -f /tmp/spdio-notarize.zip
  ditto -c -k --keepParent dist/Spdio.app /tmp/spdio-notarize.zip
  xcrun notarytool submit /tmp/spdio-notarize.zip \
    --apple-id "$APPLE_ID" \
    --password "$APP_PASSWORD" \
    --team-id "$TEAM_ID" \
    --wait
  xcrun stapler staple dist/Spdio.app
  xcrun stapler validate dist/Spdio.app
  spctl --assess --type execute --verbose=4 dist/Spdio.app
  fi
else
  if [ "$REQUIRE_NOTARIZATION" = "1" ]; then
    echo "ERROR: notarization credentials are missing (APPLE_ID, APP_PASSWORD, TEAM_ID)." >&2
    exit 1
  fi
  echo "==> Skipping notarize (set APPLE_ID, APP_PASSWORD, TEAM_ID to enable)."
fi

echo "==> Creating disk image ..."
./build_dmg.sh

echo "==> Done:"
ls -lh dist/Spdio.dmg
