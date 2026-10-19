"""Pen tool, drawn shapes, point editing, shape presets and their export. Must print ALL GOOD."""
import os
import re
import sys
import tempfile

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from PyQt5.QtCore import QPoint, QPointF, QRectF, Qt
from PyQt5.QtWidgets import QApplication

from sitewright import export, shapes
from sitewright.window import MainWindow

app = QApplication([])
w = MainWindow()
w.show()
w._sel_guard = True


class Ev:
    def __init__(self, scene_pt, button=Qt.LeftButton, mods=Qt.NoModifier):
        self._p = w.view.mapFromScene(QPointF(*scene_pt))
        self._b, self._m = button, mods

    def pos(self):
        return self._p

    def globalPos(self):
        return QPoint(0, 0)

    def button(self):
        return self._b

    def modifiers(self):
        return self._m


def key(k):
    class K:
        def key(self):
            return k
    return K()


# presets round trip through svg
for name in shapes.PRESETS:
    nodes = shapes.preset_nodes(name)
    d = shapes.svg_d(nodes, True, 100, 100)
    assert d.startswith("M") and d.endswith("Z"), name
w.grid_on = w.snap_on = False

# pen: three corners then click the first point to close
w.set_tool("pen")
for pt in ((100, 100), (300, 100), (200, 260)):
    w.pen.press(Ev(pt))
    w.pen.release(Ev(pt))
w.pen.press(Ev((100, 100)))
items = w.cur_page()["items"]
assert len(items) == 1 and items[0]["kind"] == "shape" and items[0]["closed"] and len(items[0]["nodes"]) == 3
d = items[0]
assert abs(d["x"] - 100) < 1.5 and abs(d["w"] - 200) < 3 and abs(d["h"] - 160) < 3, d
assert w.tool == "select"

# pen: a curve by dragging, finished with Enter (open path)
w.set_tool("pen")
w.pen.press(Ev((400, 100)))
w.pen.move(Ev((450, 60)))
w.pen.release(Ev((450, 60)))
w.pen.press(Ev((600, 100)))
w.pen.release(Ev((600, 100)))
w.pen.key(key(Qt.Key_Return))
c = w.cur_page()["items"][-1]
assert not c["closed"] and c["fill"] == "" and c["nodes"][0][6] is True and not shapes.is_corner(c["nodes"][0])

# edit points: drag a corner of the triangle, add a point on an edge, delete a point
w.reload({d["id"]})
w.nodes.start(d)
assert w.nodes.active
a0 = w.nodes.to_scene(d["nodes"][0], 0)
w.nodes.press(Ev((a0.x(), a0.y())))
assert w.nodes.drag and w.nodes.drag[0] == "anchor"
w.nodes.move(Ev((a0.x() - 20, a0.y() - 30)))
w.nodes.release(Ev((a0.x() - 20, a0.y() - 30)))
assert abs(d["x"] - 80) < 2 and abs(d["y"] - 70) < 2, (d["x"], d["y"])
n_before = len(d["nodes"])
w.nodes.start(d)
mid = QPointF(d["x"] + d["w"] / 2, d["y"])           # on the top edge
q = (d["x"] + d["w"] * (d["nodes"][0][0] + d["nodes"][1][0]) / 2, d["y"] + d["h"] * (d["nodes"][0][1] + d["nodes"][1][1]) / 2)
w.nodes.press(Ev(q))
w.nodes.release(Ev(q))
assert len(d["nodes"]) == n_before + 1
w.nodes.delete(1)
assert len(d["nodes"]) == n_before
w.nodes.smooth(0, True)
assert not shapes.is_corner(d["nodes"][0])
w.nodes.smooth(0, False)
assert shapes.is_corner(d["nodes"][0])
w.nodes.stop()

# preset tool
w.create_item("shape:heart", __import__("PyQt5.QtCore", fromlist=["QRectF"]).QRectF(500, 300, 120, 120))
h = w.cur_page()["items"][-1]
assert h["kind"] == "shape" and h["preset"] == "heart"

# export
out = tempfile.mkdtemp()
export.export_site(w.doc, out)
html = open(os.path.join(out, "index.html")).read()
assert html.count("<svg") >= 3 and 'vector-effect="non-scaling-stroke"' in html
assert re.search(r'<path d="M[^"]+Z"', html)
print("ALL GOOD")

# points snap to the grid while they are moved
w.grid_on = w.snap_on = True
w.cur_page()["items"].clear()
w.create_item("shape:triangle", QRectF(100, 100, 100, 100))
tri = w.cur_page()["items"][-1]
w.reload({tri["id"]})
w.nodes.start(tri)
a = w.nodes.to_scene(tri["nodes"][0], 0)
w.nodes.press(Ev((a.x(), a.y())))
w.nodes.move(Ev((a.x() + 13, a.y() - 17)))
moved = w.nodes.to_scene(tri["nodes"][0], 0)
g = w.snap_x(moved.x())
assert abs(moved.x() - g) < 0.6 and abs(moved.y() - w.snap_y(moved.y())) < 0.6, (moved.x(), moved.y())
w.nodes.release(Ev((a.x() + 13, a.y() - 17)))
w.nodes.stop()
w.grid_on = w.snap_on = False

# turned and flipped shapes can be edited, and the shape stays where it is on the page
for rot, fx in ((30, False), (90, True), (0, True)):
    w.cur_page()["items"].clear()
    w.create_item("shape:pentagon", QRectF(200, 200, 120, 80))
    sh = w.cur_page()["items"][-1]
    sh.update(rot=rot, fx=fx)
    w.reload({sh["id"]})
    w.nodes.start(sh)
    assert w.nodes.active
    before = [w.nodes.to_scene(n, 0) for n in sh["nodes"]]
    p0 = before[0]
    w.nodes.press(Ev((p0.x(), p0.y())))
    assert w.nodes.drag and w.nodes.drag[0] == "anchor"
    w.nodes.move(Ev((p0.x() + 25, p0.y() + 10)))
    w.nodes.release(Ev((p0.x() + 25, p0.y() + 10)))
    after = [w.nodes.to_scene(n, 0) for n in sh["nodes"]]
    assert abs(after[0].x() - (p0.x() + 25)) < 1 and abs(after[0].y() - (p0.y() + 10)) < 1, (rot, fx, after[0], p0)
    for b, a_ in zip(before[1:], after[1:]):
        assert abs(b.x() - a_.x()) < 1 and abs(b.y() - a_.y()) < 1, (rot, fx, b, a_)
    assert sh["rot"] == rot and sh["fx"] == fx
    # clicking a point of a turned shape picks that point, not another
    w.nodes.start(sh)
    q = w.nodes.to_scene(sh["nodes"][2], 0)
    w.nodes.press(Ev((q.x(), q.y())))
    assert w.nodes.drag and w.nodes.drag[1] == 2
    w.nodes.release(Ev((q.x(), q.y())))
    w.nodes.stop()
print("ALL GOOD")
