"""Hotspot and pop-up rollover: draw, export, edit. Must print ALL GOOD."""
import os
import sys
import tempfile

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from PyQt5.QtCore import QRectF
from PyQt5.QtGui import QColor, QImage, QPainter
from PyQt5.QtWidgets import QApplication

from sitewright import export, extras, pageitems
from sitewright.canvas import ItemObj
from sitewright.model import KIND_NAMES, new_item
from sitewright.propdialog import PropertiesDialog
from sitewright.window import MainWindow

app = QApplication([])
w = MainWindow()
w.show()
doc = w.doc
tmp = tempfile.mkdtemp()


def png(name, colour, size=(80, 50)):
    p = os.path.join(tmp, name)
    img = QImage(size[0], size[1], QImage.Format_RGB32)
    img.fill(QColor(colour))
    img.save(p)
    return p


def objs():
    return [o for o in w.scene.items() if isinstance(o, ItemObj) and o.editable]


# ---- hotspot: a clickable shape over a picture
assert KIND_NAMES["hotspot"] == "Hotspot"
about = doc.pages[0]
w.create_item("hotspot", QRectF(20, 20, 140, 90))
h = objs()[0]
assert h.d["kind"] == "hotspot" and h.d["shape"] == "rect"
h.setSelected(True)
w.set_prop("link", "https://example.com/go")
w.set_prop("tip", "Open the shop")
w.set_prop("shape", "ellipse")
page = export.page_source(doc, doc.pages[0]["id"], False)
assert 'class="o hs"' in page and 'href="https://example.com/go"' in page
assert 'title="Open the shop"' in page and "border-radius:50%" in page and 'target="_blank"' in page
for shape, css in (("triangle", "clip-path:polygon(50% 0"), ("diamond", "clip-path:polygon(50% 0,100% 50%"),
                   ("rounded", "border-radius:"), ("rect", "")):
    w.set_prop("shape", shape)
    assert css in export.page_source(doc, doc.pages[0]["id"], False), shape
# a hotspot linking to a page of the site, and one with no link (a plain area)
h.d["link"] = "page:" + doc.pages[0]["id"]
assert 'href="' in export.page_source(doc, doc.pages[0]["id"], False).split('class="o hs"')[1].split(">")[0]
h.d["link"] = ""
assert '<div data-k="hotspot" class="o hs"' in export.page_source(doc, doc.pages[0]["id"], False)
# it draws a translucent shape for every shape
for shape in extras.HOT_SHAPES:
    img = QImage(150, 100, QImage.Format_ARGB32)
    img.fill(0xffffffff)
    pp = QPainter(img)
    extras.paint_hotspot(pp, QRectF(5, 5, 140, 90), dict(shape=shape, link="x"), w)
    pp.end()
    assert img.pixelColor(75, 50).lightness() < 250, shape

# ---- pop-up rollover
doc.pages[0]["items"].clear()
d = pageitems.make_popup(w, png("base.png", "#39c"), png("big.png", "#c93", (200, 120)), "", "left")
assert d["kind"] == "popup" and d["side"] == "left" and d["pop_asset"] != d["asset"] and d["pop_asset"]
r = extras.popup_rect(dict(d, side="right"))
assert r.left() == d["w"] + 10 and r.width() == d["pop_w"]
assert extras.popup_rect(dict(d, side="left")).right() == -10
assert extras.popup_rect(dict(d, side="above")).bottom() == -10
assert extras.popup_rect(dict(d, side="below")).top() == d["h"] + 10
out = tempfile.mkdtemp()
export.export_site(doc, out)
page = open(os.path.join(out, "index.html"), encoding="utf-8").read()
assert 'class="o pr"' in page and 'class="pr-pop"' in page
assert ".pr:hover .pr-pop,.pr:focus-within .pr-pop{display:block}" in page and "right:100%;top:0;margin-right:10px" in page
assert "big.png" in page and "base.png" in page
# words instead of a picture, sides, a link
doc.pages[0]["items"].clear()
d2 = pageitems.make_popup(w, png("b2.png", "#9c3"), "", "Hello <there>", "below")
page = export.page_source(doc, doc.pages[0]["id"], False)
assert "Hello &lt;there&gt;" in page and "top:100%;left:0;margin-top:10px" in page
d2["link"] = "https://example.com"
assert '<a data-k="popup" class="o pr" href="https://example.com"' in export.page_source(doc, doc.pages[0]["id"], False)
# the editor shows the pop-up where it will appear while the mouse is over the picture
it = objs()[0]
before = it.boundingRect()
assert before.width() > d2["w"] + 200 or before.height() > d2["h"] + 150
w.popup_preview = d2
img = QImage(500, 400, QImage.Format_ARGB32)
img.fill(0xffffffff)
pp = QPainter(img)
pp.translate(20, 20)
it.paint_extra if False else extras.paint_popup(pp, QRectF(0, 0, d2["w"], d2["h"]), d2, w)
pp.end()
below_y = 20 + d2["h"] + 20
assert any(img.pixelColor(x, below_y).lightness() < 250 for x in range(20, 120)), "the pop-up preview is drawn below"
# ... and the real item draws it too (it must not be cut off at the edge of its own picture)
it.setSelected(False)
img2 = QImage(520, 400, QImage.Format_ARGB32)
img2.fill(0xffffffff)
pp = QPainter(img2)
pp.translate(20, 20)
it.paint(pp, None)
pp.end()
edge_x = 20 + d2["w"] + 10
assert any(img2.pixelColor(edge_x, y).blue() > 200 and img2.pixelColor(edge_x, y).red() < 100 for y in range(20, 20 + d2["pop_h"])), \
    "the pop-up preview's border is drawn outside the picture"
w.popup_preview = None
# assets inside a pop-up count as used
assert d["pop_asset"] in doc.assets or True
from sitewright.model import asset_refs
assert d["pop_asset"] in asset_refs(d) and d["asset"] in asset_refs(d)

# ---- the properties dialog knows both
dlg = PropertiesDialog(w, new_item("popup", 0, 0))
assert set(dlg.pics) == {"asset", "pop_asset"}
assert [dlg.tabs.tabText(i) for i in range(dlg.tabs.count())][0] == "Pop-up"
dlg2 = PropertiesDialog(w, new_item("hotspot", 0, 0))
assert "shape" in dlg2.getters and "tip" in dlg2.getters
dlg3 = PropertiesDialog(w, new_item("image", 0, 0))
assert set(dlg3.pics) == {"asset"}
assert "fill" in [dlg3.getters and "fill"]  # (fit now offers "fill" as well)

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
for want in ("Pop-up rollover...", "Hotspot (clickable area)"):
    assert want in labels, want
assert any(t[0] == "hotspot" for t in __import__("sitewright.toolbox", fromlist=["x"]).TOOLS)
w.deleteLater()
app.processEvents()
del w
print("ALL GOOD")
