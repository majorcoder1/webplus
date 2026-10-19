#!/bin/bash
# Removes the menu entry, icons, command and file type that install.sh added.
# Your sites and your saved compositions are left alone.
share="${XDG_DATA_HOME:-$HOME/.local/share}"
rm -f "$HOME/.local/bin/sitewright" "$HOME/.local/bin/webplus" "$share/applications/sitewright.desktop" \
      "$share/mime/packages/application-x-sitewright.xml"
find "$share/icons/hicolor" -name 'sitewright.png' -delete 2>/dev/null
rm -f "$share/icons/hicolor/scalable/apps/sitewright.svg"
command -v update-mime-database >/dev/null && update-mime-database "$share/mime" >/dev/null 2>&1
command -v update-desktop-database >/dev/null && update-desktop-database "$share/applications" >/dev/null 2>&1
command -v gtk-update-icon-cache >/dev/null && gtk-update-icon-cache -q -f -t "$share/icons/hicolor" >/dev/null 2>&1
echo "WebPlus was removed from your menu. Your sites were not touched."
