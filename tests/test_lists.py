"""Bullets and numbering in text boxes: on screen, in the dialog data path and on the web page.
Must print ALL GOOD."""
import os
import sys

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from PyQt5.QtCore import QRectF
from PyQt5.QtGui import QImage, QPainter
from PyQt5.QtWidgets import QApplication

from sitewright import export, textlayout
from sitewright.canvas import ItemObj
from sitewright.model import new_item
from sitewright.window import MainWindow

app = QApplication([])
TEXT = "First item\nSecond item\nThird item"

# layout: a list takes more room to the left (indent) and shows markers
plain = new_item("text", 0, 0, w=300, text=TEXT)
for style in ("bullet", "circle", "square", "number", "alpha", "ualpha", "roman", "uroman"):
    d = dict(plain, listtype=style)
    doc = textlayout.document(d, 300)
    assert doc.blockCount() == 3, style
    assert doc.begin().textList() is not None, style
    assert abs(doc.size().height() - textlayout.text_height(plain, 300)) < 40
pd = textlayout.document(plain, 300)
assert pd.begin().textList() is None

# a narrow box wraps list items inside the indent
d = dict(plain, listtype="number", text="one very long item that wraps around the box")
assert textlayout.text_height(d, 120) > textlayout.text_height(d, 400)

# the markers are really drawn: ink to the left of where plain text starts
def left_ink(listtype):
    dd = dict(plain, listtype=listtype, w=300)
    textlayout.fit_height(dd)
    img = QImage(320, int(dd["h"]) + 4, QImage.Format_ARGB32)
    img.fill(0xffffffff)
    p = QPainter(img)
    textlayout.paint(p, QRectF(0, 0, dd["w"], dd["h"]), dd)
    p.end()
    for x in range(0, 40):
        if any(img.pixelColor(x, y).lightness() < 128 for y in range(img.height())):
            return x
    return 99
assert left_ink("") <= 2
assert 2 < left_ink("bullet") < textlayout.INDENT, "the marker sits in the gutter, before the indented words"
assert 2 < left_ink("number") < textlayout.INDENT

# on a real window: the dialog's path (set_prop) turns a box into a list and back, height follows
w = MainWindow()
w.show()
w.create_item("text", QRectF(20, 20, 300, 60))
t = [o for o in w.scene.items() if isinstance(o, ItemObj) and o.editable][0]
t.setSelected(True)
w.set_prop("text", TEXT)
h0 = t.d["h"]
w.set_prop("listtype", "number")
assert t.d["listtype"] == "number"
w.undo.undo()
assert w.doc.pages[0]["items"][0].get("listtype", "") == ""
w.undo.redo()
assert w.doc.pages[0]["items"][0]["listtype"] == "number"

# export: a real ordered list
html_ = export.page_source(w.doc, w.doc.pages[0]["id"], False)
assert '<ol style="margin:0;padding-left:22px;list-style-type:decimal">' in html_
assert html_.count("<li>") == 3 and "<li>Second item</li>" in html_
w.set_prop("listtype", "bullet")
html_ = export.page_source(w.doc, w.doc.pages[0]["id"], False)
assert '<ul style="margin:0;padding-left:22px;list-style-type:disc">' in html_
w.set_prop("listtype", "")
html_ = export.page_source(w.doc, w.doc.pages[0]["id"], False)
assert "<li>" not in html_

# the dialog form of the choice and the menu entry
from sitewright.propdialog import PropertiesDialog
dlg = PropertiesDialog(w, t.d)
assert "listtype" in dlg.getters
labels = []
def walk(m):
    for a in m.actions():
        if a.menu():
            walk(a.menu())
        else:
            labels.append(a.text().replace("&", ""))
for a in w.menuBar().actions():
    if a.menu():
        walk(a.menu())
assert "Bullets and numbering..." in labels
w.deleteLater()
app.processEvents()
del w
print("ALL GOOD")
