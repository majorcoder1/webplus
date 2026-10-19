"""Pictures of the SEO and Form Designer dialogs: python3 tests/screens8.py prefix"""
import os, sys
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))
from PyQt5.QtWidgets import QApplication
from sitewright import dialogs
from sitewright.model import Document
from sitewright.window import apply_ui_font, saved_ui_pt
app = QApplication([])
apply_ui_font(saved_ui_pt())
doc = Document()
doc.pages[0]["description"] = "Family-run bakery in Crossville serving fresh bread, pastries and custom cakes every morning."
doc.pages[0]["title"] = "Crossville Bakery"
d = dialogs.SeoDialog(None, doc, doc.pages[0]); d.show(); app.processEvents()
d.grab().save(sys.argv[1] + "-seo.png")
f = dialogs.FormDesigner(None, doc); f.show(); app.processEvents()
f.grab().save(sys.argv[1] + "-form.png")
os._exit(0)
