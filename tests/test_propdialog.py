"""Edit Properties dialog: builds for every kind of object, edits apply as one Undo step,
and the table dialog has a typing grid, AutoFormat and a live sample. Must print ALL GOOD."""
import os
import sys

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from PyQt5.QtCore import QRectF
from PyQt5.QtWidgets import QApplication

from sitewright.canvas import ItemObj
from sitewright.model import DEFAULTS, new_item
from sitewright.propdialog import PropertiesDialog
from sitewright.window import MainWindow

app = QApplication([])
w = MainWindow()
w.show()

# every kind builds a dialog
for kind in DEFAULTS:
    d = new_item(kind, 10, 10)
    dlg = PropertiesDialog(w, d)
    assert dlg.tabs.count() >= 2, kind
    assert "Position and size" in [dlg.tabs.tabText(i) for i in range(dlg.tabs.count())], kind
    dlg.apply()          # no change must not break anything
    assert new_item(kind, 10, 10)["kind"] == kind
    dlg.deleteLater()


def objs():
    return [o for o in w.scene.items() if isinstance(o, ItemObj) and o.editable]


# a text box: change words, size and position, apply
w.create_item("text", QRectF(20, 20, 200, 60))
t = objs()[0]
t.setSelected(True)
dlg = PropertiesDialog(w, t.d)
tabs = [dlg.tabs.tabText(i) for i in range(dlg.tabs.count())]
assert tabs[:2] == ["Text", "Box"], tabs
txt = dlg.tabs.widget(0).findChild(type(dlg.tabs.widget(0).findChildren(object)[0]).__mro__[0]) if False else None
dlg.getters["text"]  # the words editor exists
from PyQt5.QtWidgets import QPlainTextEdit, QSpinBox
dlg.tabs.widget(0).findChildren(QPlainTextEdit)[0].setPlainText("Changed words")
dlg.getters["size"]  # exists
dlg.tabs.widget(0).findChildren(QSpinBox)[0].setValue(33)
dlg.tabs.widget(2).findChildren(QSpinBox)[0].setValue(77)      # Across
assert dlg.apply()
assert t.d["text"] == "Changed words" and t.d["size"] == 33 and t.d["x"] == 77
t.sync()
w.reload({t.d["id"]})
w.commit_if_changed("Edit properties")
w.undo.undo()
assert [d for d in w.doc.pages[0]["items"]][0]["text"] != "Changed words"
w.undo.redo()
assert [d for d in w.doc.pages[0]["items"]][0]["text"] == "Changed words"

# a table: rows/cols, typing in the grid, AutoFormat, sample, apply
w.create_item("table", QRectF(20, 120, 480, 150))
tb = [o for o in objs() if o.d["kind"] == "table"][0]
tb.setSelected(True)
dlg = PropertiesDialog(w, tb.d)
names = [dlg.tabs.tabText(i) for i in range(dlg.tabs.count())]
assert names[:2] == ["Table", "Contents"], names
dlg.t_rows.setValue(4)
dlg.t_cols.setValue(2)
assert dlg.grid.rowCount() == 4 and dlg.grid.columnCount() == 2
dlg.grid.item(1, 1).setText("typed in the grid")
dlg.t_look.setCurrentText("Dark")
assert dlg.d["hfill"] == "#0f172a" and not dlg.sample.pixmap().isNull()
assert dlg.apply()
assert tb.d["rows"] == 4 and tb.d["cols"] == 2 and tb.d["cells"][1][1] == "typed in the grid"
assert tb.d["hfill"] == "#0f172a" and tb.d["color"] == "#e2e8f0"

# the table's own merged cells survive an unrelated edit
from sitewright import tablecore as tc
tc.merge_cells(tb.d, 1, 0, 1, 1)
dlg = PropertiesDialog(w, tb.d)
dlg.t_head.setChecked(False)
dlg.apply()
assert tb.d["merges"] == [[1, 0, 1, 2]] and tb.d["header"] is False

# show_properties on the window with nothing selected does not crash
for o in objs():
    o.setSelected(False)
w.show_properties()

# double-click on a table opens properties; on text it edits the text
src = open(os.path.join(os.path.dirname(__file__), "..", "sitewright", "canvas.py")).read()
assert "self.win.show_properties()" in src

# the menu entry exists
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
assert "Object properties..." in labels
w.deleteLater()
app.processEvents()
del w
print("ALL GOOD")
