"""Artistic text on a curve, Fit text to path, and the overflowing-text options. Must print ALL GOOD."""
import os
import sys

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from PyQt5.QtCore import QRectF
from PyQt5.QtGui import QImage, QPainter
from PyQt5.QtWidgets import QApplication

from sitewright import export, pathtext, textlayout
from sitewright.canvas import ItemObj
from sitewright.model import DEFAULTS, new_item
from sitewright.window import MainWindow

app = QApplication([])


def ink_box(d):
    img = QImage(int(d["w"]) + 40, int(d["h"]) + 40, QImage.Format_ARGB32)
    img.fill(0xffffffff)
    p = QPainter(img)
    pathtext.paint(p, QRectF(20, 20, d["w"], d["h"]), d)
    p.end()
    xs, ys = [], []
    for y in range(img.height()):
        for x in range(img.width()):
            if img.pixelColor(x, y).lightness() < 140:
                xs.append(x)
                ys.append(y)
    return (min(xs), min(ys), max(xs), max(ys)) if xs else None


# the shapes: a straight line, an arch, a bowl, a wave and a ring all put letters on the page
base = new_item("arttext", 0, 0, w=420, h=200, text="CURVED WORDS", size=40, color="#000000")
boxes = {}
for shape, curve in (("arc", 0), ("arc", 60), ("arc", -60), ("wave", 60), ("ring", 0)):
    d = dict(base, shape=shape, curve=curve)
    boxes[(shape, curve)] = ink_box(d)
    assert boxes[(shape, curve)] is not None, (shape, curve)
flat, arch, bowl = boxes[("arc", 0)], boxes[("arc", 60)], boxes[("arc", -60)]
assert (arch[3] - arch[1]) > (flat[3] - flat[1]) + 20, "an arch is taller than straight text"
ring = boxes[("ring", 0)]
assert (ring[3] - ring[1]) > 100, "the ring reaches around"

# letters sit on the path: at 0 curve every letter has the same height; on an arch the middle is higher
items, _f = pathtext.placements(dict(base, shape="arc", curve=0))
assert len({round(y, 1) for _c, _x, y, _a, _w in items}) == 1
items, _f = pathtext.placements(dict(base, shape="arc", curve=70))
ys = [y for _c, _x, y, _a, _w in items]
assert min(ys) < ys[0] - 10 and abs(ys[0] - ys[-1]) < 3, "ends level, middle higher"
angs = [((a + 180) % 360) - 180 for _c, _x, _y, a, _w in items]
assert angs[0] > 0 > angs[-1] or angs[0] < 0 < angs[-1], "letters lean one way then the other"

# long words are shrunk to fit the curve
long_d = dict(base, text="A MUCH LONGER SENTENCE THAT CANNOT FIT", w=200, size=40)
assert pathtext.fit_scale(long_d, pathtext.baseline_path(long_d)[0].length()) < 1
assert pathtext.fit_scale(base, pathtext.baseline_path(base)[0].length()) == 1.0

# export is an SVG with a text path
html_ = pathtext.svg_html(dict(base, id="abc"), "left:0px;top:0px;width:420px;height:200px")
assert "<textPath" in html_ and 'id="ap-abc"' in html_ and "CURVED WORDS" in html_
assert 'startOffset="50%"' in html_ and "<path " in html_
assert 'startOffset="25%"' in pathtext.svg_html(dict(base, id="r", shape="ring"), "x")
assert "&lt;b&gt;" in pathtext.svg_html(dict(base, id="e", text="<b>"), "x")

# on a real window: the tool draws one, Fit text to path converts a text box, undo restores it
w = MainWindow()
w.show()
w.create_item("arttext", QRectF(20, 20, 420, 200))
a = [o for o in w.scene.items() if isinstance(o, ItemObj) and o.editable][0]
assert a.d["kind"] == "arttext" and a.d["text"] == "Artistic text"
a.setSelected(True)
w.set_prop("curve", -30)
w.set_prop("shape", "wave")
assert a.d["curve"] == -30 and a.d["shape"] == "wave"
page_html = export.page_source(w.doc, w.doc.pages[0]["id"], False)
assert "<textPath" in page_html and "Artistic text" in page_html

for o in w.scene.selectedItems():
    o.setSelected(False)
w.doc.pages[0]["items"].clear()
w.create_item("text", QRectF(20, 300, 260, 80))
t = [o for o in w.scene.items() if isinstance(o, ItemObj) and o.editable][0]
t.setSelected(True)
w.set_prop("text", "Make me curve")
w.commit_if_changed("setup")
w.fit_text_to_path()
conv = w.doc.pages[0]["items"][0]
assert conv["kind"] == "arttext" and conv["text"] == "Make me curve" and conv["curve"] == 45
w.undo.undo()
assert w.doc.pages[0]["items"][0]["kind"] == "text"

# overflowing text: four options, a fixed height is kept, scroll CSS goes to the page
t = [o for o in w.scene.items() if isinstance(o, ItemObj) and o.editable][0]
t.setSelected(True)
w.set_prop("text", "line\n" * 12)
for value, css in (("hidden", "overflow:hidden"), ("visible", "overflow:visible"),
                   ("auto", "overflow:auto"), ("scroll", "overflow:scroll")):
    w.set_overflow(value)
    d = w.doc.pages[0]["items"][0]
    assert d["overflow"] == value and d["autoh"] is False
    assert css in export.page_source(w.doc, w.doc.pages[0]["id"], False), value
h = w.doc.pages[0]["items"][0]["h"]
w.set_prop("text", "line\n" * 30)
assert w.doc.pages[0]["items"][0]["h"] == h, "a fixed box does not grow"

# overflow drawing: a scroll bar appears in the editor, 'visible' lets the box report more room
d = dict(w.doc.pages[0]["items"][0], overflow="scroll", w=200, h=60)
img = QImage(220, 80, QImage.Format_ARGB32)
img.fill(0xffffffff)
p = QPainter(img)
textlayout.paint(p, QRectF(0, 0, 200, 60), d)
p.end()
assert any(img.pixelColor(x, y).lightness() < 200 for x in range(190, 200) for y in range(0, 60)), "scroll bar thumb"
t2 = [o for o in w.scene.items() if isinstance(o, ItemObj) and o.editable][0]
small = t2.boundingRect().height()
w.set_overflow("visible")
t2 = [o for o in w.scene.items() if isinstance(o, ItemObj) and o.editable][0]
assert t2.boundingRect().height() > small

# menus
labels = []
def walk(m):
    for a2 in m.actions():
        if a2.menu():
            walk(a2.menu())
        else:
            labels.append(a2.text().replace("&", ""))
for a2 in w.menuBar().actions():
    if a2.menu():
        walk(a2.menu())
for want in ("Artistic text (curved words)", "Fit text to path", "Hidden (cut off)",
             "Overflow (spills out)", "Auto scroll bar", "Fixed scroll bar"):
    assert want in labels, want
assert any(k == "arttext" for k in DEFAULTS)
w.deleteLater()
app.processEvents()
del w
print("ALL GOOD")
