"""The design surface: page items, selection handles, drawing tools."""
import json
from PyQt5.QtCore import QPointF, QRectF, Qt
from PyQt5.QtGui import (QBrush, QColor, QFont, QLinearGradient, QPainter, QPainterPath,
                         QPen, QPolygonF, QTransform)
from PyQt5.QtWidgets import (QGraphicsItem, QGraphicsRectItem, QGraphicsScene,
                             QGraphicsView)

from .extras import EXTRA_KINDS, paint_extra
from .styles import paint_button, paint_nav

HANDLE = 8          # handle size in pixels
GRID = 10
CURSORS = [Qt.SizeFDiagCursor, Qt.SizeVerCursor, Qt.SizeBDiagCursor,
           Qt.SizeHorCursor, Qt.SizeFDiagCursor, Qt.SizeVerCursor,
           Qt.SizeBDiagCursor, Qt.SizeHorCursor]


def snap(v, on):
    return round(v / GRID) * GRID if on else v


def qcolor(c, default="#000000"):
    return QColor(c or default)


from . import imagefx  # noqa: E402


class ItemObj(QGraphicsItem):
    def __init__(self, d, win, editable=True):
        super().__init__()
        self.d, self.win, self.editable = d, win, editable
        self._resize = None
        self._dragging = False
        self.setPos(d["x"], d["y"])
        if editable:
            self.setFlags(QGraphicsItem.ItemIsSelectable |
                          QGraphicsItem.ItemSendsGeometryChanges)
            self.setFlag(QGraphicsItem.ItemIsMovable, not d.get("locked"))
            self.setAcceptHoverEvents(True)
        else:
            self.setAcceptedMouseButtons(Qt.NoButton)
            self.setOpacity(0.55 if win.master_mode else 1.0)
        self.setOpacity(self.opacity() * d.get("opacity", 100) / 100)

    # -- geometry --------------------------------------------------------
    def rect(self):
        return QRectF(0, 0, max(self.d["w"], 1), max(self.d["h"], 1))

    def xform(self):
        r = self.rect()
        t = QTransform()
        t.translate(r.center().x(), r.center().y())
        t.rotate(self.d.get("rot", 0))
        t.scale(-1 if self.d.get("fx") else 1, -1 if self.d.get("fy") else 1)
        t.translate(-r.center().x(), -r.center().y())
        return t

    def boundingRect(self):
        m = HANDLE + 2 + imagefx.pad_for(self.d.get("effects"))
        r = self.rect()
        if self.d.get("kind") == "text" and self.d.get("overflow") == "visible":
            from . import textlayout
            r.setHeight(max(r.height(), textlayout.text_height(self.d)))     # words may spill below
        if self.d.get("kind") == "shape":
            from .extras import shape_nodes_of
            from . import shapes
            r = r.united(shapes.qpath(shape_nodes_of(self.d), True, self.d["w"], self.d["h"]).controlPointRect())
        if self.d.get("kind") == "popup":
            from .extras import popup_rect
            r = r.united(popup_rect(self.d))                 # room to show the pop-up preview
        if self.d.get("rot"):
            r = r.united(self.xform().mapRect(r))
        return r.adjusted(-m, -m, m, m)

    def shape(self):
        p = QPainterPath()
        r = self.rect()
        if self.d["kind"] == "line":
            r = r.adjusted(0, -4, 0, 4) if r.height() < 8 else r
        if self.isSelected() and not self.d.get("locked"):
            r = r.adjusted(-HANDLE / 2, -HANDLE / 2, HANDLE / 2, HANDLE / 2)
        p.addPolygon(self.xform().map(QPolygonF(r)))
        p.closeSubpath()
        return p

    def sync(self):
        self.prepareGeometryChange()
        self.setPos(self.d["x"], self.d["y"])
        if self.editable:
            self.setFlag(QGraphicsItem.ItemIsMovable, not self.d.get("locked"))
        base = 0.55 if (not self.editable and self.win.master_mode) else 1.0
        self.setOpacity(base * self.d.get("opacity", 100) / 100)
        self.setVisible(not (self.d.get("hidden") and not getattr(self.win, "show_hidden", True)))
        self.update()

    def handle_rects(self):
        r, h = self.rect(), HANDLE
        xs = [r.left(), r.center().x(), r.right()]
        ys = [r.top(), r.center().y(), r.bottom()]
        pts = [(0, 0), (1, 0), (2, 0), (2, 1), (2, 2), (1, 2), (0, 2), (0, 1)]
        return [QRectF(xs[a] - h / 2, ys[b] - h / 2, h, h) for a, b in pts]

    def handle_at(self, pos):
        if (not self.isSelected() or len(self.scene().selectedItems()) != 1
                or self.d.get("locked")):
            return -1
        for i, hr in enumerate(self.handle_rects()):
            if hr.adjusted(-2, -2, 2, 2).contains(pos):
                return i
        return -1

    # -- painting --------------------------------------------------------
    def paint(self, p, opt, widget=None):
        r = self.rect()
        p.setRenderHint(QPainter.Antialiasing)
        p.save()
        if self.d.get("rot") or self.d.get("fx") or self.d.get("fy"):
            p.setTransform(self.xform(), True)
        if self.d.get("effects") and imagefx.fx_active(self.d["effects"]) and imagefx.have_pil():
            key = (json.dumps({k: v for k, v in self.d.items() if k not in ("x", "y")}, sort_keys=True, default=str),
                   self.isSelected(), self.win.gif_frame(self.d.get("asset")) if self.d["kind"] == "image" else -1)
            if getattr(self, "_fxcache", (None,))[0] != key:     # the Pillow work is only redone when something changed
                img, pad = imagefx.render_with_fx(
                    lambda q: self.paint_content(q, QRectF(0, 0, r.width(), r.height())),
                    r.width(), r.height(), self.d["effects"])
                self._fxcache = (key, img, pad)
            _k, img, pad = self._fxcache
            p.drawImage(QPointF(-pad, -pad), img)
        else:
            self.paint_content(p, r)
        p.restore()
        if self.editable and self.isSelected() and not self.scene().printing:
            p.setBrush(Qt.NoBrush)
            p.setPen(QPen(QColor("#1e90ff" if not self.d.get("locked") else "#d9822b"),
                          1, Qt.DashLine))
            p.drawRect(r)
            if len(self.scene().selectedItems()) == 1 and not self.d.get("locked"):
                p.setPen(QPen(QColor("#1e90ff"), 1))
                p.setBrush(QColor("white"))
                for hr in self.handle_rects():
                    p.drawRect(hr)

    def paint_content(self, p, r):
        d = self.d
        kind = d["kind"]
        fill = QBrush(QColor(d["fill"])) if d.get("fill") else Qt.NoBrush
        if d.get("fill2") and d.get("fill") and kind in ("rect", "ellipse", "text"):
            g = QLinearGradient(r.topLeft(), r.bottomLeft())
            g.setColorAt(0, QColor(d["fill"]))
            g.setColorAt(1, QColor(d["fill2"]))
            fill = QBrush(g)
        sw = d.get("sw", 0) if d.get("stroke") else 0
        pen = QPen(QColor(d["stroke"]), sw) if sw else Qt.NoPen
        if sw and d.get("sstyle") in ("dashed", "dotted"):
            pen.setStyle(Qt.DashLine if d["sstyle"] == "dashed" else Qt.DotLine)
        if d.get("shadow") and kind in ("rect", "ellipse", "text"):
            p.setPen(Qt.NoPen)
            p.setBrush(QColor(0, 0, 0, 70))
            sh = r.translated(0, 3)
            if kind == "ellipse":
                p.drawEllipse(sh)
            else:
                p.drawRoundedRect(sh, d.get("radius", 0), d.get("radius", 0))
        if kind == "line":
            p.setPen(QPen(qcolor(d.get("stroke"), "#333333"), max(d.get("sw", 2), 1)))
            p.drawLine(r.topLeft(), QPointF(d["w"], d["h"]))
        elif kind == "ellipse":
            p.setBrush(fill)
            p.setPen(pen)
            p.drawEllipse(r)
        elif kind == "image":
            self.paint_image(p, r)
        elif kind == "navbar":
            from .model import nav_entries
            cur = self.win.cur_page()
            paint_nav(p, r, d, nav_entries(self.win.doc), "page:" + cur["id"])
        elif kind == "button":
            paint_button(p, r, d)
        elif kind in EXTRA_KINDS:
            p.save()
            if kind not in ("popup", "shape"):   # a pop-up preview and a curve being edited show outside
                p.setClipRect(r)
            paint_extra(p, r, d, self.win)
            p.restore()
        else:
            p.setBrush(fill)
            p.setPen(pen)
            if d.get("radius"):
                p.drawRoundedRect(r, d["radius"], d["radius"])
            else:
                p.drawRect(r)
            if kind in ("text", "button"):
                self.paint_text(p, r)

    def paint_text(self, p, r):
        from . import textlayout
        textlayout.paint(p, r, self.d)

    def paint_image(self, p, r):
        d = self.d
        pm = self.win.gif_pixmap(d.get("asset")) or self.win.pixmap(d.get("asset"))
        if imagefx.is_derived(self.win.doc, d) and imagefx.have_pil():
            pm = self.win.derived_pixmap(d) or pm
        p.save()
        if d.get("cropshape"):
            from . import shapes
            nodes, closed = shapes.shape_nodes(d["cropshape"])
            p.setClipPath(shapes.qpath(nodes, closed, r.width(), r.height()).translated(r.left(), r.top()))
        elif d.get("radius"):
            path = QPainterPath()
            path.addRoundedRect(r, d["radius"], d["radius"])
            p.setClipPath(path)
        if pm is None or pm.isNull():
            p.fillRect(r, QColor("#eef1f5"))
            p.setPen(QPen(QColor("#9aa3ad"), 1, Qt.DashLine))
            p.drawRect(r.adjusted(.5, .5, -.5, -.5))
            p.setPen(QColor("#6b7686"))
            f = QFont()
            f.setPixelSize(max(min(int(r.height() / 6), 16), 9))
            p.setFont(f)
            p.drawText(r.adjusted(8, 8, -8, -8), int(Qt.AlignCenter | Qt.TextWordWrap),
                       "Picture frame\nDouble-click to choose a picture")
        else:
            fit = d.get("fit", "cover")
            if fit == "fill":
                p.drawPixmap(r, pm, QRectF(pm.rect()))
            else:
                k = (max if fit == "cover" else min)(r.width() / pm.width(),
                                                    r.height() / pm.height())
                w, h = pm.width() * k, pm.height() * k
                tgt = QRectF(r.center().x() - w / 2, r.center().y() - h / 2, w, h)
                p.setClipRect(r, Qt.IntersectClip)
                p.drawPixmap(tgt, pm, QRectF(pm.rect()))
        p.restore()
        if d.get("bw"):
            p.save()
            p.setBrush(Qt.NoBrush)
            pen = QPen(QColor(d.get("bcolor") or "#000000"), d["bw"])
            pen.setJoinStyle(Qt.RoundJoin)
            p.setPen(pen)
            if d.get("cropshape"):                       # the border follows the shape
                from . import shapes
                nodes, closed = shapes.shape_nodes(d["cropshape"])
                p.drawPath(shapes.qpath(nodes, closed, r.width(), r.height()).translated(r.left(), r.top()))
            else:
                half = d["bw"] / 2.0
                rr = r.adjusted(half, half, -half, -half)
                p.drawRoundedRect(rr, d.get("radius", 0), d.get("radius", 0))
            p.restore()

    # -- interaction -----------------------------------------------------
    def itemChange(self, change, value):
        if change == QGraphicsItem.ItemPositionChange and self.scene() is not None:
            if self._dragging:
                nx, ny = self.win.snap_x(value.x()), self.win.snap_y(value.y())
                win = self.win
                sel = [o for o in self.scene().selectedItems() if isinstance(o, ItemObj)]
                if win.dynamic_snap and len(sel) == 1:           # line up with the other objects
                    from . import rulers
                    others = [(o.d["x"], o.d["y"], o.d["w"], o.d["h"]) for o in self.scene().items()
                              if isinstance(o, ItemObj) and o.editable and o is not self]
                    tol = 6 / max(win.view.zoom, 0.1)
                    dx, dy, lines = rulers.dynamic_snap((nx, ny, self.d["w"], self.d["h"]), others, tol)
                    nx, ny = nx + dx, ny + dy
                    win.dyn_lines = lines
                    self.scene().update()
                return QPointF(nx, ny)
        if change == QGraphicsItem.ItemPositionHasChanged and self.editable:
            self.d["x"], self.d["y"] = round(value.x()), round(value.y())
            self.win.item_moved(self)
        if change == QGraphicsItem.ItemSelectedHasChanged:
            self.update()
        return super().itemChange(change, value)

    def hoverEnterEvent(self, e):
        if self.d.get("kind") == "popup":
            self.win.popup_preview = self.d          # show where the pop-up will appear
            self.update()
        super().hoverEnterEvent(e)

    def hoverLeaveEvent(self, e):
        if self.d.get("kind") == "popup":
            self.win.popup_preview = None
            self.update()
        super().hoverLeaveEvent(e)

    def hoverMoveEvent(self, e):
        i = self.handle_at(e.pos())
        self.setCursor(CURSORS[i] if i >= 0 else Qt.ArrowCursor)
        super().hoverMoveEvent(e)

    def mousePressEvent(self, e):
        i = self.handle_at(e.pos()) if e.button() == Qt.LeftButton else -1
        if i >= 0:
            d = self.d
            self._resize = (i, e.scenePos(), d["x"], d["y"], d["w"], d["h"])
            e.accept()
            return
        if (e.button() == Qt.LeftButton and self.editable and self.d["kind"] == "table"
                and self.isSelected() and not (e.modifiers() & Qt.ControlModifier)):
            self.pick_cell(e.pos(), bool(e.modifiers() & Qt.ShiftModifier))
        self._dragging = e.button() == Qt.LeftButton
        super().mousePressEvent(e)

    def cell_at(self, pos):
        """(row, column) of the table cell under a point in this object's own coordinates."""
        import bisect
        from . import tablecore as tc
        d = self.d
        xs = tc.edges(d, d["w"], max(d["cols"], 1), "colw")
        ys = tc.edges(d, d["h"], max(d["rows"], 1), "rowh")
        c = min(max(bisect.bisect_right(xs, pos.x()) - 1, 0), max(d["cols"], 1) - 1)
        r = min(max(bisect.bisect_right(ys, pos.y()) - 1, 0), max(d["rows"], 1) - 1)
        return r, c

    def pick_cell(self, pos, extend):
        """Choose the cell under the mouse for the Table menu tools (Shift adds a range)."""
        import bisect
        from . import tablecore as tc
        d = self.d
        xs = tc.edges(d, d["w"], max(d["cols"], 1), "colw")
        ys = tc.edges(d, d["h"], max(d["rows"], 1), "rowh")
        c = min(max(bisect.bisect_right(xs, pos.x()) - 1, 0), max(d["cols"], 1) - 1)
        r = min(max(bisect.bisect_right(ys, pos.y()) - 1, 0), max(d["rows"], 1) - 1)
        if extend:
            s = tc.clamp_sel(d)
            d["sel"] = [s[0], s[1], r, c]
        else:
            d["sel"] = [r, c, r, c]
        tc.clamp_sel(d)
        self.update()
        self.win.props.refresh_cell_range()

    def mouseMoveEvent(self, e):
        if self._resize is None:
            super().mouseMoveEvent(e)
            return
        i, p0, x, y, w, h = self._resize
        dx, dy = e.scenePos().x() - p0.x(), e.scenePos().y() - p0.y()
        l, t, r, b = x, y, x + w, y + h
        if i in (0, 6, 7):
            l = self.win.snap_x(x + dx)
        if i in (2, 3, 4):
            r = self.win.snap_x(x + w + dx)
        if i in (0, 1, 2):
            t = self.win.snap_y(y + dy)
        if i in (4, 5, 6):
            b = self.win.snap_y(y + h + dy)
        if r - l < 4:
            l, r = (r - 4, r) if i in (0, 6, 7) else (l, l + 4)
        if b - t < 4:
            t, b = (b - 4, b) if i in (0, 1, 2) else (t, t + 4)
        self.prepareGeometryChange()
        self.d.update(x=round(l), y=round(t), w=round(r - l), h=round(b - t))
        from . import textlayout
        if textlayout.grows(self.d):
            # the box follows its text: a top handle keeps the bottom edge, the rest keep the top
            bottom = self.d["y"] + self.d["h"]
            textlayout.fit_height(self.d)
            if i in (0, 1, 2):
                self.d["y"] = round(bottom - self.d["h"])
        self.setPos(self.d["x"], self.d["y"])
        self.update()
        self.win.item_moved(self)

    def mouseReleaseEvent(self, e):
        self._resize = None
        self._dragging = False
        super().mouseReleaseEvent(e)

    def mouseDoubleClickEvent(self, e):
        if self.editable and self.d["kind"] == "shape":
            self.win.nodes.start(self.d)                    # a drawn shape: edit its points
        elif self.editable and self.d["kind"] == "image" and not self.d.get("asset"):
            from . import pageitems
            pageitems.fill_frame(self.win, self.d)      # an empty frame asks for its picture
        elif self.editable and self.d["kind"] not in ("text", "button", "marquee", "arttext"):
            self.win.show_properties()      # tables, pictures and the rest open their dialog
        else:
            self.win.edit_text()


