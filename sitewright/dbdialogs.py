"""Database Merge dialogs: create, edit, import, photo database, repeating area and fields."""
import copy
import os

from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import (QCheckBox, QComboBox, QDialog, QDialogButtonBox, QFileDialog, QFormLayout, QHBoxLayout,
                             QInputDialog, QLabel, QMessageBox, QPushButton, QSpinBox, QTableWidget, QTableWidgetItem,
                             QVBoxLayout)

from . import databasemerge as dm
from .model import new_item


def pick_database(win, title="Choose a database"):
    dbs = win.doc.databases
    if not dbs:
        r = QMessageBox.question(win, "WebPlus", "There is no database yet. Create one now?")
        if r == QMessageBox.Yes:
            return create_database(win)
        return None
    if len(dbs) == 1:
        return dbs[0]
    name, ok = QInputDialog.getItem(win, title, "Database:", [d["name"] for d in dbs], 0, False)
    return next(d for d in dbs if d["name"] == name) if ok else None


def create_database(win):
    name, ok = QInputDialog.getText(win, "Create database", "Name for the database:", text="Products")
    if not ok or not name.strip():
        return None
    fields, ok = QInputDialog.getText(win, "Create database",
                                      "Field names, separated by commas (each record has one value per field):",
                                      text="name, description, price")
    if not ok:
        return None
    names = []
    for f in fields.split(","):
        f = dm.clean_field(f)
        if f and f not in names:
            names.append(f)
    db = dm.new_database(name.strip(), names or ["name"])
    win.doc.databases.append(db)
    win.commit_if_changed("Create database")
    edit_database(win, db)
    return db


def create_photo_database(win):
    folder = QFileDialog.getExistingDirectory(win, "Choose the folder of pictures")
    if not folder:
        return None
    db = dm.photo_database(win.doc, folder, os.path.basename(folder.rstrip("/")) or "Photos")
    if not db["rows"]:
        QMessageBox.information(win, "WebPlus", "There were no pictures in that folder.")
        return None
    win.doc.databases.append(db)
    win.commit_if_changed("Create photo database")
    win.statusBar().showMessage("Added %d pictures to the database \"%s\"" % (len(db["rows"]), db["name"]), 8000)
    return db


