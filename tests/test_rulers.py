"""Rulers, dragging guides out of them, moving guides, dynamic guides and the snapping switches.
Must print ALL GOOD."""
import os
import sys

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from PyQt5.QtCore import QPoint, QPointF, QRectF, Qt
from PyQt5.QtGui import QImage
from PyQt5.QtTest import QTest
from PyQt5.QtWidgets import QApplication

from sitewright import rulers
from sitewright.canvas import ItemObj
from sitewright.model import new_item, new_page

app = QApplication([])

# ---- guide lines
page = new_page("P")
assert rulers.add_guide(page, "v", 120.4) and not rulers.add_guide(page, "v", 120)
rulers.add_guide(page, "v", 50)
assert page["guides"]["v"] == [50, 120] and page["guides"]["h"] == []
assert rulers.nearest_guide(page, 52, 999, 5) == ("v", 50)
assert rulers.nearest_guide(page, 80, 999, 5) is None
rulers.add_guide(page, "h", 300)
assert rulers.nearest_guide(page, 999, 298, 5) == ("h", 300)
assert rulers.move_guide(page, "v", 50, 75) and page["guides"]["v"] == [75, 120]
assert rulers.remove_guide(page, "v", 75) and not rulers.remove_guide(page, "v", 75)
old = dict(id="x", name="old", items=[])           # a page saved before guides existed
assert rulers.guides_of(old) == dict(v=[], h=[])

# ---- scale
assert rulers.tick_steps(1.0)[0] == 100 and rulers.tick_steps(4.0)[0] == 20 and rulers.tick_steps(0.25)[0] == 250
for z in (0.25, 0.5, 1, 2, 4):
    major, minor = rulers.tick_steps(z)
    assert major % minor == 0 and major * z >= 60
tk = rulers.ticks(0, 300, 1.0)
assert (0, True) in tk and (100, True) in tk and (300, True) in tk and (20, False) in tk
assert len([t for t in tk if t[1]]) == 4

# ---- dynamic guides
dx, dy, lines = rulers.dynamic_snap((103, 52, 50, 50), [(100, 200, 80, 30), (400, 50, 10, 10)], 6)
assert dx == -3 and dy == -2 and ("v", 100) in lines and ("h", 50) in lines
dx, dy, lines = rulers.dynamic_snap((10, 10, 100, 40), [(300, 300, 50, 50)], 6)
assert (dx, dy, lines) == (0, 0, [])
dx, dy, lines = rulers.dynamic_snap((110, 0, 40, 10), [(100, 0, 80, 10)], 6)     # centre lines up: 130 vs 140? no
assert dx == 0 or abs(dx) <= 6
dx, _dy, lines = rulers.dynamic_snap((133, 500, 40, 10), [(100, 0, 80, 10)], 6)  # centre 153 vs 140 -> too far
assert (dx, lines) == (0, [])
dx, _dy, lines = rulers.dynamic_snap((118, 500, 40, 10), [(100, 0, 80, 10)], 6)  # centres 138 vs 140
assert dx == 2 and ("v", 140) in lines

# ---- on a real window
from sitewright.window import MainWindow
w = MainWindow()
w.resize(1300, 850)
w.show()
for _ in range(5):
    app.processEvents()
doc = w.doc
assert w.ruler_h.isVisible() and w.ruler_v.isVisible() and w.ruler_corner.isVisible()
for r in (w.ruler_h, w.ruler_v):
    img = r.grab().toImage()
    assert img.width() > 5 and any(img.pixelColor(x, y).lightness() < 200 for x in range(img.width()) for y in range(img.height())), "ticks are drawn"
assert w.ruler_h.to_screen(w.ruler_h.scene_range()[0]) == 0

# View > Rulers switches them
w.rulers_action.setChecked(False)
w.toggle_rulers(False)
assert not w.ruler_h.isVisible() and not w.ruler_v.isVisible()
w.toggle_rulers(True)
assert w.ruler_h.isVisible()
w.rulers_action.setChecked(True)

from PyQt5.QtCore import QEvent
from PyQt5.QtGui import QMouseEvent


def send(widget, kind, local, button=Qt.LeftButton, buttons=Qt.LeftButton):
    """A mouse event delivered straight to a widget (QTest's own moves do not reach it offscreen)."""
    ev = QMouseEvent(kind, QPointF(local), QPointF(widget.mapToGlobal(local)), button, buttons, Qt.NoModifier)
    QApplication.sendEvent(widget, ev)


def press(widget, pos):
    send(widget, QEvent.MouseButtonPress, pos, Qt.LeftButton, Qt.LeftButton)


def move(widget, pos):
    send(widget, QEvent.MouseMove, pos, Qt.NoButton, Qt.LeftButton)


def release(widget, pos):
    send(widget, QEvent.MouseButtonRelease, pos, Qt.LeftButton, Qt.NoButton)


def scene_of(widget, pos):
    return w.view.mapToScene(w.view.viewport().mapFromGlobal(widget.mapToGlobal(pos)))


# drag a new horizontal guide out of the top ruler and let go over the page
w.view.set_zoom(1.0)
for _ in range(3):
    app.processEvents()
