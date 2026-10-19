"""Form tab order/lock, frame properties, variables, default settings, pop-up menu. Must print ALL GOOD."""
import os
import sys
import tempfile

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from PyQt5.QtWidgets import QApplication, QInputDialog

from sitewright import export, formtools as ft
from sitewright.model import Document, new_item
from sitewright.window import MainWindow

app = QApplication([])
os.environ["WEBSITE_DEFAULTS"] = os.path.join(tempfile.mkdtemp(), "defaults.json")
w = MainWindow()
w._sel_guard = True
page = w.cur_page()
a = new_item("field", 40, 40, ftype="text", name="a")
b = new_item("field", 40, 100, ftype="text", name="b")
page["items"] += [a, b]
b["tab"], a["tab"] = 1, 2
out = tempfile.mkdtemp()
export.export_site(w.doc, out)
html = open(os.path.join(out, "index.html")).read()
import re
assert re.search(r'tabindex="1"[^>]*name="b"|name="b"[^>]*tabindex="1"', html), html[-1500:]

ft.lock_form(w, True)
assert a["group"] == b["group"] and a["group"].startswith("form-")
ft.lock_form(w, False)
assert not a["group"] and not b["group"]

img = new_item("image", 10, 200, asset="")
img["asset"] = "x"
page["items"].append(img)
img.update(bw=3, bcolor="#ff0000", radius=8)
w.doc.assets["x"] = dict(name="x.png", data="")
export.export_site(w.doc, out)
assert "border:3px solid #ff0000" in open(os.path.join(out, "index.html")).read()

# defaults
w.doc.width = 1100
w.doc.user = dict(name="Zed")
ft.save_defaults(w)
d = Document()
assert d.width == 960
assert ft.apply_defaults(d) and d.width == 1100 and d.user["name"] == "Zed"

# site address
QInputDialog.getText = staticmethod(lambda *x, **k: ("https://example.org", True))
import PyQt5.QtGui as g
opened = []
ft.QDesktopServices.openUrl = staticmethod(lambda u: opened.append(u.toString()))
w.doc.seo["site_url"] = ""
ft.view_online(w)
assert opened == ["https://example.org"] and w.doc.seo["site_url"] == "https://example.org"
print("ALL GOOD")