class EditDatabase(QDialog):
    def __init__(self, win, db):
        super().__init__(win)
        self.win, self.db = win, db
        self.work = copy.deepcopy(db)
        self.setWindowTitle("Edit database: " + db["name"])
        self.resize(760, 460)
        lay = QVBoxLayout(self)
        self.table = QTableWidget()
        lay.addWidget(self.table)
        row = QHBoxLayout()
        for label, fn in (("Add record", self.add_row), ("Delete record", self.del_row),
                          ("Add field", self.add_field), ("Delete field", self.del_field),
                          ("Rename database", self.rename), ("Import CSV...", self.import_csv),
                          ("Export CSV...", self.export_csv)):
            b = QPushButton(label)
            b.clicked.connect(fn)
            row.addWidget(b)
        lay.addLayout(row)
        lay.addWidget(QLabel("A picture field holds a picture name or web address. "
                             "In the page, type {{fieldname}} in a text object to show it."))
        bb = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        bb.accepted.connect(self.accept)
        bb.rejected.connect(self.reject)
        lay.addWidget(bb)
        self.fill()

    def fill(self):
        f = self.work["fields"]
        self.table.setColumnCount(len(f))
        self.table.setHorizontalHeaderLabels(f)
        self.table.setRowCount(len(self.work["rows"]))
        for i, r in enumerate(self.work["rows"]):
            for j, name in enumerate(f):
                v = str(r.get(name, ""))
                it = QTableWidgetItem(self.shown(v))
                it.setData(Qt.UserRole, v)
                self.table.setItem(i, j, it)

    def shown(self, v):
        a = self.win.doc.assets.get(v)
        return "[picture] " + a["name"] if a else v

    def pull(self):
        """Read the grid back into self.work."""
        rows = []
        for i in range(self.table.rowCount()):
            r = {}
            for j, name in enumerate(self.work["fields"]):
                it = self.table.item(i, j)
                if it is None:
                    r[name] = ""
                    continue
                keep = it.data(Qt.UserRole)
                r[name] = keep if keep is not None and it.text() == self.shown(str(keep)) else it.text()
            rows.append(r)
        self.work["rows"] = rows

    def add_row(self):
        self.pull()
        self.work["rows"].append({f: "" for f in self.work["fields"]})
        self.fill()
        self.table.scrollToBottom()

    def del_row(self):
        self.pull()
        rows = sorted({i.row() for i in self.table.selectedIndexes()}, reverse=True)
        for r in rows:
            del self.work["rows"][r]
        self.fill()

    def add_field(self):
        name, ok = QInputDialog.getText(self, "Add field", "Field name:")
        name = dm.clean_field(name) if ok else ""
        if name and name not in self.work["fields"]:
            self.pull()
            self.work["fields"].append(name)
            for r in self.work["rows"]:
                r[name] = ""
            self.fill()

    def del_field(self):
        cols = sorted({i.column() for i in self.table.selectedIndexes()}, reverse=True)
        if not cols:
            QMessageBox.information(self, "WebPlus", "Click a cell in the field first.")
            return
        self.pull()
        for c in cols:
            name = self.work["fields"].pop(c)
            for r in self.work["rows"]:
                r.pop(name, None)
        self.fill()

    def rename(self):
        name, ok = QInputDialog.getText(self, "Rename database", "Name:", text=self.work["name"])
        if ok and name.strip():
            self.work["name"] = name.strip()

    def import_csv(self):
        path, _ = QFileDialog.getOpenFileName(self, "Import CSV", "", "CSV files (*.csv *.txt)")
        if not path:
            return
        with open(path, encoding="utf-8-sig", errors="replace") as f:
            fields, rows = dm.from_csv(f.read())
        if not fields:
            QMessageBox.information(self, "WebPlus", "That file has no records.")
            return
        self.work["fields"], self.work["rows"] = fields, rows
        self.fill()

    def export_csv(self):
        self.pull()
        path, _ = QFileDialog.getSaveFileName(self, "Export CSV", self.work["name"] + ".csv", "CSV files (*.csv)")
        if path:
            with open(path, "w", encoding="utf-8", newline="") as f:
                f.write(dm.to_csv(self.work))

    def accept(self):
        self.pull()
        self.db.update(name=self.work["name"], fields=self.work["fields"], rows=self.work["rows"])
        super().accept()


def edit_database(win, db=None):
    db = db or pick_database(win, "Edit database")
    if db is None:
        return
    if EditDatabase(win, db).exec_() == QDialog.Accepted:
        win.reload({o.d["id"] for o in win.selected()})
        win.commit_if_changed("Edit database")


# -- repeating area ---------------------------------------------------------------------------------
def repeaters(win):
    return [d for d in win.cur_page()["items"] if d.get("kind") == "repeater"]


def insert_repeating_area(win):
    db = pick_database(win, "Insert repeating area")
    if db is None:
        return
    y = max([d["y"] + d["h"] for d in win.cur_page()["items"]] or [40]) + 20
    d = new_item("repeater", 40, min(round(y), max(int(win.cur_page()["h"]) - 140, 0)), db=db["id"])
    win.cur_page()["items"].append(d)
    win.reload({d["id"]})
    win.commit_if_changed("Insert repeating area")
    win.statusBar().showMessage("Now add fields inside it: Tools > Database Merge > Insert Text Field", 8000)