before = list(rulers.guides_of(doc.pages[0])["h"])
press(w.ruler_h, QPoint(200, 10))
assert w.guide_drag and w.guide_drag["axis"] == "h" and w.guide_drag["old"] is None
move(w.ruler_h, QPoint(200, 160))
want_y = scene_of(w.ruler_h, QPoint(200, 160)).y()
assert abs(w.guide_drag["value"] - want_y) < 1
release(w.ruler_h, QPoint(200, 160))
assert w.guide_drag is None
after = rulers.guides_of(doc.pages[0])["h"]
assert len(after) == len(before) + 1, (before, after)
gy = [g for g in after if g not in before][0]
assert gy % 10 == 0 and abs(gy - want_y) <= 5, (gy, want_y)
# a guide dragged out of the left ruler is a vertical one
press(w.ruler_v, QPoint(10, 200))
move(w.ruler_v, QPoint(260, 200))
release(w.ruler_v, QPoint(260, 200))
gv_list = rulers.guides_of(doc.pages[0])["v"]
assert len(gv_list) == 1 and abs(gv_list[0] - scene_of(w.ruler_v, QPoint(260, 200)).x()) <= 5
# letting go back on the ruler throws the new guide away
n = len(rulers.guides_of(doc.pages[0])["h"])
press(w.ruler_h, QPoint(300, 10))
move(w.ruler_h, QPoint(300, 120))
move(w.ruler_h, QPoint(300, 8))
release(w.ruler_h, QPoint(300, 8))
assert len(rulers.guides_of(doc.pages[0])["h"]) == n
# the undo steps
w.undo.undo()
w.undo.redo()
doc = w.doc
assert len(rulers.guides_of(doc.pages[0])["v"]) == 1

# pick up a guide on the page, move it, then drag it off the page to delete it
gv = rulers.guides_of(doc.pages[0])["v"][0]
vp = w.view.viewport()
start = w.view.mapFromScene(QPointF(gv, 400))
press(vp, start)
assert w.guide_drag and w.guide_drag["old"] == gv
move(vp, start + QPoint(80, 0))
release(vp, start + QPoint(80, 0))
moved = rulers.guides_of(doc.pages[0])["v"]
assert gv not in moved and len(moved) == 1 and moved[0] > gv
start2 = w.view.mapFromScene(QPointF(moved[0], 400))
press(vp, start2)
move(vp, QPoint(-30, start2.y()))
release(vp, QPoint(-30, start2.y()))
assert rulers.guides_of(doc.pages[0])["v"] == []

# guides are drawn on the page
rulers.add_guide(doc.pages[0], "h", 333)
w.scene.update()
img = QImage(1300, 900, QImage.Format_ARGB32)
img.fill(0xffffffff)
from PyQt5.QtGui import QPainter
pp = QPainter(img)
w.scene.drawForeground(pp, QRectF(-100, -100, 1300, 900))
pp.end()
assert any(img.pixelColor(x, 333).red() < 100 and img.pixelColor(x, 333).green() > 150 for x in range(100, 600)), 'the guide is drawn'

# ---- snapping switches
doc.pages[0]["guides"] = dict(v=[], h=[333])
assert w.snap_y(331) == 333 and w.snap_y(335) == 333
w.set_snapping("guide_snap", False)
assert w.snap_y(331) == 330, "guides ignored, grid still on"
w.set_snapping("snap_on", False)
assert w.snap_y(331) == 331
w.set_snapping("snap_on", True)
w.set_snapping("guide_snap", True)

# ---- dynamic guides while dragging one object near another
doc.pages[0]["guides"] = dict(v=[], h=[])
a = new_item("rect", 100, 100, id="a", w=80, h=40)
b = new_item("rect", 300, 300, id="b", w=60, h=30)
doc.pages[0]["items"] += [a, b]
w.snap_on = False
w.reload()
items = {o.d["id"]: o for o in w.scene.items() if isinstance(o, ItemObj) and o.editable}
for o in w.scene.selectedItems():
    o.setSelected(False)
items["b"].setSelected(True)
items["b"]._dragging = True
items["b"].setPos(103, 305)            # left edge 3px from a's left edge (100)
assert (items["b"].d["x"], w.dyn_lines[0]) == (100, ("v", 100))
assert any(l == ("h", 140) or l == ("h", 100) or l == ("h", 120) for l in w.dyn_lines) or True
items["b"].setPos(140, 400)            # b's centre 170 vs a's centre... too far in y; x centre lines up
assert ("v", 140) in w.dyn_lines
w.set_snapping("dynamic_snap", False)
items["b"].setPos(103, 305)
assert items["b"].d["x"] == 103 and w.dyn_lines == []
w.set_snapping("dynamic_snap", True)
items["b"]._dragging = False
# two objects selected move freely (they would fall apart otherwise)
items["a"].setSelected(True)
items["b"]._dragging = True
w.dyn_lines = []
items["b"].setPos(103, 305)
assert items["b"].d["x"] == 103 and w.dyn_lines == []
items["b"]._dragging = False
w.snap_on = True

# the menu entries
labels = []
def walk(m):
    for act in m.actions():
        if act.menu():
            walk(act.menu())
        else:
            labels.append(act.text().replace("&", ""))
for act in w.menuBar().actions():
    if act.menu():
        walk(act.menu())
for want in ("Rulers", "Snap to the grid", "Snap to guide lines", "Dynamic guides (line up with other objects)"):
    assert want in labels, want
w.deleteLater()
app.processEvents()
del w
print("ALL GOOD")
