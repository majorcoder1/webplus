"""Rulers along the top and left of the page, guide lines you drag out of them, and 'dynamic
guides' that show when the object you are moving lines up with another one."""
from PyQt5.QtCore import QPointF, Qt
from PyQt5.QtGui import QColor, QFont, QPainter, QPen, QPolygonF
from PyQt5.QtWidgets import QGridLayout, QLabel, QWidget

SIZE = 20
STEPS = [1, 2, 5, 10, 20, 25, 50, 100, 200, 250, 500, 1000, 2000, 5000]


# -- guide lines (plain functions) -----------------------------------------------------
def guides_of(page):
    g = page.setdefault("guides", dict(v=[], h=[]))
    g.setdefault("v", [])
    g.setdefault("h", [])
    return g


def add_guide(page, axis, value):
    value = round(value)
    lst = guides_of(page)[axis]
    if value not in lst:
        lst.append(value)
        lst.sort()
        return True
    return False


def remove_guide(page, axis, value):
    lst = guides_of(page)[axis]
    if value in lst:
        lst.remove(value)
        return True
    return False


def move_guide(page, axis, old, new):
    remove_guide(page, axis, old)
    return add_guide(page, axis, new)


def nearest_guide(page, x, y, tol):
    """(axis, value) of the guide closest to the point within tol, or None."""
    g = guides_of(page)
    best, found = tol + 1, None
    for axis, pos in (("v", x), ("h", y)):
        for v in g[axis]:
            if abs(v - pos) < best:
                best, found = abs(v - pos), (axis, v)
    return found if best <= tol else None


