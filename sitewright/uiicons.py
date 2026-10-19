"""Small drawn icons for the toolbar buttons (original artwork, drawn in code)."""
import math

from PyQt5.QtCore import QPointF, QRectF, Qt
from PyQt5.QtGui import QColor, QIcon, QPainter, QPainterPath, QPen, QPixmap, QPolygonF

INK = QColor("#2f3b4c")
BLUE = QColor("#2b7de9")
RED = QColor("#d64545")
GREEN = QColor("#2e9e5b")
AMBER = QColor("#e8a33d")
PAPER = QColor("#ffffff")
GREY = QColor("#aab4c3")


def _page(p, x=5, y=3, w=14, h=18, fold=True):
    path = QPainterPath()
    path.moveTo(x, y)
    path.lineTo(x + w - (5 if fold else 0), y)
    if fold:
        path.lineTo(x + w, y + 5)
    path.lineTo(x + w, y + h)
    path.lineTo(x, y + h)
    path.closeSubpath()
    p.setBrush(PAPER)
    p.setPen(QPen(INK, 1.4))
    p.drawPath(path)
    if fold:
        p.drawLine(QPointF(x + w - 5, y), QPointF(x + w - 5, y + 5))
        p.drawLine(QPointF(x + w - 5, y + 5), QPointF(x + w, y + 5))


def _arrow(p, a, b, color=INK, width=1.8):
    p.setPen(QPen(color, width, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin))
    p.drawLine(a, b)
    ang = math.atan2(b.y() - a.y(), b.x() - a.x())
    for d in (2.5, -2.5):
        p.drawLine(b, QPointF(b.x() - 5 * math.cos(ang + d / 5),
                              b.y() - 5 * math.sin(ang + d / 5)))


