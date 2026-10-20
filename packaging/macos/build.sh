#!/bin/bash
# Builds WebPlus.app and a .dmg on a Mac:   bash packaging/macos/build.sh
# Needs Python 3.10+ from python.org or Homebrew. Output: dist/WebPlus.app and dist/WebPlus-macOS-<chip>.dmg
set -e
cd "$(dirname "$0")/../.."
python3 -m venv .venv-mac
. .venv-mac/bin/activate
python -m pip install --upgrade pip
python -m pip install PyQt5 pillow pyinstaller
python packaging/macos/make_icns.py packaging/macos/WebPlus.icns
rm -rf build dist
pyinstaller --noconfirm --windowed --name WebPlus \
    --icon packaging/macos/WebPlus.icns \
    --osx-bundle-identifier live.fourthepeople.WebPlus \
    --add-data "sitewright/library:sitewright/library" \
    --add-data "icons:icons" \
    --collect-submodules sitewright \
    sitewright.py
# Apple Silicon programs must carry at least an ad-hoc signature to start
codesign --force --deep --sign - dist/WebPlus.app
chip="$(uname -m)"
hdiutil create -volname WebPlus -srcfolder dist/WebPlus.app -ov -format UDZO "dist/WebPlus-macOS-$chip.dmg"
echo "Done: dist/WebPlus-macOS-$chip.dmg"
