"""Sitewright's own starter pictures. Every one is drawn here with plain shapes and
gradients, so there is nothing to license: backgrounds, textures, banners and icons."""
import math
import random

from PyQt5.QtCore import QBuffer, QByteArray, QIODevice, QPointF, Qt
from PyQt5.QtGui import (QBrush, QColor, QImage, QLinearGradient, QPainter, QPainterPath,
                         QPen, QPolygonF, QRadialGradient)

BG_W, BG_H = 1200, 800

GRADIENTS = [
    ("Morning sky", "#9fd3ff", "#e8f5ff"), ("Sunset", "#ff9a5a", "#7a3b8f"),
    ("Deep ocean", "#0f4c81", "#1fa2c9"), ("Forest", "#1f5b3a", "#7fc48a"),
    ("Slate", "#2b3440", "#5d6b7c"), ("Warm sand", "#f6e3c3", "#e0a96d"),
    ("Berry", "#6a1b5a", "#d65a8a"), ("Mint", "#d5f5e3", "#58c4a2"),
    ("Night", "#0b1026", "#2c3e8f"), ("Cloud", "#ffffff", "#dfe6ee"),
]
PATTERNS = ["dots", "stripes", "checks", "diagonal", "grid", "waves", "bricks", "speckle"]
ICONS = ["circle", "star", "heart", "arrow", "check", "cross", "quote", "bolt", "house", "leaf"]
BANNER_COLORS = [("Blue banner", "#1f64c0", "#4aa3ff"), ("Green banner", "#1f7a4d", "#7fd39d"),
                 ("Orange banner", "#d9661a", "#ffbf6b"), ("Purple banner", "#5a2d9c", "#b48cf0")]


def names():
    out = [("Backgrounds", n) for n, _, _ in GRADIENTS]
    out += [("Textures", p.title()) for p in PATTERNS]
    out += [("Banners", n) for n, _, _ in BANNER_COLORS]
    out += [("Icons", i.title()) for i in ICONS]
    return out


def _canvas(w, h, transparent=False):
    img = QImage(w, h, QImage.Format_ARGB32)
    img.fill(Qt.transparent if transparent else QColor("#ffffff"))
    p = QPainter(img)
    p.setRenderHint(QPainter.Antialiasing)
    return img, p


def _gradient(name):
    for n, a, b in GRADIENTS:
        if n == name:
            img, p = _canvas(BG_W, BG_H)
            g = QLinearGradient(0, 0, BG_W * 0.4, BG_H)
            g.setColorAt(0, QColor(a))
            g.setColorAt(1, QColor(b))
            p.fillRect(0, 0, BG_W, BG_H, QBrush(g))
            r = QRadialGradient(BG_W * 0.8, BG_H * 0.15, BG_W * 0.5)
            r.setColorAt(0, QColor(255, 255, 255, 70))
            r.setColorAt(1, QColor(255, 255, 255, 0))
            p.fillRect(0, 0, BG_W, BG_H, QBrush(r))
            p.end()
            return img


def _texture(kind):
    s = 128
    img, p = _canvas(s, s)
    base, ink = QColor("#f4f6f9"), QColor("#c8d0db")
    p.fillRect(0, 0, s, s, base)
    p.setPen(Qt.NoPen)
    p.setBrush(ink)
    pen = QPen(ink, 3)
    if kind == "dots":
        for x in (32, 96):
            for y in (32, 96):
                p.drawEllipse(QPointF(x, y), 7, 7)
    elif kind == "stripes":
        for x in range(0, s, 32):
            p.drawRect(x, 0, 16, s)
    elif kind == "checks":
        for i in range(4):
            for j in range(4):
                if (i + j) % 2 == 0:
                    p.drawRect(i * 32, j * 32, 32, 32)
    elif kind == "diagonal":
        p.setPen(pen)
        for k in range(-s, s * 2, 32):
            p.drawLine(k, s, k + s, 0)
    elif kind == "grid":
        p.setPen(QPen(ink, 2))
        for k in range(0, s, 32):
            p.drawLine(k, 0, k, s)
            p.drawLine(0, k, s, k)
    elif kind == "waves":
        p.setPen(QPen(ink, 3))
        for y in (24, 64, 104):
            path = QPainterPath(QPointF(0, y))
            for x in range(0, s, 32):
                path.cubicTo(x + 10, y - 14, x + 22, y + 14, x + 32, y)
            p.drawPath(path)
    elif kind == "bricks":
        p.setPen(QPen(ink, 2))
        for r, y in enumerate(range(0, s, 32)):
            p.drawLine(0, y, s, y)
            off = 0 if r % 2 == 0 else 32
            for x in range(off, s + 64, 64):
                p.drawLine(x, y, x, y + 32)
    else:
        rnd = random.Random(7)
        for _ in range(180):
            p.drawEllipse(QPointF(rnd.randint(0, s), rnd.randint(0, s)), 1.4, 1.4)
    p.end()
    return img