class SiteScene(QGraphicsScene):
    def __init__(self, win):
        super().__init__()
        self.win = win
        self.printing = False             # true while a PDF or picture is being drawn

    def drawBackground(self, p, rect):
        d = self.win.doc
        page = self.win.cur_page()
        bg = QColor(page.get("bg", "#ffffff"))
        if self.printing:
            return
        p.fillRect(rect, bg)                    # the colour runs edge to edge, as on the web
        r = QRectF(0, 0, d.width, page["h"])
        edge = QColor(0, 0, 0, 70) if bg.lightness() > 110 else QColor(255, 255, 255, 90)
        p.setPen(QPen(edge, 0, Qt.DashLine))    # marks the design area only
        p.drawLine(QPointF(0, rect.top()), QPointF(0, rect.bottom()))
        p.drawLine(QPointF(d.width, rect.top()), QPointF(d.width, rect.bottom()))
        p.drawLine(QPointF(rect.left(), page["h"]), QPointF(rect.right(), page["h"]))
        if page.get("type") == "html":
            p.setPen(QColor("#5b6675"))
            f = QFont()
            f.setPixelSize(20)
            p.setFont(f)
            p.drawText(QRectF(40, 60, d.width - 80, 160), int(Qt.AlignHCenter | Qt.AlignTop | Qt.TextWordWrap),
                       "This is an HTML page.\n\nIts content is code, so there is nothing to drag around here.\n"
                       "Double-click anywhere, or use Tools > Site Manager > HTML Page Properties, to edit it.")
        if self.win.grid_on:
            p.setPen(QPen(QColor(0, 0, 0, 28) if bg.lightness() > 110
                          else QColor(255, 255, 255, 40), 0))
            x = 0
            while x <= r.width():
                p.drawLine(QPointF(x, 0), QPointF(x, r.height()))
                x += GRID * 4
            y = 0
            while y <= r.height():
                p.drawLine(QPointF(0, y), QPointF(r.width(), y))
                y += GRID * 4


    def drawForeground(self, p, rect):
        if self.printing:
            return
        g = self.win.cur_page().get("guides") or {}
        d, page = self.win.doc, self.win.cur_page()
        p.setPen(QPen(QColor("#00b7c3"), 0))
        for x in g.get("v", []):
            p.drawLine(QPointF(x, -80), QPointF(x, page["h"] + 80))
        for y in g.get("h", []):
            p.drawLine(QPointF(-80, y), QPointF(d.width + 80, y))
        gd = self.win.guide_drag
        if gd is not None:                                   # the guide being dragged
            p.setPen(QPen(QColor("#ff8c00"), 0))
            if gd["axis"] == "v":
                p.drawLine(QPointF(gd["value"], -80), QPointF(gd["value"], page["h"] + 80))
            else:
                p.drawLine(QPointF(-80, gd["value"]), QPointF(d.width + 80, gd["value"]))
        self.win.pen.paint(p)
        self.win.nodes.paint(p)
        p.setPen(QPen(QColor("#e0178a"), 0, Qt.DashLine))    # dynamic guides while moving an object
        for axis, pos in self.win.dyn_lines:
            if axis == "v":
                p.drawLine(QPointF(pos, -80), QPointF(pos, page["h"] + 80))
            else:
                p.drawLine(QPointF(-80, pos), QPointF(d.width + 80, pos))


