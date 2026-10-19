#!/bin/bash
# Builds FlowState for macOS end to end:
#   1. the Parakeet speech helper (Swift, FluidAudio/CoreML)
#   2. FlowState.app (PyInstaller)
#   3. helper copied into FlowState.app/Contents/Helpers, bundle signed
#   4. dist_macos/FlowState-macOS.zip (release asset the in-app updater
#      installs) and dist_macos/FlowState-<version>.dmg (for people)
#
# Requirements: Apple silicon, macOS 14+, Xcode Command Line Tools (Swift 6),
# and the project's .venv with requirements-macos.txt installed.
#
# Signing: set FLOWSTATE_SIGN_IDENTITY to a "Developer ID Application: ..."
# identity to sign for distribution (then notarize the dmg with
# `xcrun notarytool`). Without it the app is signed ad hoc, which runs on
# this Mac; other Macs need right-click > Open the first time.

set -euo pipefail

PACKAGING_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_ROOT="$(dirname "$PACKAGING_DIR")"
PYTHON="$PROJECT_ROOT/.venv/bin/python"
HELPER_DIR="$PROJECT_ROOT/native/macos/FlowStateParakeet"
DIST="$PACKAGING_DIR/dist"
OUT="$PACKAGING_DIR/dist_macos"
APP="$DIST/FlowState.app"
IDENTITY="${FLOWSTATE_SIGN_IDENTITY:--}"

if [ "$(uname -m)" != "arm64" ]; then
  echo "FlowState for macOS is built on Apple silicon." >&2
  exit 1
fi

VERSION="$("$PYTHON" -c "import sys; sys.path.insert(0, '$PROJECT_ROOT/src'); import flowstate; print(flowstate.__version__)")"
echo "== FlowState $VERSION for macOS =="

echo "== 1/4: Parakeet speech helper =="
swift build -c release --package-path "$HELPER_DIR"
HELPER_BUILD="$(swift build -c release --package-path "$HELPER_DIR" --show-bin-path)"

echo "== 2/4: FlowState.app =="
"$PYTHON" -m PyInstaller "$PACKAGING_DIR/flowstate_macos.spec" \
  --distpath "$DIST" --workpath "$PACKAGING_DIR/build_macos" --clean --noconfirm

echo "== 3/4: bundle helper and sign =="
mkdir -p "$APP/Contents/Helpers"
# Only the executable: FluidAudio's resource bundle holds text-to-speech
# data that speech recognition never reads (and isn't a signable bundle).
cp "$HELPER_BUILD/FlowStateParakeet" "$APP/Contents/Helpers/"
codesign --force --options runtime --timestamp=none --sign "$IDENTITY" "$APP/Contents/Helpers/FlowStateParakeet"
codesign --force --deep --options runtime --timestamp=none \
  --entitlements "$PACKAGING_DIR/macos_entitlements.plist" --sign "$IDENTITY" "$APP"
codesign --verify --deep --strict "$APP"

echo "== 4/4: zip and dmg =="
rm -rf "$OUT" && mkdir -p "$OUT"
ditto -c -k --keepParent "$APP" "$OUT/FlowState-macOS.zip"
STAGE="$(mktemp -d)"
cp -R "$APP" "$STAGE/"
ln -s /Applications "$STAGE/Applications"
hdiutil create -volname "FlowState" -srcfolder "$STAGE" -ov -format UDZO "$OUT/FlowState-$VERSION.dmg" >/dev/null
rm -rf "$STAGE"

echo ""
echo "Done:"
echo "  $APP"
echo "  $OUT/FlowState-macOS.zip   (attach to the GitHub release for in-app updates)"
echo "  $OUT/FlowState-$VERSION.dmg"