def _banner(name):
    for n, a, b in BANNER_COLORS:
        if n == name:
            w, h = 1000, 300
            img, p = _canvas(w, h)
            g = QLinearGradient(0, 0, w, 0)
            g.setColorAt(0, QColor(a))
            g.setColorAt(1, QColor(b))
            p.fillRect(0, 0, w, h, QBrush(g))
            p.setPen(Qt.NoPen)
            p.setBrush(QColor(255, 255, 255, 40))
            p.drawEllipse(QPointF(w * 0.85, h * 0.2), 190, 190)
            p.setBrush(QColor(255, 255, 255, 28))
            p.drawEllipse(QPointF(w * 0.1, h * 0.95), 150, 150)
            p.end()
            return img


def _icon(kind):
    s = 200
    img, p = _canvas(s, s, True)
    p.setPen(Qt.NoPen)
    p.setBrush(QColor("#2b7de9"))
    c = QPointF(s / 2, s / 2)
    if kind == "circle":
        p.drawEllipse(c, 80, 80)
    elif kind == "star":
        pts = []
        for i in range(10):
            r = 86 if i % 2 == 0 else 38
            a = -math.pi / 2 + i * math.pi / 5
            pts.append(QPointF(c.x() + r * math.cos(a), c.y() + r * math.sin(a)))
        p.setBrush(QColor("#f2b01e"))
        p.drawPolygon(QPolygonF(pts))
    elif kind == "heart":
        path = QPainterPath(QPointF(100, 175))
        path.cubicTo(-20, 80, 55, 5, 100, 60)
        path.cubicTo(145, 5, 220, 80, 100, 175)
        p.setBrush(QColor("#d64545"))
        p.drawPath(path)
    elif kind == "arrow":
        p.drawPolygon(QPolygonF([QPointF(20, 80), QPointF(110, 80), QPointF(110, 35),
                                 QPointF(185, 100), QPointF(110, 165), QPointF(110, 120),
                                 QPointF(20, 120)]))
    elif kind == "check":
        p.setBrush(QColor("#2e9e5b"))
        p.drawEllipse(c, 84, 84)
        p.setPen(QPen(QColor("white"), 16, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin))
        p.drawPolyline(QPolygonF([QPointF(58, 104), QPointF(88, 134), QPointF(144, 72)]))
    elif kind == "cross":
        p.setBrush(QColor("#d64545"))
        p.drawEllipse(c, 84, 84)
        p.setPen(QPen(QColor("white"), 16, Qt.SolidLine, Qt.RoundCap))
        p.drawLine(66, 66, 134, 134)
        p.drawLine(134, 66, 66, 134)
    elif kind == "quote":
        p.setBrush(QColor("#9aa3ad"))
        for x in (30, 112):
            p.drawEllipse(QPointF(x + 28, 80), 28, 28)
            p.drawPolygon(QPolygonF([QPointF(x, 90), QPointF(x + 56, 90), QPointF(x + 22, 150)]))
    elif kind == "bolt":
        p.setBrush(QColor("#f2b01e"))
        p.drawPolygon(QPolygonF([QPointF(115, 10), QPointF(45, 110), QPointF(95, 110),
                                 QPointF(80, 190), QPointF(160, 80), QPointF(108, 80)]))
    elif kind == "house":
        p.setBrush(QColor("#4b5868"))
        p.drawPolygon(QPolygonF([QPointF(100, 20), QPointF(185, 100), QPointF(15, 100)]))
        p.setBrush(QColor("#2b7de9"))
        p.drawRect(38, 100, 124, 80)
        p.setBrush(QColor("white"))
        p.drawRect(88, 130, 24, 50)
    else:
        path = QPainterPath(QPointF(40, 170))
        path.cubicTo(30, 70, 100, 20, 175, 25)
        path.cubicTo(180, 100, 140, 175, 40, 170)
        p.setBrush(QColor("#2e9e5b"))
        p.drawPath(path)
        p.setPen(QPen(QColor("white"), 5, Qt.SolidLine, Qt.RoundCap))
        p.drawLine(48, 162, 130, 78)
    p.end()
    return img


def make(group, name):
    """The picture as a QImage."""
    if group == "Backgrounds":
        return _gradient(name)
    if group == "Textures":
        return _texture(name.lower())
    if group == "Banners":
        return _banner(name)
    return _icon(name.lower())


def png_bytes(group, name):
    img = make(group, name)
    ba = QByteArray()
    buf = QBuffer(ba)
    buf.open(QIODevice.WriteOnly)
    img.save(buf, "PNG")
    return bytes(ba)
