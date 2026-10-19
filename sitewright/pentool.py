"""The pen tool (click for corners, drag for curves) and the point editor for drawn shapes."""
import math

from PyQt5.QtCore import QPointF, QRectF, Qt
from PyQt5.QtGui import QColor, QPen, QPolygonF, QTransform
from PyQt5.QtWidgets import QMenu

from . import shapes
from .model import new_item

ANCHOR = QColor("#1e90ff")
HANDLE = QColor("#e0178a")


def view_scale(win):
    return max(win.view.transform().m11(), 0.05)


class PenController:
    """Drawing a new shape point by point."""

    def __init__(self, win):
        self.win = win
        self.reset()

    def reset(self):
        self.pts = []              # nodes in page pixels
        self.dragging = False
        self.cursor = None

    @property
    def active(self):
        return self.win.tool == "pen"

    def pos(self, e):
        p = self.win.view.mapToScene(e.pos())
        return QPointF(self.win.snap_x(p.x()), self.win.snap_y(p.y()))

    def press(self, e):
        if e.button() != Qt.LeftButton:
            return True
        p = self.pos(e)
        tol = 9 / view_scale(self.win)
        if len(self.pts) >= 3 and math.hypot(p.x() - self.pts[0][0], p.y() - self.pts[0][1]) < tol:
            self.finish(True)
            return True
        self.pts.append(shapes.node(p.x(), p.y()))
        self.dragging = True
        self.win.scene.update()
        return True

    def move(self, e):
        p = self.pos(e)                                   # snapped to the grid and guides like everything else
        self.cursor = p
        if self.dragging and self.pts:
            n = self.pts[-1]
            if math.hypot(p.x() - n[0], p.y() - n[1]) > 3 / view_scale(self.win):
                n[4], n[5] = p.x(), p.y()                         # the curve leaves toward the mouse...
                n[2], n[3] = 2 * n[0] - p.x(), 2 * n[1] - p.y()   # ...and arrives from the opposite side
                n[6] = True
        self.win.scene.update()
        return True

    def release(self, e):
        self.dragging = False
        return True

    def double_click(self, e):
        if len(self.pts) >= 2:
            self.finish(False)
        return True

    def key(self, e):
        if e.key() in (Qt.Key_Return, Qt.Key_Enter):
            self.finish(False)
        elif e.key() == Qt.Key_Escape:
            self.reset()
            self.win.set_tool("select")
            self.win.scene.update()
        elif e.key() == Qt.Key_Backspace and self.pts:
            self.pts.pop()
            self.win.scene.update()
        else:
            return False
        return True

    def finish(self, closed):
        pts, self.pts = self.pts, []
        self.dragging = False
        win = self.win
        if len(pts) < 2:
            win.set_tool("select")
            win.scene.update()
            return
        x, y, w, h, norm = shapes.fit_to_box(pts, closed, 0, 0)
        d = new_item("shape", round(x, 2), round(y, 2), nodes=norm, closed=closed, preset="")
        d["w"], d["h"] = round(w, 2), round(h, 2)
        if not closed:
            d["fill"] = ""
        win.set_tool("select")
        win.target_list().append(d)
        win.reload({d["id"]})
        win.commit_if_changed("Draw shape")
        win.statusBar().showMessage("Double-click the shape to edit its points", 6000)

    def paint(self, p):
        if not self.pts:
            return
        s = view_scale(self.win)
        nodes = [list(n) for n in self.pts]
        if self.cursor is not None and not self.dragging:
            nodes.append(shapes.node(self.cursor.x(), self.cursor.y()))
        p.setPen(QPen(QColor("#1e90ff"), 1.5 / s))
        p.setBrush(Qt.NoBrush)
        p.drawPath(shapes.qpath(nodes, False))
        for n in self.pts:
            p.setBrush(QColor("white"))
            p.drawRect(QRectF(n[0] - 3 / s, n[1] - 3 / s, 6 / s, 6 / s))
            if n[6]:
                p.setPen(QPen(HANDLE, 1 / s))
                p.drawLine(QPointF(n[2], n[3]), QPointF(n[4], n[5]))
                p.setPen(QPen(ANCHOR, 1.5 / s))


