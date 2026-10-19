#!/bin/bash
# Installs Sitewright for the current user: menu entry, icon, "sitewright" command and
# .site file association. Nothing outside your home folder is touched.
set -e
here="$(cd "$(dirname "$0")" && pwd)"
share="${XDG_DATA_HOME:-$HOME/.local/share}"

if ! python3 -c "import PyQt5.QtWidgets" 2>/dev/null; then
    echo "WebPlus needs PyQt5. On Linux Mint / Ubuntu / Debian install it with:"
    echo "    sudo apt install python3-pyqt5"
    exit 1
fi

if ! python3 -c "import PIL" 2>/dev/null; then
    echo "Note: picture effects, PhotoLab and phone-photo turning need Pillow. Install it with:"
    echo "    sudo apt install python3-pil"
    echo "(WebPlus still runs without it; those features just say so.)"
fi

# icons
for f in "$here"/icons/sitewright-*.png; do
    size="$(basename "$f" .png)"; size="${size#sitewright-}"
    mkdir -p "$share/icons/hicolor/${size}x${size}/apps"
    cp "$f" "$share/icons/hicolor/${size}x${size}/apps/sitewright.png"
done
mkdir -p "$share/icons/hicolor/scalable/apps"
cp "$here/icons/sitewright.svg" "$share/icons/hicolor/scalable/apps/sitewright.svg"

# command
mkdir -p "$HOME/.local/bin"
cat > "$HOME/.local/bin/sitewright" <<LAUNCH
#!/bin/bash
exec python3 "$here/sitewright.py" "\$@"
LAUNCH
chmod +x "$HOME/.local/bin/sitewright"
cp "$HOME/.local/bin/sitewright" "$HOME/.local/bin/webplus"

# menu entry
mkdir -p "$share/applications"
cat > "$share/applications/sitewright.desktop" <<DESK
[Desktop Entry]
Type=Application
Version=1.0
Name=WebPlus
GenericName=Website Designer
Comment=Design and publish websites by dragging things onto a page
Exec=$HOME/.local/bin/sitewright %f
Icon=sitewright
Terminal=false
Categories=Development;WebDevelopment;
MimeType=application/x-sitewright;
Keywords=website;web;design;html;site;page;
StartupWMClass=sitewright.py
DESK

# file type
mkdir -p "$share/mime/packages"
cat > "$share/mime/packages/application-x-sitewright.xml" <<MIME
<?xml version="1.0" encoding="UTF-8"?>
<mime-info xmlns="http://www.freedesktop.org/standards/shared-mime-info">
  <mime-type type="application/x-sitewright">
    <comment>Web page</comment>
    <glob pattern="*.site"/>
    <glob pattern="*.sitewright"/>
    <icon name="sitewright"/>
  </mime-type>
</mime-info>
MIME

command -v update-mime-database >/dev/null && update-mime-database "$share/mime" >/dev/null 2>&1 || true
command -v update-desktop-database >/dev/null && update-desktop-database "$share/applications" >/dev/null 2>&1 || true
command -v gtk-update-icon-cache >/dev/null && gtk-update-icon-cache -q -f -t "$share/icons/hicolor" >/dev/null 2>&1 || true
xdg-mime default sitewright.desktop application/x-sitewright 2>/dev/null || true

echo "WebPlus is installed."
echo "  Menu:    Development > WebPlus (or search for it)"
echo "  Command: webplus   (make sure ~/.local/bin is on your PATH)"
echo "  Files:   double-click any .site file to open it (older .sitewright files open too)"
