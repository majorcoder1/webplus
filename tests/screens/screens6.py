"""Pictures of the Task Monitor layout and the publish window."""
import os, sys
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))
from PyQt5.QtCore import QRectF
from PyQt5.QtWidgets import QApplication
from sitewright import publish
from sitewright.model import new_item
from sitewright.window import MainWindow, apply_ui_font, saved_ui_pt
app = QApplication([])
apply_ui_font(saved_ui_pt())
w = MainWindow(); w.resize(1360, 860); w.show(); app.processEvents()
w.insert_block("Call to action"); w.insert_block("Three columns")
w.target_list().append(new_item("image", 500, 40))
w.reload(); w.refresh_tasks(); app.processEvents(); w.fit_page(); app.processEvents()
w.grab().save(sys.argv[1])
d = publish.FileOperationDialog(w, publish.Target("ftp.example.com", 21, "u", "", "/public_html"), "/tmp")
d.on_progress(15, 98, "wpimages/wp1b35153d_06.png", 400, 1024, 150000, 1200000)
d.left.setText("Time remaining: 11 Min, 7 Sec")
d.show(); app.processEvents()
d.grab().save(sys.argv[2])
os._exit(0)
