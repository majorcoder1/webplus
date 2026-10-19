"""Text > Insert: date, page and site info, variables, placeholder text; tokens fill in on export.
Must print ALL GOOD."""
import datetime
import os
import sys

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from PyQt5.QtCore import QRectF
from PyQt5.QtWidgets import QApplication

from sitewright import export, insertinfo
from sitewright.canvas import ItemObj
from sitewright.model import new_item, new_page
from sitewright.window import MainWindow

app = QApplication([])
w = MainWindow()
w.show()
doc = w.doc
doc.site_title = "Garden Club"
doc.pages.append(new_page("About us"))
doc.user = {"company": "Garden Club LLC", "phone": "555-0100"}

# token values
now = datetime.datetime.now()
v = export.token_values(doc, doc.pages[1])
assert v["sitename"] == "Garden Club" and v["pagename"] == "About us" and v["pagenumber"] == "2"
assert v["pagecount"] == "2" and v["year"] == str(now.year) and v["sitepages"] == "2"
assert v["companyname"] == "Garden Club LLC" and v["companyphone"] == "555-0100"
assert v["date"].endswith(str(now.year)) and ":" in v["time"] and v["time24"].count(":") == 1
assert v["isodate"] == now.strftime("%Y-%m-%d")
assert export.replace_tokens("Page %pagenumber% of %pagecount% - %year%", v) == "Page 2 of 2 - %d" % now.year

# a text box with tokens is filled in on the published page, also inside a table
w.create_item("text", QRectF(20, 20, 300, 60))
t = [o for o in w.scene.items() if isinstance(o, ItemObj) and o.editable][0]
t.setSelected(True)
w.set_prop("text", "Welcome to %sitename% on %date%. Call %companyphone%.")
doc.pages[0]["items"].append(new_item("table", 0, 200))
doc.pages[0]["items"][-1]["cells"][1][0] = "%pagename% / %year%"
w.reload()
html_ = export.page_source(doc, doc.pages[0]["id"], False)
assert "Welcome to Garden Club on %s" % v["date"] in html_
assert "Call 555-0100." in html_ and "%sitename%" not in html_
assert "%s / %d" % (doc.pages[0]["name"], now.year) in html_

# insert through the dialogs' path: appends to the chosen text box, undo takes it away
for o in w.scene.selectedItems():
    o.setSelected(False)
t = [o for o in w.scene.items() if isinstance(o, ItemObj) and o.editable and o.d["kind"] == "text"][0]
t.setSelected(True)
w.set_prop("text", "Today is ")
assert insertinfo.insert_into_selection(w, "%date%")
cur = [o for o in w.scene.items() if isinstance(o, ItemObj) and o.editable and o.d["kind"] == "text"][0]
assert cur.d["text"] == "Today is %date%", cur.d["text"]

# the choice dialogs list real values
for kind in ("datetime", "page", "site", "variable", "object"):
    dlg = insertinfo.InfoDialog(w, kind)
    assert dlg.list.count() >= 3, kind
    dlg.list.setCurrentRow(0)
    dlg.accept()
    assert dlg.chosen, kind
dlg = insertinfo.InfoDialog(w, "datetime")
assert any(str(now.year) in dlg.list.item(i).text() for i in range(dlg.list.count()))
assert any("Your details: Company" in c[1] for c in insertinfo.variable_choices(w))

# placeholder text
assert insertinfo.fill_placeholder(w, 3, replace=True)
txt = [o for o in w.scene.items() if isinstance(o, ItemObj) and o.editable and o.d["kind"] == "text"][0].d["text"]
assert txt.count("\n\n") == 2 and txt.startswith("Lorem ipsum")
assert insertinfo.fill_placeholder(w, 1, replace=False)
txt2 = [o for o in w.scene.items() if isinstance(o, ItemObj) and o.editable and o.d["kind"] == "text"][0].d["text"]
assert txt2.startswith(txt) and txt2.count("\n\n") == 3
w.undo.undo()
assert [o for o in w.scene.items() if isinstance(o, ItemObj) and o.editable and o.d["kind"] == "text"][0].d["text"] == txt

# nothing selected: no crash, text goes to the clipboard
for o in w.scene.selectedItems():
    o.setSelected(False)
assert not insertinfo.insert_into_selection(w, "%year%")
assert not insertinfo.fill_placeholder(w, 1)

labels = []
def walk(m):
    for a in m.actions():
        if a.menu():
            walk(a.menu())
        else:
            labels.append(a.text().replace("&", ""))
for a in w.menuBar().actions():
    if a.menu():
        walk(a.menu())
for want in ("Date or time...", "Page info...", "Site info...", "Object info...", "Variable...",
             "Fill with placeholder text..."):
    assert want in labels, want
w.deleteLater()
app.processEvents()
del w
print("ALL GOOD")
