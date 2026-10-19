#!/usr/bin/env python3
"""WebPlus - website designer. Run: python3 sitewright.py [file.site]"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from PyQt5.QtGui import QIcon  # noqa: E402
from PyQt5.QtWidgets import QApplication  # noqa: E402

from sitewright import __version__  # noqa: E402

from sitewright.window import APP, MainWindow, apply_ui_font, saved_ui_pt  # noqa: E402


def main():
    if "--version" in sys.argv[1:]:
        print("WebPlus " + __version__)
        return
    if "--help" in sys.argv[1:] or "-h" in sys.argv[1:]:
        print("Usage: webplus [file.site]\n\nOpens the website designer. "
              "Give a .site file (or an older .sitewright file) to open it straight away.")
        return
    app = QApplication(sys.argv)
    app.setApplicationName(APP)
    app.setApplicationVersion(__version__)
    # names that pop up over the picture buttons must always be readable
    app.setStyleSheet("QToolTip{color:#101820;background-color:#ffffe0;"
                      "border:1px solid #6b7480;padding:3px 6px;font-size:13px}")
    app.setDesktopFileName(os.environ.get("FLATPAK_ID", "sitewright"))
    icon = os.path.join(os.path.dirname(os.path.abspath(__file__)), "icons", "sitewright-256.png")
    if os.path.exists(icon):
        app.setWindowIcon(QIcon(icon))
    apply_ui_font(saved_ui_pt())
    path = sys.argv[1] if len(sys.argv) > 1 and os.path.isfile(sys.argv[1]) else None
    w = MainWindow(path)
    w.showMaximized()           # always fills the screen when it opens
    if path is None:
        from PyQt5.QtCore import QSettings, QTimer
        show = QSettings("4ThePeopleMedia", "Sitewright").value("show_start", True)
        if str(show).lower() in ("true", "1"):
            QTimer.singleShot(150, w.startup_assistant)
    sys.exit(app.exec_())


if __name__ == "__main__":
    main()
