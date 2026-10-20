#!/usr/bin/env python3
"""WebPlus - website designer. Run: python3 sitewright.py [file.site]"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from PyQt5.QtGui import QIcon  # noqa: E402
from PyQt5.QtWidgets import QApplication  # noqa: E402

from sitewright import __version__  # noqa: E402

from sitewright.window import APP, MainWindow, apply_ui_font, saved_ui_pt  # noqa: E402


def selftest():
    """Checks that a packaged copy can start, find its pictures and word lists, and write a site. Used by the build."""
    import tempfile
    os.environ["QT_QPA_PLATFORM"] = "offscreen"
    app = QApplication(sys.argv[:1])
    from sitewright import export, library, thesaurus
    from sitewright.model import new_item
    w = MainWindow()
    w.cur_page()["items"].append(new_item("text", 20, 20, text="Hello"))
    out = tempfile.mkdtemp()
    export.export_site(w.doc, out)
    assert os.path.exists(os.path.join(out, "index.html")), "export failed"
    root = os.path.join(os.path.dirname(os.path.abspath(library.__file__)), "library")
    assert os.path.isfile(os.path.join(root, "icons.json")), "picture library missing"
    assert os.path.isfile(os.path.join(root, "thesaurus.json.gz")), "thesaurus missing"
    try:
        import PIL  # noqa: F401
        pil = "yes"
    except ImportError:
        pil = "NO"
    print("SELFTEST OK  version %s  pillow %s" % (__version__, pil))
    return 0


def main():
    if "--version" in sys.argv[1:]:
        print("WebPlus " + __version__)
        return
    if "--help" in sys.argv[1:] or "-h" in sys.argv[1:]:
        print("Usage: webplus [file.site]\n\nOpens the website designer. "
              "Give a .site file (or an older .sitewright file) to open it straight away.")
        return
    if "--selftest" in sys.argv[1:]:
        raise SystemExit(selftest())
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
