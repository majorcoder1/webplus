"""Save a screenshot of the window with a sample site: python3 tests/screens.py out.png"""
import os, sys
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))
from PyQt5.QtCore import QRectF
from PyQt5.QtWidgets import QApplication
from sitewright.model import new_item
from sitewright.window import MainWindow
app = QApplication([])
from sitewright.window import apply_ui_font, saved_ui_pt
apply_ui_font(saved_ui_pt())
w = MainWindow(); w.resize(1360, 860); w.show()
app.processEvents()
w.doc.pages[0]["name"] = "Home"
w.add_page(template="About")
w.add_page(template="Contact")
w.page_index = 0
w.reload()
w.master_btn.setChecked(True)
w.target_list().append(new_item("navbar", 0, 0, w=960, h=48))
w.master_btn.setChecked(False)
from sitewright.templates import build
items, h = build("Landing page", w.doc.width)
for i in items:
    i["y"] += 60
w.cur_page()["items"][:] = items
w.cur_page()["h"] = h + 60
w.reload()
app.processEvents()
w.fit_page()
w.scene.items()
sel = [o for o in w.scene.items() if getattr(o, "editable", False) and o.d["kind"] == "button"]
if sel:
    sel[0].setSelected(True)
app.processEvents()
if os.environ.get("FLOAT"):
    w.toolbox_dock.setFloating(True)
    w.toolbox_dock.move(w.x() + 520, w.y() + 330)
    app.processEvents()
w.grab().save(sys.argv[1] if len(sys.argv) > 1 else "screen.png")
