"""Find and Replace over text boxes, buttons, table cells and labels, this page or the whole site.
Must print ALL GOOD."""
import os
import sys

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from PyQt5.QtCore import QRectF
from PyQt5.QtWidgets import QApplication

from sitewright import findreplace as fr
from sitewright.canvas import ItemObj
from sitewright.model import new_item, new_page
from sitewright.window import MainWindow

app = QApplication([])
w = MainWindow()
w.show()
doc = w.doc

# a small site: two pages and a master page
doc.pages.append(new_page("Second"))
doc.pages[0]["items"] += [new_item("text", 0, 0, text="Welcome to the Garden. The garden is open."),
                          new_item("button", 0, 100, text="Garden tour"),
                          new_item("table", 0, 200)]
doc.pages[0]["items"][-1]["cells"] = [["Name", "Where"], ["Garden shed", "back"], ["gardener", "x"]]
doc.pages[1]["items"] += [new_item("text", 0, 0, text="GARDEN hours: 9 to 5\nsecond line garden")]
doc.master.append(new_item("text", 0, 0, text="(c) The Garden Club"))
w.reload()

# plain search: not case sensitive by default, counts every spot
ms = fr.find_all(doc, "garden")
assert len(ms) == 8, len(ms)
assert len(fr.find_all(doc, "garden", match_case=True)) == 3      # lower-case ones only
assert len(fr.find_all(doc, "garden", whole_word=True)) == 7      # not "gardener"
assert len(fr.find_all(doc, "garden", page_index=0)) == 5
assert fr.find_all(doc, "") == []
assert fr.find_all(doc, "zzz") == []

# the matches come in reading order and know their page
pages = [m.field.page_name for m in ms]
assert pages[0] == "Home" or pages[0] == doc.pages[0]["name"]
assert pages[-1] == "Master page"

# replace one
m = ms[0]
fr.replace_one(m, "Park")
assert doc.pages[0]["items"][0]["text"].startswith("Welcome to the Park.")
fr.replace_one(fr.find_all(doc, "Park")[0], "Garden")

# replace all with options
n = fr.replace_all(doc, "garden", "orchard", whole_word=True, match_case=True)
assert n == 2, n
assert doc.pages[0]["items"][0]["text"] == "Welcome to the Garden. The orchard is open."
assert doc.pages[0]["items"][2]["cells"][2][0] == "gardener"
n = fr.replace_all(doc, "garden", "plot")           # everything left, any case
assert n >= 5
assert fr.find_all(doc, "garden") == []
assert "plot hours" in doc.pages[1]["items"][0]["text"].lower() or "PLOT hours" in doc.pages[1]["items"][0]["text"]
assert "second line orchard" in doc.pages[1]["items"][0]["text"]
assert doc.master[0]["text"] == "(c) The plot Club"

# the dialog: find next walks through, wraps, replace and replace all are one undo step each
w.undo.clear()
w.commit_if_changed("start")
dlg = fr.FindReplaceDialog(w)
dlg.find.setText("plot")
dlg.scope.setCurrentIndex(1)
seen = []
for _ in range(len(fr.find_all(doc, "plot")) + 1):
    m = dlg.find_next()
    seen.append((id(m.field.cont), m.field.key, m.start))
assert seen[0] == seen[-1], "should wrap around to the first match"
assert len(set(seen)) == len(seen) - 1
dlg.repl.setText("field")
before = len(fr.find_all(doc, "plot"))
dlg.pos = (0, 0)
dlg.replace_current()
assert len(fr.find_all(doc, "plot")) == before - 1
dlg.do_replace_all()
assert fr.find_all(doc, "plot") == []
w.undo.undo()
assert fr.find_all(doc, "plot") != []
dlg.find.setText("nothing here")
assert dlg.find_next() is None and dlg.status.text() == "Not found"

# the menu entries exist
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
assert labels.count("Find and Replace...") == 2
w.find_replace()
w.deleteLater()
app.processEvents()
del w
print("ALL GOOD")
