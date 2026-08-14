#!/bin/bash
set -euo pipefail

cd "$(dirname "$0")"

APP="$(pwd)/dist/Spdio.app"
OUT="$(pwd)/dist/Spdio.dmg"
if [ ! -d "$APP" ]; then
  echo "Build dist/Spdio.app first." >&2
  exit 1
fi

WORK="$(mktemp -d /tmp/spdio-dmg.XXXXXX)"
RW="$WORK/Spdio-rw.dmg"
MOUNT=""
cleanup() {
  if [ -n "$MOUNT" ] && mount | grep -Fq "$MOUNT"; then
    hdiutil detach "$MOUNT" -quiet || true
  fi
  rm -rf "$WORK"
}
trap cleanup EXIT

mkdir -p "$WORK/stage"
ditto "$APP" "$WORK/stage/Spdio.app"
ln -s /Applications "$WORK/stage/Applications"

hdiutil create -volname "Spdio" -srcfolder "$WORK/stage" \
  -fs HFS+ -format UDRW -ov "$RW" >/dev/null
MOUNT="$(hdiutil attach "$RW" -nobrowse | awk '/Apple_HFS/ {print $3; exit}')"
if [ -z "$MOUNT" ]; then
  echo "Could not mount the temporary DMG." >&2
  exit 1
fi

osascript <<'APPLESCRIPT'
tell application "Finder"
  tell disk "Spdio"
    open
    set current view of container window to icon view
    set toolbar visible of container window to false
    set statusbar visible of container window to false
    set bounds of container window to {120, 120, 860, 600}
    set opts to the icon view options of container window
    set arrangement of opts to not arranged
    set icon size of opts to 128
    set text size of opts to 14
    set position of item "Spdio.app" to {210, 245}
    set position of item "Applications" to {570, 245}
    close
    open
    update without registering applications
    delay 1
    close
  end tell
end tell
APPLESCRIPT

hdiutil detach "$MOUNT" -quiet
MOUNT=""
hdiutil convert "$RW" -format UDZO -imagekey zlib-level=9 -ov -o "$OUT" >/dev/null
echo "Created $OUT"
