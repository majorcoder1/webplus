"""Right-click menus and the Insert > Calendar entry. Must print ALL GOOD."""
import os
import sys

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from PyQt5.QtCore import QPointF, QRectF
from PyQt5.QtWidgets import QApplication, QMenu

from sitewright import tablecore as tc
from sitewright.canvas import ItemObj
from sitewright.window import MainWindow

app = QApplication([])
w = MainWindow()
w.show()


def objs():
    return [o for o in w.scene.items() if isinstance(o, ItemObj) and o.editable]


def labels(menu, out=None, path=""):
    out = out if out is not None else []
    for a in menu.actions():
        if a.isSeparator():
            continue
        t = a.text().replace("&", "")
        if a.menu():
            labels(a.menu(), out, path + t + " > ")
        else:
            out.append(path + t)
    return out


# the Insert menu has Calendar
insert = [a.menu() for a in w.menuBar().actions() if a.text().replace("&", "") == "Insert"][0]
assert "Calendar..." in labels(insert), labels(insert)

# page menu (empty page)
m = QMenu(w)
w.page_context_menu(m)
pl = labels(m)
for want in ("Paste", "Paste as unformatted text", "Page properties...", "Insert > Calendar...",
             "Insert > Table", "View > Fit page"):
    assert want in pl, (want, pl)

# object menu on a text box has the text and arrange entries
w.create_item("text", QRectF(20, 20, 200, 60))
t = objs()[0]
m = QMenu(w)
w.object_context_menu(m, "text")
ol = labels(m)
for want in ("Cut", "Copy", "Paste", "Delete", "Edit properties...", "Hyperlink...",
             "Arrange > Send to back", "Arrange > Align objects > Left", "Flip and rotate > Flip horizontal",
             "Text > Change case > tOGGLE cASE"):
    assert want in ol, (want, ol)
assert not any(a.shortcut().toString() for a in m.actions() if not a.menu()), "pop-up actions must not own shortcuts"

# table object menu has the whole Table submenu
w.create_item("table", QRectF(20, 120, 480, 150))
tb = [o for o in objs() if o.d["kind"] == "table"][0]
tb.setSelected(True)
m = QMenu(w)
w.object_context_menu(m, "table")
tl = labels(m)
for want in ("Table > AutoFormat...", "Table > Insert > Rows...", "Table > Select > All",
             "Table > Delete > Column(s)", "Table > Merge cells", "Table > Separate cells",
             "Table > Evenly distribute rows", "Table > AutoFit column(s) to contents",
             "Table > Set column width(s)...", "Table > Fill down", "Table > Cell properties...",
             "Table > Sort..."):
    assert want in tl, (want, tl)

# cell_at finds the right cell
assert tb.cell_at(QPointF(250, 80)) == (1, 1)
assert tb.cell_at(QPointF(5, 5)) == (0, 0)

# insert rows/columns keep merges in step; fill down / right
d = tb.d
d["cells"] = [["a", "b", "c"], ["", "", ""], ["", "", ""]]
tc.merge_cells(d, 1, 0, 2, 0)
tc.insert_rows(d, 2, 2)
assert d["rows"] == 5 and d["merges"] == [[1, 0, 4, 1]]
tc.insert_cols(d, 0, 1)
assert d["cols"] == 4 and d["merges"] == [[1, 1, 4, 1]]
d["cells"][0] = ["x", "a", "b", "c"]
tc.fill_down(d, 0, 0, 3, 0)
assert [r[0] for r in d["cells"][:4]] == ["x", "x", "x", "x"]
tc.fill_right(d, 0, 1, 0, 3)
assert d["cells"][0] == ["x", "a", "a", "a"]

# a real right-click on the page does not crash (menu is closed straight away)
from PyQt5.QtCore import QTimer
QTimer.singleShot(150, lambda: [x.close() for x in app.topLevelWidgets() if isinstance(x, QMenu)])
w.canvas_menu(w.view.mapToGlobal(w.view.rect().center()), None, QPointF(400, 600))
QTimer.singleShot(150, lambda: [x.close() for x in app.topLevelWidgets() if isinstance(x, QMenu)])
w.canvas_menu(w.view.mapToGlobal(w.view.rect().center()), tb, QPointF(100, 140))
print("ALL GOOD")
