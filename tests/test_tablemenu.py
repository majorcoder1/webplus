"""Table menu tools on a real window: click a cell, merge, sort, autofit, cell properties,
AutoFormat, calendar, undo, save and load. Must print ALL GOOD."""
import os
import sys
import tempfile

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from PyQt5.QtCore import QPointF, QRectF, Qt
from PyQt5.QtWidgets import QApplication

from sitewright import tablecore as tc
from sitewright.canvas import ItemObj
from sitewright.window import MainWindow

app = QApplication([])
w = MainWindow()
w.show()


def objs():
    return [o for o in w.scene.items() if isinstance(o, ItemObj) and o.editable]


def the_table():
    return [o for o in objs() if o.d["kind"] == "table"][0]


w.create_item("table", QRectF(20, 20, 480, 150))
t = the_table()
t.setSelected(True)
w.set_table_dims(rows=5, cols=3)
t = the_table()
t.setSelected(True)
assert t.d["rows"] == 5 and t.d["merges"] == [] and t.d["fmt"] == {}

# click on a cell picks it (a table that is already selected)
class Ev:
    def __init__(self, pos, mod=Qt.NoModifier):
        self._p, self._m = pos, mod
    def pos(self): return self._p
    def modifiers(self): return self._m
t.pick_cell(QPointF(250, 80), False)
assert t.d["sel"] == [2, 1, 2, 1], t.d["sel"]
t.pick_cell(QPointF(400, 140), True)
assert t.d["sel"] == [2, 1, 4, 2], t.d["sel"]
assert [sp.value() for sp in w.props.range_spins] == [3, 5, 2, 3]
w.table_sel_changed(0, 2)           # first row of the range -> row 2
assert the_table().d["sel"][0] == 1

# merge and separate through the menu methods; undo puts it back
t.d["cells"][1][0], t.d["cells"][1][1] = "A", "B"
w.commit_if_changed("Type")
t = the_table(); t.setSelected(True)
t.d["sel"] = [1, 0, 1, 1]
w.table_merge()
assert the_table().d["merges"] == [[1, 0, 1, 2]] and the_table().d["cells"][1][0] == "A B"
w.undo.undo()
assert the_table().d["merges"] == [] and the_table().d["cells"][1][0] == "A"
w.undo.redo()
assert the_table().d["merges"] == [[1, 0, 1, 2]]
w.table_separate()
assert the_table().d["merges"] == []

# sizes
t = the_table(); t.setSelected(True)
t.d["sel"] = [0, 0, 0, 0]
w.table_sizes("fit_cols")
assert abs(sum(tc.fractions(the_table().d, "colw", 3)) - 1) < 1e-9
w.table_sizes("dist_cols")
assert the_table().d["colw"] == []

# sort
t = the_table(); t.setSelected(True)
t.d["cells"] = [["H1", "H2", "H3"], ["b", "2", ""], ["a", "1", ""], ["c", "3", ""], ["", "", ""]]
w.commit_if_changed("Type")
t = the_table(); t.setSelected(True)
assert w.table_do("Sort table", lambda d: tc.sort_rows(d, 0, True))
assert [r[0] for r in the_table().d["cells"]][:4] == ["H1", "", "a", "b"]

# cell properties through the data path the dialog uses; AutoFormat; delete rows
t = the_table(); t.setSelected(True)
t.d["sel"] = [1, 0, 1, 2]
w.table_do("Cell properties", lambda d: tc.set_fmt(d, *tc.clamp_sel(d), fill="#ffee00", bold=False))
assert the_table().d["fmt"]["1,0"] == {"fill": "#ffee00", "bold": False}
w.table_do("AutoFormat", lambda d: tc.apply_autoformat(d, "Green stripes"))
assert the_table().d["hfill"] == "#1f7a4d" and the_table().d["fmt"] == {}
t = the_table(); t.setSelected(True)
t.d["sel"] = [1, 0, 2, 2]
w.table_delete("rows")
assert the_table().d["rows"] == 3

# calendar object and save/load
import datetime
before = len(w.doc.pages[0]["items"])
from sitewright.model import new_item
d = new_item("table", 80, 80, w=490, h=336)
tc.make_calendar(d, 2026, 10)
w.target_list().append(d)
w.reload({d["id"]})
w.commit_if_changed("Insert calendar")
assert len(w.doc.pages[0]["items"]) == before + 1
path = os.path.join(tempfile.mkdtemp(), "t.sitewright")
w.doc.save(path)
w.open_path(path)
cal = [i for i in w.doc.pages[0]["items"] if i["kind"] == "table" and i["rows"] == 8][0]
assert cal["merges"] == [[0, 0, 1, 7]] and cal["cells"][0][0] == "October 2026"

# the menu entries exist
labels = []
def walk(m):
    for a in m.actions():
        if a.menu():
            walk(a.menu())
        else:
            labels.append(a.text().replace("&", ""))
for a in w.menuBar().actions():
    if a.text().replace("&", "") == "Table":
        walk(a.menu())
for want in ("Merge cells", "Separate cells", "Sort...", "AutoFormat...", "Cell properties...",
             "Insert calendar...", "AutoFit column(s) to contents", "Set column width(s)...",
             "Evenly distribute rows"):
    assert want in labels, (want, labels)
print("ALL GOOD")
