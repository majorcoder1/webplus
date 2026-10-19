"""Page tools: Set Object Order, Select Parent and Attach to Text."""
from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import (QAbstractItemView, QDialog, QDialogButtonBox, QHBoxLayout, QLabel,
                             QListWidget, QListWidgetItem, QPushButton, QVBoxLayout)

from .model import KIND_NAMES


def describe(item):
    name = KIND_NAMES.get(item.get("kind", ""), item.get("kind", "").title())
    text = item.get("text") or item.get("label") or item.get("alt") or ""
    text = " ".join(str(text).split())
    return "%s: %s" % (name, text[:34]) if text else name


# -- Set Object Order -------------------------------------------------------------
def reorder(lst, ids_top_first):
    """Put the objects in lst in the given order (first id = in front). Unknown ids are ignored,
    and objects that were not named keep their place at the back."""
    by = {d["id"]: d for d in lst}
    named = [by[i] for i in ids_top_first if i in by]
    rest = [d for d in lst if d["id"] not in set(ids_top_first)]
    lst[:] = rest + list(reversed(named))
    return lst


class SetOrderDialog(QDialog):
    """The objects of the page as a list, the one in front at the top; move them about."""

    def __init__(self, win):
        super().__init__(win)
        self.win = win
        self.setWindowTitle("Set Object Order")
        self.resize(420, 440)
        v = QVBoxLayout(self)
        v.addWidget(QLabel("The object at the top is in front of all the others."))
        row = QHBoxLayout()
        self.list = QListWidget()
        self.list.setDragDropMode(QAbstractItemView.InternalMove)
        self.list.setSelectionMode(QAbstractItemView.SingleSelection)
        row.addWidget(self.list, 1)
        col = QVBoxLayout()
        for label, fn in (("To front", lambda: self.move("front")), ("Forward", lambda: self.move(-1)),
                          ("Backward", lambda: self.move(1)), ("To back", lambda: self.move("back"))):
            b = QPushButton(label)
            b.clicked.connect(lambda _=False, f=fn: f())
            col.addWidget(b)
        col.addStretch(1)
        row.addLayout(col)
        v.addLayout(row, 1)
        bb = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        bb.accepted.connect(self.accept)
        bb.rejected.connect(self.reject)
        v.addWidget(bb)
        chosen = {o.d["id"] for o in win.selected()}
        for d in reversed(win.target_list()):
            it = QListWidgetItem(describe(d))
            it.setData(Qt.UserRole, d["id"])
            self.list.addItem(it)
            if d["id"] in chosen and self.list.currentItem() is None:
                self.list.setCurrentItem(it)
        if self.list.currentItem() is None and self.list.count():
            self.list.setCurrentRow(0)

    def move(self, how):
        r = self.list.currentRow()
        if r < 0:
            return
        n = self.list.count()
        new = {"front": 0, "back": n - 1}.get(how, max(0, min(n - 1, r + (how if isinstance(how, int) else 0))))
        it = self.list.takeItem(r)
        self.list.insertItem(new, it)
        self.list.setCurrentRow(new)

    def order(self):
        return [self.list.item(i).data(Qt.UserRole) for i in range(self.list.count())]


def set_object_order(win):
    if not win.target_list():
        win.statusBar().showMessage("There are no objects on this page yet", 4000)
        return
    dlg = SetOrderDialog(win)
    if dlg.exec_() == QDialog.Accepted:
        keep = {o.d["id"] for o in win.selected()}
        reorder(win.target_list(), dlg.order())
        win.reload(keep)
        win.commit_if_changed("Set object order")


# -- Select Parent --------------------------------------------------------------
def parent_ids(lst, selected_ids):
    """Ids of everything that shares a group with the selected objects (the selection's 'parent')."""
    groups = {d.get("group") for d in lst if d["id"] in selected_ids and d.get("group")}
    attached = {d["attach"]["to"] for d in lst if d["id"] in selected_ids and d.get("attach")}
    out = {d["id"] for d in lst if d.get("group") in groups and d.get("group")}
    return out | attached


def select_parent(win):
    sel = {o.d["id"] for o in win.selected()}
    if not sel:
        win.statusBar().showMessage("Select an object first", 4000)
        return False
    ids = parent_ids(win.target_list(), sel)
    if not ids or ids == sel:
        win.statusBar().showMessage("That object is not inside a group and is not attached to anything", 4000)
        return False
    win.reload(ids)
    return True


# -- Attach to Text ---------------------------------------------------------------
def attach(win, edge="bottom"):
    """Attach the other chosen objects to the chosen text box. They then move with it, and with
    edge 'bottom' they also stay under it when the text grows."""
    order = {d["id"]: i for i, d in enumerate(win.target_list())}
    objs = sorted(win.selected(), key=lambda o: order.get(o.d["id"], 0))     # the same anchor every time
    texts = [o for o in objs if o.d["kind"] == "text"]
    others = [o for o in objs if o not in texts or len(texts) > 1 and o is not texts[0]]
    if not texts or not others:
        win.statusBar().showMessage("Choose a text box and the object(s) to attach to it", 5000)
        return 0
    parent = texts[0].d
    n = 0
    for o in others:
        d = o.d
        if d["id"] == parent["id"] or (d.get("attach") or {}).get("to") == d["id"]:
            continue
        if _would_loop(win.target_list(), d["id"], parent["id"]):
            continue
        base_y = parent["y"] + (parent["h"] if edge == "bottom" else 0)
        d["attach"] = dict(to=parent["id"], edge=edge, dx=d["x"] - parent["x"], dy=d["y"] - base_y)
        n += 1
    if n:
        win.commit_if_changed("Attach to text")
    return n


def _would_loop(lst, child_id, parent_id):
    by = {d["id"]: d for d in lst}
    cur, seen = parent_id, set()
    while cur and cur not in seen:
        if cur == child_id:
            return True
        seen.add(cur)
        cur = (by.get(cur, {}).get("attach") or {}).get("to")
    return False


def detach(win):
    n = 0
    for o in win.selected():
        if o.d.pop("attach", None) is not None:
            n += 1
    if n:
        win.commit_if_changed("Detach from text")
    return n


def follow(win, moved=None):
    """Move the attached objects to where their text box says. If the user moved an attached
    object itself, remember its new distance instead."""
    lst = win.target_list()
    by = {d["id"]: d for d in lst}
    if moved is not None and moved.get("attach") and moved["attach"].get("to") in by:
        p = by[moved["attach"]["to"]]
        a = moved["attach"]
        base_y = p["y"] + (p["h"] if a["edge"] == "bottom" else 0)
        a["dx"], a["dy"] = moved["x"] - p["x"], moved["y"] - base_y
    changed = False
    for _ in range(4):                       # a few passes so chains of attached objects settle
        moved_any = False
        for d in lst:
            a = d.get("attach")
            if not a:
                continue
            p = by.get(a["to"])
            if p is None:
                d.pop("attach", None)
                continue
            if d is moved:
                continue
            x = p["x"] + a["dx"]
            y = p["y"] + (p["h"] if a["edge"] == "bottom" else 0) + a["dy"]
            if (d["x"], d["y"]) != (x, y):
                d["x"], d["y"] = x, y
                moved_any = changed = True
        if not moved_any:
            break
    if changed:
        for o in win.scene.items():
            d = getattr(o, "d", None)
            if getattr(o, "editable", False) and d and d.get("attach"):
                o.setPos(d["x"], d["y"])
    return changed
