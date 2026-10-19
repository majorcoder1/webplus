"""Picture of the themes: python3 tests/screens5.py out.png"""
import os, sys
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))
from PyQt5.QtGui import QColor, QPainter, QPixmap
from PyQt5.QtWidgets import QApplication
from sitewright.schemes import THEMES, preview_theme
app = QApplication([])
n = len(THEMES)
img = QPixmap(2 * 330 + 20, ((n + 1) // 2) * 88 + 30)
img.fill(QColor("#e9edf2"))
p = QPainter(img)
p.setPen(QColor("#334155"))
p.drawText(10, 18, "Site themes")
for i, name in enumerate(THEMES):
    p.drawPixmap(10 + (i % 2) * 330, 26 + (i // 2) * 88, preview_theme(name))
p.end()
img.save(sys.argv[1] if len(sys.argv) > 1 else "themes.png")
