"""Picture of the button and navigation galleries: python3 tests/screens4.py out.png"""
import os, sys
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))
from PyQt5.QtCore import QRectF
from PyQt5.QtGui import QColor, QPainter, QPixmap
from PyQt5.QtWidgets import QApplication
from sitewright.styles import BUTTON_STYLES, NAV_STYLES, preview_button, preview_nav
app = QApplication([])
cols, bw, bh = 5, 160, 56
names = list(BUTTON_STYLES)
rows = (len(names) + cols - 1) // cols
nav_h = sum(preview_nav(p).height() + 8 for p in NAV_STYLES.values())
W = cols * bw + 20
img = QPixmap(W * 2 + 30, max(rows * (bh + 20) + 40, nav_h + 40))
img.fill(QColor("#f3f5f8"))
p = QPainter(img)
p.setPen(QColor("#334155"))
p.drawText(10, 20, "Button gallery (30 styles)")
for i, n in enumerate(names):
    p.drawPixmap(10 + (i % cols) * bw, 30 + (i // cols) * (bh + 20), preview_button(BUTTON_STYLES[n], n.split()[-1].title(), bw - 6, bh))
    p.setPen(QColor("#667085"))
    p.drawText(14 + (i % cols) * bw, 30 + (i // cols) * (bh + 20) + bh + 12, n)
x0, y = W + 20, 30
p.setPen(QColor("#334155"))
p.drawText(x0, 20, "Navigation gallery (10 styles)")
for n, props in NAV_STYLES.items():
    pm = preview_nav(props, W - 10)
    p.drawPixmap(x0, y, pm)
    y += pm.height() + 8
p.end()
img.save(sys.argv[1] if len(sys.argv) > 1 else "gallery.png")
