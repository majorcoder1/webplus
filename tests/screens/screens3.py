"""Screenshot of the Phase 3 objects: python3 tests/screens3.py out.png"""
import os, sys
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))
from PyQt5.QtCore import QRectF
from PyQt5.QtWidgets import QApplication
from sitewright.window import MainWindow
app = QApplication([])
w = MainWindow(); w.resize(1360, 860); w.show(); app.processEvents()
for k, r in (("table", (30, 30, 420, 130)), ("video", (30, 190, 300, 170)),
             ("map", (350, 190, 300, 170)), ("social", (30, 390, 220, 44)),
             ("marquee", (280, 395, 370, 36)), ("audio", (30, 460, 320, 48)),
             ("field:text", (30, 540, 280, 36)), ("field:select", (30, 590, 280, 36)),
             ("field:checkbox", (30, 640, 280, 28)), ("field:submit", (330, 640, 140, 42)),
             ("field:textarea", (330, 540, 320, 90)), ("html", (480, 390, 170, 100))):
    w.create_item(k, QRectF(*r))
d = {i["kind"]: i for i in w.cur_page()["items"]}
d["video"]["url"] = "https://youtu.be/dQw4w9WgXcQ"
d["map"]["address"] = "Crossville, Tennessee"
d["marquee"]["text"] = "Grand opening this Saturday!"
w.cur_page()["h"] = 720
w.doc.width = 700
w.reload(); app.processEvents(); w.fit_page(); app.processEvents()
w.scene.clearSelection()
w.grab().save(sys.argv[1] if len(sys.argv) > 1 else "screen3.png")
