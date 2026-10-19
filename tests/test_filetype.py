"""The program is called WebPlus; pages are saved as .site and older .sitewright files still open;
the Startup Assistant wears red, white and blue. Must print ALL GOOD."""
import os
import sys
import tempfile

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from PyQt5.QtCore import QRectF
from PyQt5.QtWidgets import QApplication, QFileDialog

from sitewright import startup, window
from sitewright.window import APP, FILTER, MainWindow

app = QApplication([])
assert APP == "WebPlus" and startup.PROGRAM == "WebPlus"
assert "*.site" in FILTER and "*.sitewright" in FILTER and "Web page" in FILTER

w = MainWindow()
w.show()
assert APP in w.windowTitle()
w.create_item("rect", QRectF(10, 10, 100, 60))
tmp = tempfile.mkdtemp()

# Save As with no extension typed -> .site
asked = {}
def fake_save(parent, title, name, flt):
    asked["name"], asked["filter"] = name, flt
    return os.path.join(tmp, "mypage"), flt
QFileDialog.getSaveFileName = staticmethod(fake_save)
assert w.save_as()
assert os.path.isfile(os.path.join(tmp, "mypage.site")), os.listdir(tmp)
assert asked["name"].endswith(".site")

# a name typed with .site is kept as is
QFileDialog.getSaveFileName = staticmethod(lambda *a: (os.path.join(tmp, "other.site"), ""))
assert w.save_as()
assert os.path.isfile(os.path.join(tmp, "other.site")) and not os.path.exists(os.path.join(tmp, "other.site.site"))

# an old .sitewright file still opens and can be saved on
old = os.path.join(tmp, "old.sitewright")
w.doc.save(old)
w.open_path(old)
assert len(w.doc.pages[0]["items"]) == 1
w.open_path(os.path.join(tmp, "mypage.site"))
assert len(w.doc.pages[0]["items"]) == 1

# patriotic colours on the Startup Assistant
src = open(os.path.join(os.path.dirname(__file__), "..", "sitewright", "startup.py")).read()
assert "#6cc700" not in src and "#58a600" not in src, "no green left"
assert startup.GREEN.name() == "#c8102e" and startup.GREY.name() == "#0a2a5e"

# hovering swaps the colours: navy tiles turn red, the red chosen tile turns navy
from sitewright.startup import NAVY, RED, NavTile
t = NavTile("Open")
assert t.colour() == NAVY
t.hover = True
assert t.colour() == RED
t.hover = False
t.set_active(True)
assert t.colour() == RED
t.hover = True
assert t.colour() == NAVY
assert src.count("QPushButton:hover{background:#0a2a5e}") >= 2
assert "QPushButton:hover{background:#c8102e}" in src

w.deleteLater()
app.processEvents()
del w
print("ALL GOOD")
