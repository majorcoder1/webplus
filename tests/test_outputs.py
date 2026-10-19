"""Publish as PDF, Export as picture, Export as widget. Must print ALL GOOD."""
import os
import subprocess
import sys
import tempfile

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from PyQt5.QtGui import QColor, QImage
from PyQt5.QtWidgets import QApplication

from sitewright import outputs
from sitewright.canvas import ItemObj
from sitewright.model import new_item, new_page
from sitewright.window import MainWindow

app = QApplication([])
w = MainWindow()
w.doc.site_title = "Test Site"
w._sel_guard = True


def add(page, text, x, y, fill=None):
    it = new_item("text", x, y)
    it.update(w=300, h=80, text=text)
    if fill:
        it["fill"] = fill
    page["items"].append(it)
    return it


add(w.doc.pages[0], "First page words", 40, 40)
w.doc.pages[0]["h"] = 400
p2 = new_page("Second")
p2["h"] = 600
w.doc.pages.append(p2)
r = add(p2, "Second page words", 40, 40, "#ff0000")
w.reload()
d = tempfile.mkdtemp()

pdf = os.path.join(d, "t.pdf")
assert outputs.write_pdf(w, pdf) == 2
info = subprocess.run(["pdfinfo", pdf], capture_output=True, text=True).stdout
assert "Pages:           2" in info, info
txt = subprocess.run(["pdftotext", pdf, "-"], capture_output=True, text=True).stdout
assert "First page words" in txt and "Second page words" in txt, txt
assert w.page_index == 0

# picture of the whole page
w.page_index = 1
w.reload()
img = outputs.picture_image(w, False, 1, False)
assert img.width() == w.doc.width and img.height() == 600
# selection only, see-through
for o in w.scene.items():
    if isinstance(o, ItemObj) and o.editable and o.d["id"] == r["id"]:
        o.setSelected(True)
img = outputs.picture_image(w, True, 2, True)
assert img.width() == 600 and img.height() == 160, (img.width(), img.height())
assert QColor(img.pixel(2, 2)).red() > 200
assert not w.scene.printing

# widget
for o in w.scene.items():
    if isinstance(o, ItemObj) and o.editable and o.d["id"] == r["id"]:
        o.setSelected(True)
doc2, ww, hh = outputs.widget_document(w, w.selected())
assert (ww, hh) == (300, 80) and len(doc2.pages) == 1
from sitewright import export
tmp = tempfile.mkdtemp()
export.export_site(doc2, tmp, optimise=False, preview=True)
html = outputs.inline_site(tmp)
assert "Second page words" in html and 'href="style.css"' not in html and "<style>" in html
print("ALL GOOD")

# links in the PDF click
w3 = MainWindow()
w3._sel_guard = True
w3.doc.pages.append(new_page("Second"))
pa, pb = w3.doc.pages
pa["h"], pb["h"] = 400, 400
for text, link, x, y in (("WEB", "https://example.com/x?a=1&b=(2)", 40, 40), ("MAIL", "mailto:me@example.com", 40, 100),
                         ("GOSECOND", "page:" + pb["id"], 40, 160), ("NOLINK", "", 40, 220), ("TOG", "toggle:abc", 40, 280)):
    it = new_item("text", x, y, text=text, link=link)
    it.update(w=200, h=40)
    pa["items"].append(it)
nav = new_item("navbar", 300, 40)
nav.update(w=400, h=50)
pa["items"].append(nav)
rot = new_item("text", 500, 200, text="ROT", link="https://rot.example.com")
rot.update(w=100, h=40, rot=90)
pa["items"].append(rot)
w3.reload()
pdf2 = os.path.join(tempfile.mkdtemp(), "links.pdf")
outputs.write_pdf(w3, pdf2)
xml = subprocess.run(["pdftohtml", "-xml", "-stdout", "-i", pdf2], capture_output=True, text=True).stdout
assert 'href="https://example.com/x?a=1&amp;b=%282%29"' in xml or "example.com/x?a=1" in xml, xml[:1500]
assert "mailto:me@example.com" in xml
assert xml.count("<a href") >= 5, xml.count("<a href")          # web, mail, go-second, two nav entries, rotated
assert "https://rot.example.com" in xml
assert subprocess.run(["pdfinfo", pdf2], capture_output=True, text=True).stdout.count("Pages:           2") == 1
assert subprocess.run(["mutool", "info", pdf2], capture_output=True).returncode == 0
assert "TOG" in subprocess.run(["pdftotext", pdf2, "-"], capture_output=True, text=True).stdout
print("ALL GOOD")