class NodeEditor:
    """Moving, adding and removing the points of a drawn shape."""

    def __init__(self, win):
        self.win = win
        self.d = None
        self.sel = -1
        self.drag = None            # ("anchor"|"in"|"out", index, last scene point)
        self.before = None
        self.grab = QPointF(0, 0)

    @property
    def active(self):
        return self.d is not None

    def start(self, d):
        from .extras import shape_nodes_of
        shape_nodes_of(d)
        self.d, self.sel, self.drag = d, -1, None
        self.win.statusBar().showMessage(
            "Editing points: drag a point or its handles, click the line to add a point, "
            "right-click a point for more, Esc to finish", 10000)
        self.win.scene.update()

    def stop(self):
        if self.d is not None:
            self.d, self.sel, self.drag = None, -1, None
            self.win.scene.update()

    # coordinates: nodes are 0..1 across the object's box; a turned or flipped shape is mapped through the
    # same transform the object is drawn with
    @staticmethod
    def transform_for(d):
        r = QRectF(0, 0, d["w"], d["h"])
        t = QTransform()
        t.translate(r.center().x(), r.center().y())
        t.rotate(d.get("rot", 0))
        t.scale(-1 if d.get("fx") else 1, -1 if d.get("fy") else 1)
        t.translate(-r.center().x(), -r.center().y())
        return t * QTransform.fromTranslate(d["x"], d["y"])          # turn about the centre, then put it on the page

    def to_scene(self, n, i):
        d = self.d
        return self.transform_for(d).map(QPointF(n[i] * d["w"], n[i + 1] * d["h"]))

    def from_scene(self, p):
        d = self.d
        q, ok = self.transform_for(d).inverted()
        q = q.map(p)
        return q.x() / max(d["w"], 1e-6), q.y() / max(d["h"], 1e-6)

    def local(self, p):
        """A scene point in the shape's own pixels (before it was turned or flipped)."""
        q, ok = self.transform_for(self.d).inverted()
        return q.map(p)

    def hit(self, p):
        d, s = self.d, view_scale(self.win)
        tol = 8 / s
        nodes = d["nodes"]
        order = ([self.sel] if self.sel >= 0 else []) + [i for i in range(len(nodes)) if i != self.sel]
        for i in order[:1] if self.sel >= 0 else []:     # the chosen point's handles come first
            n = nodes[i]
            for kind, k in (("in", 2), ("out", 4)):
                if not shapes.is_corner(n) or n[6]:
                    q = self.to_scene(n, k)
                    if math.hypot(q.x() - p.x(), q.y() - p.y()) < tol and (q != self.to_scene(n, 0)):
                        return kind, i
        for i in range(len(nodes)):
            q = self.to_scene(nodes[i], 0)
            if math.hypot(q.x() - p.x(), q.y() - p.y()) < tol:
                return "anchor", i
        local = self.local(p)
        seg = shapes.hit_segment(nodes, d.get("closed", True), d["w"], d["h"], local, 6 / s)
        if seg >= 0:
            return "segment", seg
        return None

    def press(self, e):
        win = self.win
        p = win.view.mapToScene(e.pos())
        h = self.hit(p)
        if h is None:
            self.stop()
            return False
        kind, i = h
        d = self.d
        if e.button() == Qt.RightButton:
            if kind == "anchor":
                self.sel = i
                self.menu(i, e.globalPos())
            return True
        if e.button() != Qt.LeftButton:
            return True
        self.before = win.doc.snapshot()
        if kind == "segment":
            local = self.local(p)
            i = shapes.insert_node(d["nodes"], d.get("closed", True), i, d["w"], d["h"], local)
            kind = "anchor"
        self.sel = i
        self.drag = (kind, i, p)
        a = self.to_scene(d["nodes"][i], 0)
        self.grab = QPointF(p.x() - a.x(), p.y() - a.y())          # where on the point the mouse took hold
        win.scene.update()
        return True

    def move(self, e):
        if self.drag is None:
            return False
        kind, i, last = self.drag
        win = self.win
        p = win.view.mapToScene(e.pos())
        n = self.d["nodes"][i]
        if kind == "anchor":
            target = QPointF(p.x() - self.grab.x(), p.y() - self.grab.y())       # where the point itself would land
            target = QPointF(win.snap_x(target.x()), win.snap_y(target.y()))     # ...snapped to the grid and guides
            nx, ny = self.from_scene(target)
            dx, dy = nx - n[0], ny - n[1]
            for k in (0, 2, 4):
                n[k] += dx
                n[k + 1] += dy
        else:
            q = QPointF(win.snap_x(p.x()), win.snap_y(p.y()))
            nx, ny = self.from_scene(q)
            k = 2 if kind == "in" else 4
            n[k], n[k + 1] = nx, ny
            if not (e.modifiers() & Qt.AltModifier):                   # Alt breaks the smoothness
                o = 4 if kind == "in" else 2
                n[o], n[o + 1] = 2 * n[0] - nx, 2 * n[1] - ny          # keep the curve smooth through the point
                n[6] = True
            else:
                n[6] = False
        self.drag = (kind, i, p)
        win.scene.update()
        return True

    def release(self, e):
        if self.drag is None:
            return False
        self.drag = None
        self.refit()
        return True

    def refit(self):
        d = self.d
        turned = bool(d.get("rot") or d.get("fx") or d.get("fy"))
        keep = self.to_scene(d["nodes"][0], 0) if turned else None       # a point that must not move on the page
        shapes.refit(d)
        if turned:
            # the box changed size, so it turns about a new centre: put it where the kept point lands as before
            d["x"] = d["y"] = 0
            moved = self.to_scene(d["nodes"][0], 0)
            d["x"], d["y"] = round(keep.x() - moved.x(), 2), round(keep.y() - moved.y(), 2)
        self.win.reload({d["id"]})
        self.win.commit_if_changed("Edit points")
        self.win.scene.update()

    def key(self, e):
        if e.key() == Qt.Key_Escape:
            self.stop()
        elif e.key() in (Qt.Key_Delete, Qt.Key_Backspace) and self.sel >= 0:
            self.delete(self.sel)
        else:
            return False
        return True

    def delete(self, i):
        d = self.d
        floor = 3 if d.get("closed", True) else 2
        if len(d["nodes"]) <= floor:
            self.win.statusBar().showMessage("A shape needs at least %d points" % floor, 4000)
            return
        del d["nodes"][i]
        self.sel = -1
        self.refit()

    def smooth(self, i, on):
        d = self.d
        nodes = d["nodes"]
        n = nodes[i]
        if on:
            prev, nxt = nodes[(i - 1) % len(nodes)], nodes[(i + 1) % len(nodes)]
            tx, ty = (nxt[0] - prev[0]) / 6.0, (nxt[1] - prev[1]) / 6.0
            n[2], n[3], n[4], n[5] = n[0] - tx, n[1] - ty, n[0] + tx, n[1] + ty
            n[6] = True
        else:
            n[2], n[3], n[4], n[5] = n[0], n[1], n[0], n[1]
            n[6] = False
        self.refit()

    def toggle_closed(self):
        self.d["closed"] = not self.d.get("closed", True)
        self.refit()

    def menu(self, i, gpos):
        m = QMenu(self.win)
        smooth = shapes.is_corner(self.d["nodes"][i])
        m.addAction("Make smooth" if smooth else "Make corner", lambda: self.smooth(i, smooth))
        m.addAction("Delete point", lambda: self.delete(i))
        m.addSeparator()
        m.addAction("Open the path" if self.d.get("closed", True) else "Close the path", self.toggle_closed)
        m.addAction("Finish editing", self.stop)
        m.exec_(gpos)

    def paint(self, p):
        if self.d is None:
            return
        d, s = self.d, view_scale(self.win)
        p.setBrush(Qt.NoBrush)
        p.setPen(QPen(QColor("#1e90ff"), 1 / s, Qt.DashLine))
        p.drawPolygon(self.transform_for(d).map(QPolygonF(QRectF(0, 0, d["w"], d["h"]))))
        nodes = d["nodes"]
        for i, n in enumerate(nodes):
            a = self.to_scene(n, 0)
            if i == self.sel and (not shapes.is_corner(n) or n[6]):
                for k in (2, 4):
                    q = self.to_scene(n, k)
                    p.setPen(QPen(HANDLE, 1 / s))
                    p.drawLine(a, q)
                    p.setBrush(HANDLE)
                    p.drawEllipse(q, 3.5 / s, 3.5 / s)
            p.setPen(QPen(ANCHOR, 1.5 / s))
            p.setBrush(ANCHOR if i == self.sel else QColor("white"))
            p.drawRect(QRectF(a.x() - 4 / s, a.y() - 4 / s, 8 / s, 8 / s))
