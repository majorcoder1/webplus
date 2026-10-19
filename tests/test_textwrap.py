"""Text boxes wrap at the box width (even one long word) and the height follows the text.
Must print ALL GOOD."""
import os
import sys

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from PyQt5.QtCore import QRectF
from PyQt5.QtGui import QImage, QPainter
from PyQt5.QtWidgets import QApplication

from sitewright import textlayout
from sitewright.canvas import ItemObj
from sitewright.model import new_item
from sitewright.window import MainWindow

app = QApplication([])

LONG = "fsafsfasfasfasdfsdgfaGADFGAOJ'OFJOAJDFIOAJ IOJOFDIJHJIDAS'HIDGH['I'HDGI'HIGD'HAIDGHGIDH'AIDGHAIDGHADIG"

# layout: a long unbroken string is broken into several lines instead of running off the edge
d = new_item("text", 0, 0, w=240, text=LONG)
one = textlayout.document(dict(d, text="x"), 240).size().height()
many = textlayout.text_height(d)
assert many > one * 2, (one, many)
doc = textlayout.document(d, 240)
assert doc.idealWidth() <= 240.5, doc.idealWidth()      # nothing sticks out sideways

# narrower box -> taller; wider box -> shorter
narrow = textlayout.text_height(d, 120)
wide = textlayout.text_height(d, 600)
assert narrow > many > wide

# fit_height follows the text for text boxes, not for buttons
assert textlayout.fit_height(d)
assert d["h"] == int(-(-many // 1)) or abs(d["h"] - many) <= 1
b = new_item("button", 0, 0, w=100, h=40, text=LONG)
assert not textlayout.fit_height(b) and b["h"] == 40
d["autoh"] = False
d["h"] = 55
assert not textlayout.fit_height(d) and d["h"] == 55

# every line is really drawn inside the box: paint it and look for ink on the last line row
d2 = new_item("text", 0, 0, w=200, text=LONG)
textlayout.fit_height(d2)
img = QImage(220, int(d2["h"]) + 20, QImage.Format_ARGB32)
img.fill(0xffffffff)
p = QPainter(img)
textlayout.paint(p, QRectF(0, 0, d2["w"], d2["h"]), d2)
p.end()
def ink_in(y0, y1):
    return any(img.pixelColor(x, y).lightness() < 128 for y in range(y0, y1) for x in range(0, 200))
assert ink_in(0, 20), "first line"
assert ink_in(int(d2["h"]) - 18, int(d2["h"]) - 1), "last line is inside the box"
assert not any(img.pixelColor(x, y).lightness() < 128 for y in range(int(d2["h"]) + 2, img.height()) for x in range(220)), "nothing below the box"
assert not any(img.pixelColor(x, y).lightness() < 128 for y in range(img.height()) for x in range(201, 220)), "nothing right of the box"

# on a real window: changing the words or the width resizes the box
w = MainWindow()
w.show()
w.create_item("text", QRectF(20, 20, 200, 90))
t = [o for o in w.scene.items() if isinstance(o, ItemObj) and o.editable][0]
t.setSelected(True)
h0 = t.d["h"]
w.set_prop("text", LONG)
h1 = t.d["h"]
assert h1 > h0 * 2, (h0, h1)
t.d["w"] = 100
w.set_prop("w", 100)
h2 = t.d["h"]
assert h2 > h1, (h1, h2)
w.set_prop("size", 40)
assert t.d["h"] > h2
w.set_prop("text", "short")
assert t.d["h"] < h2

# the published page lets long words wrap as well
from sitewright import export
html_ = export.page_source(w.doc, w.doc.pages[0]["id"], False)
assert "overflow-wrap:anywhere" in html_

w.deleteLater()
app.processEvents()
del w
print("ALL GOOD")
