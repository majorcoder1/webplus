"""Database Merge: records, repeating area expansion, CSV, photo database, export. Must print ALL GOOD."""
import glob
import os
import sys
import tempfile

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from PyQt5.QtGui import QColor, QImage
from PyQt5.QtWidgets import QApplication

from sitewright import databasemerge as dm, export
from sitewright.model import Document, new_item

app = QApplication([])

# CSV round trip
fields, rows = dm.from_csv("Name,Unit Price\nApple,3\nPear,10\nFig,2\n")
assert fields == ["Name", "Unit_Price"] and len(rows) == 3
db = dm.new_database("Fruit", fields)
db["rows"] = rows
assert dm.from_csv(dm.to_csv(db))[1] == rows
assert [r["Name"] for r in dm.sorted_rows(db, "Unit_Price")] == ["Fig", "Apple", "Pear"]       # numbers sort as numbers
assert [r["Name"] for r in dm.sorted_rows(db, "Unit_Price", True, 2)] == ["Pear", "Apple"]

doc = Document()
doc.databases.append(db)
page = doc.pages[0]
page["h"] = 500
rep = new_item("repeater", 40, 100, db=db["id"], cols=2, gap=10)
rep["w"], rep["h"] = 200, 60
t = new_item("text", 48, 108, text="{{Name}}: ${{Unit_Price}}", link="http://x/{{Name}}")
t["w"], t["h"] = 180, 30
t["rep"] = rep["id"]
below = new_item("text", 40, 300, text="Footer")
page["items"] += [below, rep, t]
items, page2 = dm.expand(doc, page, page["items"])
texts = [i["text"] for i in items if i["kind"] == "text"]
assert texts.count("Footer") == 1
assert [x for x in texts if ":" in x] == ["Apple: $3", "Pear: $10", "Fig: $2"], texts
# 3 records, 2 across = 2 rows: height grows by (60+10)
foot = next(i for i in items if i["text"] == "Footer")
assert foot["y"] == 370 and page2["h"] == 570, (foot["y"], page2["h"])
assert not any(i["kind"] == "repeater" for i in items)
pear = next(i for i in items if i["text"].startswith("Pear"))
assert pear["x"] == 48 + 210 and pear["y"] == 108 and pear["link"] == "http://x/Pear"
fig = next(i for i in items if i["text"].startswith("Fig"))
assert fig["x"] == 48 and fig["y"] == 108 + 70
assert len({i["id"] for i in items}) == len(items)
assert page["h"] == 500 and len(page["items"]) == 3          # the design itself is untouched

# photo database + picture field
folder = tempfile.mkdtemp()
for n, c in (("red_one.png", "#ff0000"), ("blue-two.png", "#0000ff")):
    im = QImage(20, 20, QImage.Format_RGB32)
    im.fill(QColor(c))
    im.save(os.path.join(folder, n))
open(os.path.join(folder, "notes.txt"), "w").write("x")
pdb = dm.photo_database(doc, folder, "Pics")
assert [r["name"] for r in pdb["rows"]] == ["blue two", "red one"] and all(r["photo"] in doc.assets for r in pdb["rows"])
doc.databases.append(pdb)
page["items"] = []
rp = new_item("repeater", 0, 0, db=pdb["id"])
rp["w"], rp["h"] = 100, 100
img = new_item("image", 0, 0, asset="", field="photo")
img["w"], img["h"] = 100, 100
img["rep"] = rp["id"]
cap = new_item("text", 0, 80, text="{{caption}}")
cap["rep"] = rp["id"]
page["items"] += [rp, img, cap]
out = tempfile.mkdtemp()
export.export_site(doc, out)
html = open(os.path.join(out, "index.html")).read()
assert html.count("images/blue-two.png") >= 1 and html.count("images/red_one.png") >= 1, html[:2000]
assert "blue two" in html and "red one" in html
assert "{{" not in html

# save / load / undo snapshot keep the databases
p = os.path.join(out, "x.site")
doc.save(p)
assert len(Document.load(p).databases) == 2
d2 = Document()
d2.restore(doc.snapshot())
assert len(d2.databases) == 2

# URL pictures
db3 = dm.new_database("U", ["pic"])
db3["rows"] = [dict(pic="https://example.com/a.jpg")]
doc.databases.append(db3)
page["items"] = []
r3 = new_item("repeater", 0, 0, db=db3["id"])
i3 = new_item("image", 0, 0, asset="", field="pic")
i3["rep"] = r3["id"]
page["items"] += [r3, i3]
export.export_site(doc, out)
assert 'src="https://example.com/a.jpg"' in open(os.path.join(out, "index.html")).read()
print("ALL GOOD")

# the menu commands
from PyQt5.QtWidgets import QInputDialog
from sitewright import dbdialogs
from sitewright.window import MainWindow
w = MainWindow()
w._sel_guard = True
w.doc.databases.append(dm.new_database("Shop", ["name", "price"]))
w.doc.databases[0]["rows"] = [dict(name="Hat", price="5")]
dbdialogs.insert_repeating_area(w)
assert len(dbdialogs.repeaters(w)) == 1
QInputDialog.getItem = staticmethod(lambda *a, **k: ("name", True))
dbdialogs.insert_field(w)
dbdialogs.insert_field(w, True)
its = w.cur_page()["items"]
assert sum(1 for i in its if i.get("rep")) == 2
dm_items, _ = dm.expand(w.doc, w.cur_page(), its)
assert any(i["kind"] == "text" and i["text"] == "Hat" for i in dm_items)
print("ALL GOOD")

# the editor shows the other records; PDF and picture show them all, merged
import subprocess
from sitewright.canvas import ItemObj
w2 = MainWindow()
w2._sel_guard = True
dbx = dm.new_database("Pets", ["name"])
dbx["rows"] = [dict(name=n) for n in ("Rex", "Tom", "Fido", "Kit")]
w2.doc.databases.append(dbx)
pg = w2.cur_page()
pg["h"] = 600
rp = new_item("repeater", 40, 40, db=dbx["id"], cols=1, gap=10)
rp["w"], rp["h"] = 200, 40
tx = new_item("text", 44, 44, text="Pet: {{name}}")
tx["w"], tx["h"] = 180, 30
tx["rep"] = rp["id"]
tail = new_item("text", 40, 300, text="TAILEND")
pg["items"] += [rp, tx, tail]
w2.reload()
texts = lambda: sorted(o.d["text"] for o in w2.scene.items() if isinstance(o, ItemObj) and o.d["kind"] == "text")
assert texts() == ["Pet: Fido", "Pet: Kit", "Pet: Tom", "Pet: {{name}}", "TAILEND"], texts()
ghost = next(o for o in w2.scene.items() if isinstance(o, ItemObj) and not o.editable and "Tom" in o.d["text"])
assert ghost.d["y"] == 44 + 50 and not ghost.flags() & ghost.ItemIsSelectable
w2.records_action.setChecked(False)
w2.toggle_records()
assert texts() == ["Pet: {{name}}", "TAILEND"]
w2.records_action.setChecked(True)
w2.toggle_records()
from sitewright import outputs
pdf = os.path.join(tempfile.mkdtemp(), "m.pdf")
outputs.write_pdf(w2, pdf)
txt = subprocess.run(["pdftotext", pdf, "-"], capture_output=True, text=True).stdout
for n in ("Rex", "Tom", "Fido", "Kit", "TAILEND"):
    assert n in txt, (n, txt)
assert "{{" not in txt
assert pg["h"] == 600 and len(pg["items"]) == 3          # the design was put back
print("ALL GOOD")