def layout_dialog(win):
    objs = [o for o in win.selected() if o.d["kind"] == "repeater"]
    reps = [o.d for o in objs] or repeaters(win)
    if not reps:
        QMessageBox.information(win, "WebPlus", "There is no repeating area on this page yet.")
        return
    d = reps[0]
    dlg = QDialog(win)
    dlg.setWindowTitle("Repeating area layout")
    lay = QFormLayout(dlg)
    dbs = QComboBox()
    for x in win.doc.databases:
        dbs.addItem(x["name"], x["id"])
    dbs.setCurrentIndex(max(dbs.findData(d.get("db")), 0))
    cols = QSpinBox()
    cols.setRange(1, 12)
    cols.setValue(int(d.get("cols", 1)))
    gap = QSpinBox()
    gap.setRange(0, 400)
    gap.setValue(int(d.get("gap", 16)))
    gap.setSuffix(" px")
    limit = QSpinBox()
    limit.setRange(0, 9999)
    limit.setValue(int(d.get("limit", 0)))
    limit.setSpecialValueText("All records")
    sort = QComboBox()
    sort.addItem("As entered", "")

    def fields():
        sort.clear()
        sort.addItem("As entered", "")
        x = dm.find(win.doc, dbs.currentData())
        for f in (x["fields"] if x else []):
            sort.addItem(f, f)
        sort.setCurrentIndex(max(sort.findData(d.get("sort", "")), 0))

    dbs.currentIndexChanged.connect(lambda _=0: fields())
    fields()
    desc = QCheckBox("Biggest or last first")
    desc.setChecked(bool(d.get("desc")))
    lay.addRow("Database", dbs)
    lay.addRow("Records across", cols)
    lay.addRow("Space between records", gap)
    lay.addRow("Show at most", limit)
    lay.addRow("Sort by", sort)
    lay.addRow(desc)
    lay.addRow(QLabel("The size of the area is the size of one record. Drag its corners to change it."))
    bb = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
    bb.accepted.connect(dlg.accept)
    bb.rejected.connect(dlg.reject)
    lay.addRow(bb)
    if dlg.exec_() != QDialog.Accepted:
        return
    for r in (reps if objs else reps[:1]):
        r.update(db=dbs.currentData() or "", cols=cols.value(), gap=gap.value(), limit=limit.value(),
                 sort=sort.currentData() or "", desc=desc.isChecked())
    win.reload({o.d["id"] for o in win.selected()})
    win.commit_if_changed("Repeating area layout")


def insert_field(win, picture=False):
    reps = repeaters(win)
    if not reps:
        QMessageBox.information(win, "WebPlus", "Insert a repeating area first "
                                "(Tools > Database Merge > Insert Repeating Area).")
        return
    sel = [o.d for o in win.selected() if o.d["kind"] == "repeater"]
    rep = sel[0] if sel else reps[0]
    db = dm.find(win.doc, rep.get("db")) or pick_database(win, "Insert field")
    if db is None:
        return
    if not db["fields"]:
        QMessageBox.information(win, "WebPlus", "That database has no fields.")
        return
    name, ok = QInputDialog.getItem(win, "Insert picture field" if picture else "Insert text field",
                                    "Field:", db["fields"], 0, False)
    if not ok:
        return
    n = sum(1 for d in win.cur_page()["items"] if d.get("rep") == rep["id"])
    x, y = rep["x"] + 8, rep["y"] + 8 + (n * 26 if not picture else 0)
    if picture:
        d = new_item("image", round(x), round(y), asset="", field=name, fit="cover", alt="{{%s}}" % name)
        d["w"], d["h"] = round(min(rep["w"] - 16, 160)), round(min(rep["h"] - 16, 120))
    else:
        d = new_item("text", round(x), round(min(y, rep["y"] + rep["h"] - 34)), text="{{%s}}" % name)
        d["w"], d["h"] = round(rep["w"] - 16), 28
    d["rep"] = rep["id"]
    d["attach"] = dict(to=rep["id"], edge="top", dx=d["x"] - rep["x"], dy=d["y"] - rep["y"])   # moves with the area
    win.cur_page()["items"].append(d)
    win.reload({d["id"]})
    win.commit_if_changed("Insert database field")