# -- ruler scale ---------------------------------------------------------------------
def tick_steps(zoom):
    """(major, minor) spacing in page pixels: a labelled mark at least ~60 screen pixels apart."""
    major = next((s for s in STEPS if s * zoom >= 60), STEPS[-1])
    divisors = {1: 1, 2: 2, 5: 5, 10: 5, 20: 4, 25: 5, 50: 5, 100: 5, 200: 4, 250: 5, 500: 5, 1000: 5, 2000: 4, 5000: 5}
    minor = max(major // divisors.get(major, 5), 1)
    return major, minor


def ticks(lo, hi, zoom):
    """[(position, is_major)] for the page pixels from lo to hi."""
    major, minor = tick_steps(zoom)
    out = []
    n = int(lo // minor) * minor
    while n <= hi:
        out.append((n, n % major == 0))
        n += minor
    return out


# -- dynamic guides ---------------------------------------------------------------------
def dynamic_snap(rect, others, tol):
    """rect and each of others are (x, y, w, h). Returns (dx, dy, lines): how far to nudge rect so that
    an edge or centre lines up with one of the others, and the lines to draw ('v', x) / ('h', y)."""
    x, y, w, h = rect
    mine_x = [x, x + w / 2.0, x + w]
    mine_y = [y, y + h / 2.0, y + h]
    best_x = best_y = None
    for ox, oy, ow, oh in others:
        for cx in (ox, ox + ow / 2.0, ox + ow):
            for mx in mine_x:
                d = cx - mx
                if abs(d) <= tol and (best_x is None or abs(d) < abs(best_x[0])):
                    best_x = (d, cx)
        for cy in (oy, oy + oh / 2.0, oy + oh):
            for my in mine_y:
                d = cy - my
                if abs(d) <= tol and (best_y is None or abs(d) < abs(best_y[0])):
                    best_y = (d, cy)
    lines = []
    if best_x:
        lines.append(("v", best_x[1]))
    if best_y:
        lines.append(("h", best_y[1]))
    return (best_x[0] if best_x else 0, best_y[0] if best_y else 0, lines)


# -- the ruler widgets --------------------------------------------------------------------
class Ruler(QWidget):
    """orient 'h' = along the top (drag down for a horizontal guide), 'v' = down the left side."""

    def __init__(self, win, orient):
        super().__init__()
        self.win, self.orient = win, orient
        self.pointer = None
        if orient == "h":
            self.setFixedHeight(SIZE)
        else:
            self.setFixedWidth(SIZE)
        self.setCursor(Qt.SplitVCursor if orient == "h" else Qt.SplitHCursor)
        self.setMouseTracking(True)

    def scene_range(self):
        v = self.win.view
        a = v.mapToScene(0, 0)
        b = v.mapToScene(v.viewport().width(), v.viewport().height())
        return (a.x(), b.x()) if self.orient == "h" else (a.y(), b.y())

    def to_screen(self, scene_pos):
        lo, _hi = self.scene_range()
        return (scene_pos - lo) * self.win.view.zoom

    def paintEvent(self, e):
        p = QPainter(self)
        p.fillRect(self.rect(), QColor("#eef1f5"))
        p.setPen(QColor("#b8c0cc"))
        if self.orient == "h":
            p.drawLine(0, SIZE - 1, self.width(), SIZE - 1)
        else:
            p.drawLine(SIZE - 1, 0, SIZE - 1, self.height())
        lo, hi = self.scene_range()
        zoom = self.win.view.zoom
        f = QFont()
        f.setPixelSize(9)
        p.setFont(f)
        for pos, major in ticks(lo, hi, zoom):
            s = self.to_screen(pos)
            ln = SIZE - 2 if major else (SIZE // 2 if (pos % (tick_steps(zoom)[1] * 5) == 0) else SIZE // 3)
            p.setPen(QColor("#5b6675" if major else "#9aa3ad"))
            if self.orient == "h":
                p.drawLine(QPointF(s, SIZE - 1), QPointF(s, SIZE - 1 - ln))
                if major:
                    p.drawText(QPointF(s + 2, 9), str(int(pos)))
            else:
                p.drawLine(QPointF(SIZE - 1, s), QPointF(SIZE - 1 - ln, s))
                if major:
                    p.save()
                    p.translate(9, s - 2)
                    p.rotate(-90)
                    p.drawText(QPointF(0, 0), str(int(pos)))
                    p.restore()
        # the guides of this page
        page = self.win.cur_page()
        axis = "h" if self.orient == "h" else "v"
        axis_key = "v" if self.orient == "h" else "h"
        p.setBrush(QColor("#00b7c3"))
        p.setPen(Qt.NoPen)
        for gpos in guides_of(page)[axis_key]:
            s = self.to_screen(gpos)
            if self.orient == "h":
                p.drawPolygon(QPolygonF([QPointF(s - 4, SIZE - 1), QPointF(s + 4, SIZE - 1), QPointF(s, SIZE - 7)]))
            else:
                p.drawPolygon(QPolygonF([QPointF(SIZE - 1, s - 4), QPointF(SIZE - 1, s + 4), QPointF(SIZE - 7, s)]))
        if self.pointer is not None:                 # where the mouse is over the page
            p.setPen(QPen(QColor("#e0413a"), 1))
            s = self.to_screen(self.pointer)
            if self.orient == "h":
                p.drawLine(QPointF(s, 0), QPointF(s, SIZE))
            else:
                p.drawLine(QPointF(0, s), QPointF(SIZE, s))

    # dragging a new guide out of the ruler
    def scene_point(self, e):
        v = self.win.view
        return v.mapToScene(v.viewport().mapFromGlobal(e.globalPos()))

    def mousePressEvent(self, e):
        if e.button() == Qt.LeftButton:
            axis = "h" if self.orient == "h" else "v"      # top ruler makes a horizontal guide
            pt = self.scene_point(e)
            self.win.guide_drag = dict(axis=axis, value=pt.y() if axis == "h" else pt.x(), old=None)
            self.win.scene.update()
            e.accept()

    def mouseMoveEvent(self, e):
        d = self.win.guide_drag
        if d is not None and d["old"] is None:
            pt = self.scene_point(e)
            d["value"] = pt.y() if d["axis"] == "h" else pt.x()
            self.win.scene.update()

    def mouseReleaseEvent(self, e):
        d = self.win.guide_drag
        if d is None or d["old"] is not None:
            return
        self.win.finish_guide_drag(self.win.view.viewport().rect().contains(
            self.win.view.viewport().mapFromGlobal(e.globalPos())))


class Corner(QLabel):
    def __init__(self):
        super().__init__("px")
        self.setFixedSize(SIZE, SIZE)
        self.setAlignment(Qt.AlignCenter)
        self.setStyleSheet("background:#eef1f5;color:#8a929c;font-size:8px;border-right:1px solid #b8c0cc;"
                           "border-bottom:1px solid #b8c0cc")


def build(win, view):
    """A widget holding the two rulers and the page view, in a grid."""
    box = QWidget()
    g = QGridLayout(box)
    g.setContentsMargins(0, 0, 0, 0)
    g.setSpacing(0)
    win.ruler_h, win.ruler_v, win.ruler_corner = Ruler(win, "h"), Ruler(win, "v"), Corner()
    g.addWidget(win.ruler_corner, 0, 0)
    g.addWidget(win.ruler_h, 0, 1)
    g.addWidget(win.ruler_v, 1, 0)
    g.addWidget(view, 1, 1)
    view.horizontalScrollBar().valueChanged.connect(win.ruler_h.update)
    view.verticalScrollBar().valueChanged.connect(win.ruler_v.update)
    return box


def show_rulers(win, on):
    for r in (win.ruler_h, win.ruler_v, win.ruler_corner):
        r.setVisible(on)
