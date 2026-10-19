#!/usr/bin/env python3
"""Draws the Sitewright icon (a web page with a star) at every size into ../icons/."""
import math
import os
import sys

from PyQt5.QtCore import QPointF, QRectF, Qt
from PyQt5.QtGui import QColor, QImage, QPainter, QPainterPath, QPolygonF

NAVY, RED, WHITE = QColor("#0a2a5e"), QColor("#c8102e"), QColor("#ffffff")
SIZES = (16, 22, 24, 32, 48, 64, 128, 256, 512)


def star(cx, cy, r):
    pts = []
    for i in range(10):
        a = -math.pi / 2 + i * math.pi / 5
        rad = r if i % 2 == 0 else r * 0.42
        pts.append(QPointF(cx + rad * math.cos(a), cy + rad * math.sin(a)))
    return pts


def draw(p, s):
    k = s / 256.0
    p.setRenderHint(QPainter.Antialiasing)
    p.scale(k, k)
    p.setPen(Qt.NoPen)
    p.setBrush(NAVY)
    p.drawRoundedRect(QRectF(8, 8, 240, 240), 52, 52)
    # the page
    page = QRectF(48, 40, 160, 176)
    p.setBrush(WHITE)
    p.drawRoundedRect(page, 14, 14)
    # red header band with a white line through it (flag stripes)
    clip = QPainterPath()
    clip.addRoundedRect(page, 14, 14)
    p.save()
    p.setClipPath(clip)
    p.setBrush(RED)
    p.drawRect(QRectF(page.left(), page.top(), page.width(), 44))
    p.setBrush(WHITE)
    p.drawRect(QRectF(page.left(), page.top() + 17, page.width(), 8))
    p.restore()
    # the star
    p.setBrush(NAVY)
    p.drawPolygon(QPolygonF(star(128, 144, 46)))
    # text lines
    p.setBrush(QColor("#b9c4d6"))
    p.drawRoundedRect(QRectF(70, 190, 116, 9), 4, 4)


def svg():
    pts = " ".join("%.1f,%.1f" % (pt.x(), pt.y()) for pt in star(128, 144, 46))
    return f"""<svg xmlns="http://www.w3.org/2000/svg" width="256" height="256" viewBox="0 0 256 256">
<rect x="8" y="8" width="240" height="240" rx="52" fill="#0a2a5e"/>
<clipPath id="pg"><rect x="48" y="40" width="160" height="176" rx="14"/></clipPath>
<rect x="48" y="40" width="160" height="176" rx="14" fill="#ffffff"/>
<g clip-path="url(#pg)"><rect x="48" y="40" width="160" height="44" fill="#c8102e"/>
<rect x="48" y="57" width="160" height="8" fill="#ffffff"/></g>
<polygon points="{pts}" fill="#0a2a5e"/>
<rect x="70" y="190" width="116" height="9" rx="4" fill="#b9c4d6"/>
</svg>
"""


def main(out):
    os.makedirs(out, exist_ok=True)
    for s in SIZES:
        img = QImage(s, s, QImage.Format_ARGB32)
        img.fill(Qt.transparent)
        p = QPainter(img)
        draw(p, s)
        p.end()
        img.save(os.path.join(out, "sitewright-%d.png" % s))
    with open(os.path.join(out, "sitewright.svg"), "w") as f:
        f.write(svg())


if __name__ == "__main__":
    here = os.path.dirname(os.path.abspath(__file__))
    main(sys.argv[1] if len(sys.argv) > 1 else os.path.join(here, "..", "icons"))