def draw(p, name):
    p.setRenderHint(QPainter.Antialiasing)
    pen = QPen(INK, 1.5, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin)
    p.setPen(pen)
    p.setBrush(Qt.NoBrush)
    if name == "new":
        _page(p)
        p.setPen(QPen(BLUE, 2))
        p.drawLine(QPointF(12, 9), QPointF(12, 17))
        p.drawLine(QPointF(8, 13), QPointF(16, 13))
    elif name == "open":
        p.setBrush(AMBER)
        path = QPainterPath()
        path.moveTo(3, 7); path.lineTo(9, 7); path.lineTo(11, 9); path.lineTo(20, 9)
        path.lineTo(20, 19); path.lineTo(3, 19); path.closeSubpath()
        p.drawPath(path)
    elif name == "save":
        p.setBrush(BLUE)
        p.drawRoundedRect(QRectF(4, 4, 16, 16), 2, 2)
        p.setBrush(PAPER)
        p.drawRect(QRectF(7, 4, 10, 6))
        p.drawRect(QRectF(7, 13, 10, 7))
    elif name == "cut":
        p.drawLine(QPointF(8, 4), QPointF(15, 14))
        p.drawLine(QPointF(16, 4), QPointF(9, 14))
        p.setBrush(PAPER)
        p.drawEllipse(QPointF(8, 17), 3, 3)
        p.drawEllipse(QPointF(16, 17), 3, 3)
    elif name == "copy":
        _page(p, 4, 3, 11, 14, fold=False)
        _page(p, 9, 8, 11, 14, fold=False)
    elif name == "paste":
        p.setBrush(AMBER)
        p.drawRoundedRect(QRectF(4, 5, 16, 16), 2, 2)
        p.setBrush(GREY)
        p.drawRoundedRect(QRectF(8, 3, 8, 4), 1.5, 1.5)
        p.setBrush(PAPER)
        p.drawRect(QRectF(7, 10, 10, 9))
    elif name in ("undo", "redo"):
        sign = 1 if name == "undo" else -1
        cx = 12
        path = QPainterPath()
        path.moveTo(cx - sign * 6, 10)
        path.cubicTo(cx - sign * 2, 4, cx + sign * 7, 6, cx + sign * 7, 14)
        p.setPen(QPen(INK, 2, Qt.SolidLine, Qt.RoundCap))
        p.drawPath(path)
        p.setBrush(INK)
        p.drawPolygon(QPolygonF([QPointF(cx - sign * 9, 10.5), QPointF(cx - sign * 3, 5.5),
                                 QPointF(cx - sign * 3, 15)]))
    elif name in ("front", "back"):
        top = name == "front"
        p.setBrush(GREY if top else BLUE)
        p.drawRect(QRectF(4, 4 if top else 8, 11, 11))
        p.setBrush(BLUE if top else GREY)
        p.drawRect(QRectF(9, 9 if top else 5, 11, 11))
    elif name == "group":
        p.setPen(QPen(INK, 1.3, Qt.DashLine))
        p.drawRect(QRectF(3, 3, 18, 18))
        p.setPen(QPen(INK, 1.5))
        p.setBrush(BLUE)
        p.drawRect(QRectF(6, 6, 6, 6))
        p.setBrush(AMBER)
        p.drawRect(QRectF(12, 12, 6, 6))
    elif name.startswith("align"):
        side = name.split("-")[1]
        p.setPen(QPen(INK, 1.8, Qt.SolidLine, Qt.RoundCap))
        ws = (14, 9, 12)
        for i, w in enumerate(ws):
            y = 6 + i * 6
            if side == "left":
                x0 = 4
            elif side == "right":
                x0 = 20 - w
            else:
                x0 = 12 - w / 2
            p.drawLine(QPointF(x0, y), QPointF(x0 + w, y))
    elif name in ("fill", "line", "text"):
        if name == "fill":
            p.setBrush(QColor("#7fb5f5"))
            p.drawRoundedRect(QRectF(5, 4, 14, 12), 2, 2)
        elif name == "line":
            p.setPen(QPen(INK, 2.4, Qt.SolidLine, Qt.RoundCap))
            p.drawLine(QPointF(5, 14), QPointF(19, 6))
        else:
            p.setPen(QPen(INK, 2.2, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin))
            p.drawLine(QPointF(7, 17), QPointF(12, 5))
            p.drawLine(QPointF(12, 5), QPointF(17, 17))
            p.drawLine(QPointF(9, 13), QPointF(15, 13))
        p.setPen(Qt.NoPen)
        p.setBrush(RED if name == "fill" else (BLUE if name == "line" else GREEN))
        p.drawRect(QRectF(4, 19, 16, 3))
    elif name == "page-properties":
        _page(p)
        p.setPen(QPen(GREY, 1.5))
        for y in (11, 14, 17):
            p.drawLine(QPointF(8, y), QPointF(16, y))
    elif name == "site-properties":
        p.setBrush(PAPER)
        p.drawRoundedRect(QRectF(3, 5, 18, 14), 2, 2)
        p.drawLine(QPointF(3, 9), QPointF(21, 9))
        p.setBrush(BLUE)
        p.drawEllipse(QPointF(12, 14), 3, 3)
    elif name == "site-structure":
        p.setBrush(BLUE)
        p.drawRect(QRectF(9, 3, 6, 5))
        p.setBrush(PAPER)
        for x in (3, 9, 15):
            p.drawRect(QRectF(x, 16, 6, 5))
        p.drawLine(QPointF(12, 8), QPointF(12, 12))
        p.drawLine(QPointF(6, 12), QPointF(18, 12))
        for x in (6, 12, 18):
            p.drawLine(QPointF(x, 12), QPointF(x, 16))
    elif name == "site-manager":
        for i, c in enumerate((BLUE, GREEN, AMBER)):
            p.setBrush(c)
            p.drawRoundedRect(QRectF(4, 4 + i * 6, 16, 4.5), 1.5, 1.5)
    elif name == "colour-scheme":
        for (x, y), c in zip(((8, 8), (16, 8), (8, 16), (16, 16)),
                             (RED, AMBER, GREEN, BLUE)):
            p.setBrush(c)
            p.setPen(Qt.NoPen)
            p.drawEllipse(QPointF(x, y), 4.2, 4.2)
    elif name == "user":
        p.setBrush(GREY)
        p.drawEllipse(QPointF(12, 8), 4, 4)
        p.setBrush(BLUE)
        path = QPainterPath()
        path.moveTo(4, 21); path.cubicTo(4, 13, 20, 13, 20, 21); path.closeSubpath()
        p.drawPath(path)
    elif name == "options":
        p.setPen(QPen(INK, 1.6, Qt.SolidLine, Qt.RoundCap))
        for i, x in enumerate((8, 15, 11)):
            y = 6 + i * 6
            p.drawLine(QPointF(4, y), QPointF(20, y))
            p.setBrush(BLUE)
            p.drawEllipse(QPointF(x, y), 2.6, 2.6)
    elif name == "fit":
        p.setPen(QPen(INK, 1.8, Qt.SolidLine, Qt.RoundCap))
        for sx, sy in ((1, 1), (-1, 1), (1, -1), (-1, -1)):
            cx, cy = 12 - sx * 8, 12 - sy * 8
            p.drawLine(QPointF(cx, cy), QPointF(cx + sx * 5, cy))
            p.drawLine(QPointF(cx, cy), QPointF(cx, cy + sy * 5))
    elif name == "preview":
        path = QPainterPath()
        path.moveTo(2, 12); path.quadTo(12, 3, 22, 12); path.quadTo(12, 21, 2, 12)
        p.setBrush(PAPER)
        p.drawPath(path)
        p.setBrush(BLUE)
        p.drawEllipse(QPointF(12, 12), 3.5, 3.5)
    elif name == "publish":
        p.setBrush(QColor("#cfe0f7"))
        path = QPainterPath()
        path.moveTo(6, 17); path.cubicTo(1, 17, 1, 9, 7, 10)
        path.cubicTo(8, 4, 17, 4, 18, 10); path.cubicTo(24, 9, 24, 17, 18, 17)
        path.closeSubpath()
        p.drawPath(path)
        _arrow(p, QPointF(12, 21), QPointF(12, 11), BLUE, 2)
    else:
        p.drawRect(QRectF(5, 5, 14, 14))


def ui_icon(name, size=22):
    scale = 2
    pm = QPixmap(size * scale, size * scale)
    pm.fill(Qt.transparent)
    p = QPainter(pm)
    p.scale(size * scale / 24.0, size * scale / 24.0)
    draw(p, name)
    p.end()
    pm.setDevicePixelRatio(scale)
    return QIcon(pm)