class SiteView(QGraphicsView):
    def __init__(self, scene, win):
        super().__init__(scene)
        self.win = win
        self.setRenderHint(QPainter.Antialiasing)
        self.setRenderHint(QPainter.SmoothPixmapTransform)
        self.setDragMode(QGraphicsView.RubberBandDrag)
        self.setTransformationAnchor(QGraphicsView.AnchorUnderMouse)
        self.setViewportUpdateMode(QGraphicsView.FullViewportUpdate)
        self.setFrameShape(QGraphicsView.NoFrame)
        self._start = None
        self._rb = None
        self.zoom = 1.0

    def mouseDoubleClickEvent(self, e):
        page = self.win.cur_page()
        if self.win.tool == "pen":
            self.win.pen.double_click(e)
            return
        if page.get("type") == "html" and not self.itemAt(e.pos()):
            self.win.html_page_properties_for(page)
            return
        super().mouseDoubleClickEvent(e)

    def contextMenuEvent(self, e):
        """Right-click: the object menu on an object, the page menu on empty page."""
        if self.win.nodes.active or self.win.tool == "pen":
            return
        item = self.itemAt(e.pos())
        while item is not None and not isinstance(item, ItemObj):
            item = item.parentItem()
        self.win.canvas_menu(e.globalPos(), item, self.mapToScene(e.pos()))
        e.accept()

    def set_zoom(self, z):
        self.zoom = max(0.1, min(4.0, z))
        self.resetTransform()
        self.scale(self.zoom, self.zoom)
        self.win.zoom_changed(self.zoom)

    def wheelEvent(self, e):
        if e.modifiers() & Qt.ControlModifier:
            self.set_zoom(self.zoom * (1.15 if e.angleDelta().y() > 0 else 1 / 1.15))
        else:
            super().wheelEvent(e)

    def guide_at(self, e):
        from . import rulers
        pt = self.mapToScene(e.pos())
        return rulers.nearest_guide(self.win.cur_page(), pt.x(), pt.y(), 5 / max(self.zoom, 0.1))

    def mousePressEvent(self, e):
        if self.win.tool == "pen":
            self.win.pen.press(e)
            e.accept()
            return
        if self.win.nodes.active and self.win.nodes.press(e):
            e.accept()
            return
        if (self.win.tool == "select" and e.button() == Qt.LeftButton and not self.itemAt(e.pos())
                and self.guide_at(e)):                       # pick up a guide line to move it
            axis, value = self.guide_at(e)
            self.win.guide_drag = dict(axis=axis, value=value, old=value)
            self.win.scene.update()
            e.accept()
            return
        if self.win.tool != "select" and e.button() == Qt.LeftButton:
            self._start = self.mapToScene(e.pos())
            self._rb = QGraphicsRectItem()
            self._rb.setPen(QPen(QColor("#1e90ff"), 1, Qt.DashLine))
            self.scene().addItem(self._rb)
            e.accept()
            return
        super().mousePressEvent(e)

    def _drag_rect(self, e):
        a, b = self._start, self.mapToScene(e.pos())
        sx, sy = self.win.snap_x, self.win.snap_y
        return QRectF(QPointF(sx(min(a.x(), b.x())), sy(min(a.y(), b.y()))),
                      QPointF(sx(max(a.x(), b.x())), sy(max(a.y(), b.y()))))

    def mouseMoveEvent(self, e):
        pt = self.mapToScene(e.pos())
        self.win.show_coords(pt)
        if self.win.tool == "pen":
            self.win.pen.move(e)
            return
        if self.win.nodes.active and self.win.nodes.move(e):
            return
        for r, v in ((self.win.ruler_h, pt.x()), (self.win.ruler_v, pt.y())):
            r.pointer = v
            r.update()
        gd = self.win.guide_drag
        if gd is not None and gd["old"] is not None:         # moving a guide
            gd["value"] = pt.x() if gd["axis"] == "v" else pt.y()
            self.win.scene.update()
            return
        if self.win.tool == "select" and not self.itemAt(e.pos()) and not e.buttons():
            g = self.guide_at(e)
            self.viewport().setCursor(Qt.ArrowCursor if not g else (Qt.SplitHCursor if g[0] == "v" else Qt.SplitVCursor))
        if self._start is not None:
            self._rb.setRect(self._drag_rect(e))
            return
        super().mouseMoveEvent(e)

    def mouseReleaseEvent(self, e):
        if self.win.tool == "pen":
            self.win.pen.release(e)
            return
        if self.win.nodes.active and self.win.nodes.release(e):
            return
        gd = self.win.guide_drag
        if gd is not None and gd["old"] is not None:         # a guide put down (or dragged off the page)
            pt = self.mapToScene(e.pos())
            vp = self.viewport().rect()
            inside = vp.contains(e.pos())
            self.win.finish_guide_drag(inside)
            return
        if self.win.dyn_lines:
            self.win.dyn_lines = []
            self.scene().update()
        if self._start is not None:
            r = self._drag_rect(e)
            self.scene().removeItem(self._rb)
            self._rb, self._start = None, None
            self.win.create_item(self.win.tool, r)
            return
        super().mouseReleaseEvent(e)
        self.win.commit_if_changed()

    def keyPressEvent(self, e):
        if self.win.tool == "pen" and self.win.pen.key(e):
            return
        if self.win.nodes.active and self.win.nodes.key(e):
            return
        step = 10 if e.modifiers() & Qt.ShiftModifier else 1
        d = {Qt.Key_Left: (-step, 0), Qt.Key_Right: (step, 0),
             Qt.Key_Up: (0, -step), Qt.Key_Down: (0, step)}.get(e.key())
        if d and self.scene().selectedItems():
            self.win.nudge(*d)
            return
        super().keyPressEvent(e)
