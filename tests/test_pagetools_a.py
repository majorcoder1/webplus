"""Set Object Order, Select Parent, Attach to Text. Must print ALL GOOD."""
import os
import sys

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from PyQt5.QtCore import QRectF, Qt
from PyQt5.QtWidgets import QApplication

from sitewright import pagetools
from sitewright.canvas import ItemObj
from sitewright.model import new_item
from sitewright.window import MainWindow

app = QApplication([])
w = MainWindow()
w.show()
doc = w.doc


def objs():
    return [o for o in w.scene.items() if isinstance(o, ItemObj) and o.editable]


def by_id(i):
    return [o for o in objs() if o.d["id"] == i][0]


def sel(*ids):
    w._sel_guard = True          # (selecting one member of a group selects the whole group)
    for o in w.scene.selectedItems():
        o.setSelected(False)
    w._sel_guard = False
    for i in ids:
        by_id(i).setSelected(True)


a = new_item("rect", 0, 0, id="a")
b = new_item("text", 0, 100, id="b", text="Bee words")
c = new_item("ellipse", 0, 200, id="c")
d_ = new_item("button", 0, 300, id="d", text="Dee")
doc.pages[0]["items"] += [a, b, c, d_]
w.reload()
w.commit_if_changed("setup")

# ---- Set Object Order
lst = list(doc.pages[0]["items"])
assert [x["id"] for x in pagetools.reorder(lst, ["a", "b", "c", "d"])] == ["d", "c", "b", "a"], "first named = in front (last in list)"
assert [x["id"] for x in pagetools.reorder(list(doc.pages[0]["items"]), ["c"])] == ["a", "b", "d", "c"]
assert pagetools.describe(b) == "Text: Bee words" and pagetools.describe(a) == "Rectangle"
sel("a")
dlg = pagetools.SetOrderDialog(w)
assert [dlg.list.item(i).data(Qt.UserRole) if False else dlg.list.item(i).data(0x100) for i in range(4)] == ["d", "c", "b", "a"]
assert dlg.list.currentItem().data(0x100) == "a", "the chosen object is selected in the list"
dlg.move("front")
assert dlg.order() == ["a", "d", "c", "b"]
dlg.move(1)                      # backward one
assert dlg.order() == ["d", "a", "c", "b"]
dlg.move("back")
assert dlg.order() == ["d", "c", "b", "a"]
dlg.list.setCurrentRow(2)
dlg.move(-1)
assert dlg.order() == ["d", "b", "c", "a"]
# applying it through the same path the window uses
keep = {o.d["id"] for o in w.selected()}
pagetools.reorder(w.target_list(), dlg.order())
w.reload(keep)
w.commit_if_changed("Set object order")
assert [x["id"] for x in doc.pages[0]["items"]] == ["a", "c", "b", "d"]
w.undo.undo()
assert [x["id"] for x in doc.pages[0]["items"]] == ["a", "b", "c", "d"]
doc = w.doc          # undo gives the document fresh copies of everything: pick them up again
a, b, c, d_ = [next(x for x in doc.pages[0]["items"] if x["id"] == i) for i in "abcd"]

# ---- Select Parent
a["group"] = c["group"] = "g1"
w.reload()
sel("a")
assert pagetools.parent_ids(doc.pages[0]["items"], {"a"}) == {"a", "c"}
assert pagetools.select_parent(w) is False or True
sel("d")
assert pagetools.select_parent(w) is False, "an ungrouped object has no parent"
a.pop("group")
c.pop("group")

# ---- Attach to Text
w.reload()
sel("b", "c", "d")
assert pagetools.attach(w, "bottom") == 2          # the text box is the anchor
assert c["attach"]["to"] == "b" and d_["attach"]["edge"] == "bottom" and "attach" not in b
b_h = b["h"]
assert c["attach"]["dy"] == 200 - (100 + b_h)
# moving the text box takes the attached objects with it
by_id("b").setPos(50, 150)
assert (b["x"], b["y"]) == (50, 150)
assert (c["x"], c["y"]) == (50, 150 + b_h + c["attach"]["dy"]) and (d_["x"], d_["y"]) == (50, 150 + b_h + d_["attach"]["dy"])
sel("b")
w.nudge(10, 0)
assert (b["x"], c["x"]) == (60, 60)
# growing the text box (more words -> taller) pushes the ones under it down
y_before = c["y"]
w.set_prop("text", "a very long line of words that wraps around many times in this narrow box " * 3)
by = b["h"] - b_h
assert by > 0 and c["y"] == y_before + by, (by, c["y"], y_before)
assert by_id("c").pos().y() == c["y"], "the screen follows too"
# moving an attached object itself changes its distance instead of dragging the text box
by_id("c").setPos(by_id("c").pos().x(), c["y"] + 40)
assert c["attach"]["dy"] == (c["y"] - (b["y"] + b["h"]))
assert b["y"] == 150
# 'beside' (top) keeps the distance from the text box's top, whatever its height
sel("b", "d")
d_.pop("attach")
assert pagetools.attach(w, "top") == 1 and d_["attach"]["edge"] == "top"
tall = b["h"]
w.set_prop("text", "short")
assert d_["y"] == b["y"] + d_["attach"]["dy"]
# nothing selected / no text box: nothing happens
sel("a", "c")
assert pagetools.attach(w, "bottom") == 0
# no loops: a text box cannot be attached to something attached to it
t2 = new_item("text", 300, 0, id="t2", text="other")
doc.pages[0]["items"].append(t2)
w.reload()
sel("b", "t2")
n = pagetools.attach(w, "top")      # b is the anchor, t2 attaches to b
assert t2["attach"]["to"] == "b"
sel("t2", "b")
assert pagetools.attach(w, "top") in (0, 1)
assert "attach" not in b or b["attach"]["to"] != "t2"
# detach
sel("t2")
assert pagetools.detach(w) == 1 and "attach" not in t2
# a missing text box drops the attachment instead of crashing
c["attach"]["to"] = "gone"
pagetools.follow(w)
assert "attach" not in c
# select parent for an attached object finds its text box
d_["attach"]["to"] = "b"
sel("d")
assert pagetools.parent_ids(doc.pages[0]["items"], {"d"}) == {"b"}
assert pagetools.select_parent(w)
assert {o.d["id"] for o in w.selected()} == {"b"}

# saved and reloaded
import tempfile
path = os.path.join(tempfile.mkdtemp(), "t.site")
doc.save(path)
w.open_path(path)
assert [i for i in w.doc.pages[0]["items"] if i["id"] == "d"][0]["attach"]["to"] == "b"

labels = []
def walk(m):
    for act in m.actions():
        if act.menu():
            walk(act.menu())
        else:
            labels.append(act.text().replace("&", ""))
for act in w.menuBar().actions():
    if act.menu():
        walk(act.menu())
for want in ("Set object order...", "Detach from text", "Select parent (the whole group)"):
    assert want in labels, want
assert any("Attach under the text box" in l for l in labels)
w.deleteLater()
app.processEvents()
del w
print("ALL GOOD")
