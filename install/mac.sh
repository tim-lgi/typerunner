#!/bin/bash
# Typerunner installer for macOS.
#
# Downloads the latest release, installs it to /Applications and clears the
# quarantine flag so macOS will open it. The app is not signed with an Apple
# Developer certificate, and since macOS Sequoia there is no right-click-Open
# bypass left, so without that last step the only way in is a trip through
# System Settings. Nothing else is installed and nothing is left behind.
set -euo pipefail

REPO="tim-lgi/typerunner"
APP="/Applications/Typerunner.app"

if [ "$(uname -s)" != "Darwin" ]; then
  echo "This installer is for macOS."; exit 1
fi
if [ "$(uname -m)" != "arm64" ]; then
  echo "Typerunner needs an Apple Silicon Mac (M1 or newer)."; exit 1
fi

echo "Finding the latest Typerunner..."
URL=$(curl -fsSL "https://api.github.com/repos/$REPO/releases" \
  | grep -o 'https://[^"]*Typerunner_[^"]*_arm64\.dmg' | head -1)
[ -n "$URL" ] || { echo "Could not find a download. Check your connection."; exit 1; }

TMP=$(mktemp -d)
trap 'hdiutil detach "$TMP/mnt" -quiet 2>/dev/null || true; rm -rf "$TMP"' EXIT

echo "Downloading..."
curl -fsSL -o "$TMP/typerunner.dmg" "$URL"

echo "Installing..."
mkdir -p "$TMP/mnt"
hdiutil attach "$TMP/typerunner.dmg" -mountpoint "$TMP/mnt" -nobrowse -quiet

if pgrep -f "Typerunner.app/Contents/MacOS/typerunner" >/dev/null 2>&1; then
  osascript -e 'quit app "Typerunner"' >/dev/null 2>&1 || true
  sleep 1
fi

rm -rf "$APP"
cp -R "$TMP/mnt/Typerunner.app" "$APP"
xattr -dr com.apple.quarantine "$APP" 2>/dev/null || true

echo
echo "Done. Typerunner is in your Applications folder."
open "$APP"
