"""Text > Insert: date and time, page, site and object information, variables, placeholder text.
Dates, page and site facts go in as %tokens% that are filled in when the site is published."""
from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import (QCheckBox, QDialog, QDialogButtonBox, QFormLayout, QLabel,
                             QListWidget, QListWidgetItem, QSpinBox, QVBoxLayout)

from . import export

LOREM = [
    "Lorem ipsum dolor sit amet, consectetur adipiscing elit, sed do eiusmod tempor incididunt "
    "ut labore et dolore magna aliqua. Ut enim ad minim veniam, quis nostrud exercitation "
    "ullamco laboris nisi ut aliquip ex ea commodo consequat.",
    "Duis aute irure dolor in reprehenderit in voluptate velit esse cillum dolore eu fugiat "
    "nulla pariatur. Excepteur sint occaecat cupidatat non proident, sunt in culpa qui officia "
    "deserunt mollit anim id est laborum.",
    "Sed ut perspiciatis unde omnis iste natus error sit voluptatem accusantium doloremque "
    "laudantium, totam rem aperiam, eaque ipsa quae ab illo inventore veritatis et quasi "
    "architecto beatae vitae dicta sunt explicabo.",
    "Nemo enim ipsam voluptatem quia voluptas sit aspernatur aut odit aut fugit, sed quia "
    "consequuntur magni dolores eos qui ratione voluptatem sequi nesciunt.",
    "Neque porro quisquam est, qui dolorem ipsum quia dolor sit amet, consectetur, adipisci "
    "velit, sed quia non numquam eius modi tempora incidunt ut labore et dolore magnam "
    "aliquam quaerat voluptatem.",
]

GROUPS = {
    "datetime": ("Date or time", [
        ("date", "Date (October 17, 2026)"), ("shortdate", "Short date (10/17/2026)"),
        ("isodate", "Year first (2026-10-17)"), ("weekday", "Day of the week"),
        ("month", "Month name"), ("day", "Day of the month"), ("year", "Year"),
        ("time", "Time (3:45 PM)"), ("time24", "Time, 24 hour (15:45)")]),
    "page": ("Page information", [
        ("pagename", "Page name"), ("pagetitle", "Page title"),
        ("pagenumber", "Page number"), ("pagecount", "Number of pages")]),
    "site": ("Site information", [
        ("sitename", "Site name"), ("sitepages", "Number of pages"), ("siteurl", "Web address")]),
}


def variable_choices(win):
    from .panels import USER_FIELDS
    out = []
    for key, (title, rows) in GROUPS.items():
        out += [(t, "%s: %s" % (title, label)) for t, label in rows]
    for key, label in USER_FIELDS:
        out.append((export.USER_TOKENS.get(key, key), "Your details: " + label))
    return out


def insert_into_selection(win, text):
    """Put text into the chosen text box (at the cursor if you were typing). False if none chosen."""
    objs = [o for o in win.selected() if o.d["kind"] in ("text", "button", "marquee", "arttext")]
    if not objs:
        from PyQt5.QtWidgets import QApplication
        QApplication.clipboard().setText(text)
        win.statusBar().showMessage("Copied %s - paste it into a text box" % text, 5000)
        return False
    box = win.props.w.get("text")
    o = objs[0]
    if box is not None and box.isVisible():
        if box.toPlainText() != o.d.get("text", ""):          # the panel is a step behind: catch it up
            box.blockSignals(True)
            box.setPlainText(o.d.get("text", ""))
            box.blockSignals(False)
        cur = box.textCursor()
        if not box.hasFocus():
            cur.movePosition(cur.End)                          # not typing: put it at the end
        cur.insertText(text)
        box.setTextCursor(cur)
        if o.d.get("text", "") != box.toPlainText():           # make sure the object has it too
            win.set_prop("text", box.toPlainText())
    else:
        win.set_prop("text", o.d.get("text", "") + text)
    return True


def fill_placeholder(win, paragraphs, replace=True):
    objs = [o for o in win.selected() if o.d["kind"] in ("text", "button", "marquee", "arttext")]
    if not objs:
        return False
    body = "\n\n".join(LOREM[i % len(LOREM)] for i in range(paragraphs))
    for o in objs:
        win.set_prop("text", body if replace else (o.d.get("text", "") + "\n\n" + body).strip(),
                     commit=False)
    win.props.refresh()
    win.commit_if_changed("Placeholder text")
    return True


class InfoDialog(QDialog):
    """A list of things that can be put into text; double-click or OK inserts the chosen one."""

    def __init__(self, win, kind):
        super().__init__(win)
        self.win, self.kind, self.chosen = win, kind, ""
        page = win.cur_page()
        self.values = export.token_values(win.doc, page)
        v = QVBoxLayout(self)
        if kind == "object":
            self.setWindowTitle("Insert object information")
            rows = self.object_rows()
        elif kind == "variable":
            self.setWindowTitle("Insert variable")
            rows = [(t, label) for t, label in variable_choices(win)]
        else:
            title, group = GROUPS[kind]
            self.setWindowTitle("Insert " + title.lower())
            rows = group
        v.addWidget(QLabel("Pick one and press OK. It is filled in when the site is published."
                           if kind != "object" else "Pick one and press OK. It is typed in as plain words."))
        self.list = QListWidget()
        for token, label in rows:
            shown = token if kind == "object" else self.values.get(token, "")
            it = QListWidgetItem("%s   ->   %s" % (label, shown or "(empty)"))
            it.setData(Qt.UserRole, token if kind == "object" else "%" + token + "%")
            self.list.addItem(it)
        self.list.setCurrentRow(0)
        self.list.itemDoubleClicked.connect(lambda _: self.accept())
        v.addWidget(self.list)
        bb = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        bb.accepted.connect(self.accept)
        bb.rejected.connect(self.reject)
        v.addWidget(bb)
        self.resize(480, 360)

    def object_rows(self):
        from .model import KIND_NAMES
        objs = self.win.selected()
        if not objs:
            return [("(select an object first)", "Nothing selected")]
        d = objs[0].d
        return [(KIND_NAMES.get(d["kind"], d["kind"]), "Kind of object"),
                ("%d px" % d["w"], "Width"), ("%d px" % d["h"], "Height"),
                ("%d" % d["x"], "Distance from the left"), ("%d" % d["y"], "Distance from the top"),
                (d["id"], "Object id")]

    def accept(self):
        it = self.list.currentItem()
        self.chosen = it.data(Qt.UserRole) if it else ""
        super().accept()


def run_info(win, kind):
    dlg = InfoDialog(win, kind)
    if dlg.exec_() == QDialog.Accepted and dlg.chosen and not dlg.chosen.startswith("(select"):
        insert_into_selection(win, dlg.chosen)


def run_placeholder(win):
    if not [o for o in win.selected() if o.d["kind"] in ("text", "button", "marquee", "arttext")]:
        win.statusBar().showMessage("Select a text box first", 4000)
        return
    dlg = QDialog(win)
    dlg.setWindowTitle("Fill with placeholder text")
    form = QFormLayout(dlg)
    n = QSpinBox()
    n.setRange(1, 10)
    n.setValue(2)
    form.addRow("Paragraphs", n)
    rep = QCheckBox("Replace the words already there")
    rep.setChecked(True)
    form.addRow(rep)
    bb = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
    bb.accepted.connect(dlg.accept)
    bb.rejected.connect(dlg.reject)
    form.addRow(bb)
    if dlg.exec_() == QDialog.Accepted:
        fill_placeholder(win, n.value(), rep.isChecked())
