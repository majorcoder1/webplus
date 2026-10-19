"""Pictures of the Startup Assistant pages: python3 tests/screens7.py outprefix"""
import os, sys
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))
from PyQt5.QtWidgets import QApplication
from sitewright import startup
from sitewright.window import apply_ui_font, saved_ui_pt
app = QApplication([])
apply_ui_font(saved_ui_pt())
d = startup.StartupDialog(None, [])
d.show(); app.processEvents()
for i, name in ((0, "home"), (3, "new"), (4, "templates")):
    d.show_page(i); app.processEvents()
    d.grab().save("%s-%s.png" % (sys.argv[1], name))
os._exit(0)
