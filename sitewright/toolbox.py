"""Toolbox: tool list and the small icons drawn for each tool."""
from PyQt5.QtCore import QPointF, QRectF, Qt
from PyQt5.QtGui import QColor, QFont, QIcon, QPainter, QPainterPath, QPen, QPixmap, QPolygonF

# (key, tooltip, shortcut)
TOOLS = [("select", "Pointer", "V"), ("text", "Text frame", "T"),
         ("image", "Picture", "P"), ("rect", "Rectangle", "R"),
         ("ellipse", "Ellipse", "E"), ("line", "Line", "L"),
         ("button", "Button", "B"), ("navbar", "Navigation bar", "N"),
         ("table", "Table", ""), ("gallery", "Photo gallery", ""),
         ("video", "Video", ""), ("map", "Map", ""),
         ("audio", "Audio player", ""), ("field:text", "Form field", ""),
         ("social", "Social buttons", ""), ("marquee", "Scrolling message", ""),
         ("html", "HTML fragment", ""), ("arttext", "Artistic text", ""), ("hotspot", "Hotspot", ""), ("pen", "Pen (draw curves)", "Shift+P")]

INK = QColor("#334155")
ACC = QColor("#2b7de9")


def tool_icon(key, size=28):
    pm = QPixmap(size, size)
    pm.fill(Qt.transparent)
    p = QPainter(pm)
    p.setRenderHint(QPainter.Antialiasing)
    p.setPen(QPen(INK, 1.6))
    p.setBrush(Qt.NoBrush)
    s = size
    if key == "select":
        p.setBrush(INK)
        p.drawPolygon(QPolygonF([QPointF(8, 4), QPointF(8, 22), QPointF(13, 17.5),
                                 QPointF(16.5, 25), QPointF(19, 24), QPointF(15.5, 16.5),
                                 QPointF(22, 16)]))
    elif key == "text":
        f = QFont("Serif")
        f.setPixelSize(22)
        f.setBold(True)
        p.setFont(f)
        p.drawText(QRectF(0, 0, s, s), int(Qt.AlignCenter), "T")
    elif key == "image":
        p.drawRect(QRectF(4, 6, 20, 16))
        p.setBrush(INK)
        p.drawPolygon(QPolygonF([QPointF(6, 21), QPointF(12, 12), QPointF(16, 17),
                                 QPointF(19, 14), QPointF(23, 21)]))
        p.drawEllipse(QPointF(19, 10), 2, 2)
    elif key == "pen":
        path = QPainterPath()
        path.moveTo(5, 22)
        path.cubicTo(6, 8, 15, 4, 20, 12)
        p.drawPath(path)
        p.setBrush(INK)
        p.drawPolygon(QPolygonF([QPointF(18, 15), QPointF(24, 6), QPointF(26, 8), QPointF(20, 18)]))
    elif key == "rect":
        p.setBrush(QColor("#cfe0f7"))
        p.drawRoundedRect(QRectF(4, 7, 20, 14), 2, 2)
    elif key == "ellipse":
        p.setBrush(QColor("#fde3c4"))
        p.drawEllipse(QRectF(4, 5, 20, 18))
    elif key == "line":
        p.drawLine(QPointF(5, 23), QPointF(23, 5))
    elif key == "button":
        p.setBrush(ACC)
        p.setPen(Qt.NoPen)
        p.drawRoundedRect(QRectF(3, 8, 22, 12), 5, 5)
        p.setPen(QPen(QColor("white"), 1.6))
        p.drawLine(QPointF(9, 14), QPointF(19, 14))
    elif key == "navbar":
        p.setBrush(QColor("#1f3a5f"))
        p.setPen(Qt.NoPen)
        p.drawRoundedRect(QRectF(2, 8, 24, 12), 2, 2)
        p.setBrush(QColor("white"))
        for x in (6, 12, 18):
            p.drawRect(QRectF(x, 12.5, 4, 3))
    elif key == "table":
        p.drawRect(QRectF(4, 5, 20, 18))
        p.drawLine(QPointF(4, 11), QPointF(24, 11))
        p.drawLine(QPointF(4, 17), QPointF(24, 17))
        p.drawLine(QPointF(11, 5), QPointF(11, 23))
        p.drawLine(QPointF(18, 5), QPointF(18, 23))
    elif key == "gallery":
        p.setBrush(QColor("#cfe0f7"))
        for x, y in ((4, 4), (15, 4), (4, 15), (15, 15)):
            p.drawRect(QRectF(x, y, 9, 9))
    elif key == "video":
        p.drawRoundedRect(QRectF(3, 6, 22, 16), 3, 3)
        p.setBrush(INK)
        p.drawPolygon(QPolygonF([QPointF(11, 10), QPointF(11, 18), QPointF(18, 14)]))
    elif key == "map":
        p.setBrush(QColor("#d9453d"))
        p.setPen(Qt.NoPen)
        p.drawEllipse(QPointF(14, 11), 7, 7)
        p.drawPolygon(QPolygonF([QPointF(8, 15), QPointF(20, 15), QPointF(14, 25)]))
        p.setBrush(QColor("white"))
        p.drawEllipse(QPointF(14, 11), 2.5, 2.5)
    elif key == "audio":
        p.drawRoundedRect(QRectF(2, 8, 24, 12), 6, 6)
        p.setBrush(ACC)
        p.setPen(Qt.NoPen)
        p.drawEllipse(QPointF(8.5, 14), 3.5, 3.5)
        p.setPen(QPen(INK, 1.6))
        p.drawLine(QPointF(14, 14), QPointF(23, 14))
    elif key.startswith("field"):
        p.drawRoundedRect(QRectF(3, 8, 22, 12), 2, 2)
        p.drawLine(QPointF(8, 11), QPointF(8, 17))
    elif key == "social":
        p.setPen(Qt.NoPen)
        for x, c in ((8, "#3b5998"), (14, "#111111"), (20, "#c8232c")):
            p.setBrush(QColor(c))
            p.drawEllipse(QPointF(x, 14), 4, 4)
    elif key == "marquee":
        p.drawRect(QRectF(3, 8, 22, 12))
        p.drawLine(QPointF(7, 14), QPointF(21, 14))
        p.drawLine(QPointF(7, 14), QPointF(10, 11))
        p.drawLine(QPointF(7, 14), QPointF(10, 17))
    elif key == "hotspot":
        p.setBrush(QColor(43, 125, 233, 80))
        p.setPen(QPen(QColor("#2b7de9"), 1.5, Qt.DashLine))
        p.drawEllipse(QRectF(4, 6, 20, 16))
        p.setPen(QPen(QColor("#1f3a5f"), 1.5))
        p.drawLine(QPointF(14, 14), QPointF(21, 23))
        p.drawLine(QPointF(14, 14), QPointF(14, 23))
    elif key == "arttext":
        f = QFont("Sans Serif")
        f.setPixelSize(15)
        f.setBold(True)
        p.setFont(f)
        pth = QPainterPath(QPointF(3, 20))
        pth.quadTo(QPointF(14, 4), QPointF(25, 20))
        for i, ch in enumerate("Aa"):
            t = 0.28 + i * 0.42
            pt = pth.pointAtPercent(t)
            p.save()
            p.translate(pt)
            p.rotate(-pth.angleAtPercent(t))
            p.drawText(QPointF(-5, 0), ch)
            p.restore()
    elif key == "html":
        f = QFont("Monospace")
        f.setPixelSize(13)
        f.setBold(True)
        p.setFont(f)
        p.drawText(QRectF(0, 0, s, s), int(Qt.AlignCenter), "</>")
    p.end()
    return QIcon(pm)
