"""Slider Studio and main window pictures: python3 tests/screens9.py prefix"""
import os, sys
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))
from PyQt5.QtGui import QColor, QImage
from PyQt5.QtWidgets import QApplication
from sitewright import dialogs
from sitewright.model import Document, new_item
from sitewright.window import apply_ui_font, saved_ui_pt
app = QApplication([])
apply_ui_font(saved_ui_pt())
doc = Document()
sl = new_item("slider", 0, 0)
d = dialogs.SliderStudio(None, doc, sl)
d.show(); app.processEvents()
d.grab().save(sys.argv[1] + "-slider.png")
os._exit(0)
