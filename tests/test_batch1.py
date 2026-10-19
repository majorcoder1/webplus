"""Batch 1 features: replicate, paste unformatted, hidden objects, zoom to selection. Must print ALL GOOD."""
import os
import sys

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from PyQt5.QtCore import QRectF
from PyQt5.QtWidgets import QApplication

from sitewright.canvas import ItemObj
from sitewright.window import MainWindow

app = QApplication([])
w = MainWindow()
w.show()


def objs():
    return [o for o in w.scene.items() if isinstance(o, ItemObj) and o.editable]


# replicate: 1 rectangle -> 3 across x 2 down = 6 in total
w.create_item("rect", QRectF(20, 20, 100, 50))
objs()[0].setSelected(True)
w.replicate(3, 2, 120, 70)
items = w.doc.pages[0]["items"]
assert len(items) == 6, len(items)
xs = sorted({d["x"] for d in items})
ys = sorted({d["y"] for d in items})
assert xs == [20, 140, 260] and ys == [20, 90], (xs, ys)
assert len({d["id"] for d in items}) == 6

# undo takes all the copies away at once
w.undo.undo()
assert len(w.doc.pages[0]["items"]) == 1

# paste as unformatted text: bold red text comes back plain
w.create_item("text", QRectF(40, 200, 300, 60))
t = [o for o in objs() if o.d["kind"] == "text"][0]
t.setSelected(True)
w.set_prop("bold", True)
w.set_prop("color", "#ff0000")
w.set_prop("text", "Keep these words")
w.copy()
w.paste_plain()
texts = [d for d in w.doc.pages[0]["items"] if d["kind"] == "text"]
assert len(texts) == 2
new = texts[-1]
assert new["text"] == "Keep these words" and not new["bold"] and new["color"] == "#222222", new
assert w.clip[0]["bold"] is True, "clipboard should keep the original look"

# hidden objects can be hidden in the editor and shown again
t = [o for o in objs() if o.d["kind"] == "text"][0]
for o in objs():
    o.setSelected(False)
t.setSelected(True)
w.set_prop("hidden", True)
t = [o for o in objs() if o.d["id"] == t.d["id"]][0]
w.hidden_action.setChecked(False)
w.toggle_hidden_objects()
assert not t.isVisible()
w.hidden_action.setChecked(True)
w.toggle_hidden_objects()
assert t.isVisible()

# zoom to selection changes the zoom and does not crash with nothing selected
for o in objs():
    o.setSelected(False)
w.zoom_selection()
objs()[0].setSelected(True)
w.zoom_selection()
assert 0.1 <= w.view.zoom <= 4.0

# toggle case and clear text formatting
for o in objs():
    o.setSelected(False)
t = [o for o in objs() if o.d["kind"] == "text"][0]
t.setSelected(True)
w.set_prop("text", "Hello World")
w.change_case("toggle")
t = [o for o in objs() if o.d["id"] == t.d["id"]][0]
assert t.d["text"] == "hELLO wORLD", t.d["text"]
w.set_prop("bold", True)
w.set_prop("color", "#00aa00")
w.clear_text_format()
assert not t.d["bold"] and t.d["color"] == "#222222" and t.d["text"] == "hELLO wORLD"

print("ALL GOOD")
