"""Find and Replace: search the words in text boxes, buttons, table cells and form labels,
on this page or on the whole site. The search itself is plain functions (easy to test);
FindReplaceDialog is the window around them."""
import re
from collections import namedtuple

from PyQt5.QtWidgets import (QCheckBox, QComboBox, QDialog, QFormLayout, QHBoxLayout, QLabel,
                             QLineEdit, QPushButton)

Field = namedtuple("Field", "page_index page_name item cont key")
Match = namedtuple("Match", "field start end")

TEXT_KINDS = ("text", "button", "marquee", "arttext")


def fields(doc, page_index=None):
    """Every piece of words on the site in reading order. page_index limits it to one page."""
    spots = [(i, p["name"], p["items"]) for i, p in enumerate(doc.pages)
             if p.get("type", "page") == "page"]
    if page_index is None:
        spots += [(-1, name, items) for _mid, name, items in doc.all_masters()]
    else:
        spots = [s for s in spots if s[0] == page_index]
    for pi, name, items in spots:
        for it in items:
            k = it["kind"]
            if k in TEXT_KINDS and it.get("text"):
                yield Field(pi, name, it, it, "text")
            elif k == "table":
                for row in it.get("cells", []):
                    for j, c in enumerate(row):
                        if c:
                            yield Field(pi, name, it, row, j)
            elif k == "field" and it.get("label"):
                yield Field(pi, name, it, it, "label")


def pattern(query, match_case=False, whole_word=False):
    if not query:
        return None
    body = re.escape(query)
    if whole_word:
        body = r"(?<!\w)" + body + r"(?!\w)"
    return re.compile(body, 0 if match_case else re.IGNORECASE)


def find_all(doc, query, match_case=False, whole_word=False, page_index=None):
    pat = pattern(query, match_case, whole_word)
    if pat is None:
        return []
    out = []
    for f in fields(doc, page_index):
        for m in pat.finditer(str(f.cont[f.key])):
            if m.end() > m.start():
                out.append(Match(f, m.start(), m.end()))
    return out


def replace_one(match, new):
    s = str(match.field.cont[match.field.key])
    match.field.cont[match.field.key] = s[:match.start] + new + s[match.end:]


def replace_all(doc, query, new, match_case=False, whole_word=False, page_index=None):
    """Replace every match; returns how many were changed."""
    pat = pattern(query, match_case, whole_word)
    if pat is None:
        return 0
    n = 0
    for f in list(fields(doc, page_index)):
        s = str(f.cont[f.key])
        s2, k = pat.subn(lambda _m: new, s)
        if k:
            f.cont[f.key] = s2
            n += k
    return n


class FindReplaceDialog(QDialog):
    """Stays open beside the page so you can step through the matches."""

    def __init__(self, win):
        super().__init__(win)
        self.win = win
        self.setWindowTitle("Find and Replace")
        self.setModal(False)
        form = QFormLayout(self)
        self.find = QLineEdit()
        self.repl = QLineEdit()
        form.addRow("Find what", self.find)
        form.addRow("Replace with", self.repl)
        self.case = QCheckBox("Match case")
        self.word = QCheckBox("Whole words only")
        row = QHBoxLayout()
        row.addWidget(self.case)
        row.addWidget(self.word)
        form.addRow(row)
        self.scope = QComboBox()
        self.scope.addItems(["This page", "Whole site"])
        self.scope.setCurrentIndex(1)
        form.addRow("Look in", self.scope)
        self.status = QLabel("")
        form.addRow(self.status)
        btns = QHBoxLayout()
        for label, fn in (("Find next", self.find_next), ("Replace", self.replace_current),
                          ("Replace all", self.do_replace_all), ("Close", self.close)):
            b = QPushButton(label)
            b.clicked.connect(fn)
            btns.addWidget(b)
        form.addRow(btns)
        self.find.returnPressed.connect(self.find_next)
        self.pos = (0, 0)          # (field number, offset) where the next search starts
        self.current = None

    # -- helpers ---------------------------------------------------------
    def args(self):
        page = self.win.page_index if self.scope.currentIndex() == 0 else None
        return dict(query=self.find.text(), match_case=self.case.isChecked(),
                    whole_word=self.word.isChecked(), page_index=page)

    def matches(self):
        return find_all(self.win.doc, **self.args())

    def field_numbers(self):
        a = self.args()
        return {(id(f.cont), f.key): n for n, f in enumerate(fields(self.win.doc, a["page_index"]))}

    def order(self, m, nums):
        return (nums[(id(m.field.cont), m.field.key)], m.start)

    def go_to(self, m):
        """Go to the match: its page, its object selected, the words highlighted."""
        w = self.win
        if m.field.page_index >= 0 and m.field.page_index != w.page_index:
            i = w.page_combo.findData(w.doc.pages[m.field.page_index]["id"])
            if i >= 0:
                w.page_combo.setCurrentIndex(i)
                w.page_combo_picked(i)
            else:
                w.page_index = m.field.page_index
                w.reload()
        for o in w.scene.items():
            if getattr(o, "editable", False) and o.d.get("id") == m.field.item.get("id"):
                for s in w.scene.selectedItems():
                    s.setSelected(False)
                o.setSelected(True)
                if m.field.item["kind"] == "table":
                    row = [i for i, r in enumerate(m.field.item["cells"]) if r is m.field.cont]
                    if row:
                        m.field.item["sel"] = [row[0], m.field.key, row[0], m.field.key]
                    o.update()
                w.view.ensureVisible(o)
                break
        box = w.props.w.get("text")
        if box is not None and m.field.key == "text" and box.isVisible():
            from PyQt5.QtGui import QTextCursor
            cur = box.textCursor()
            cur.setPosition(m.start)
            cur.setPosition(m.end, QTextCursor.KeepAnchor)
            box.setTextCursor(cur)
        where = "master page" if m.field.page_index < 0 else 'page "%s"' % m.field.page_name
        self.status.setText("Found on %s" % where)

    # -- buttons ---------------------------------------------------------
    def find_next(self):
        ms = self.matches()
        if not ms:
            self.current = None
            self.status.setText("Not found")
            return None
        nums = self.field_numbers()
        later = [m for m in ms if self.order(m, nums) >= self.pos]
        m = later[0] if later else ms[0]
        if not later:
            self.status.setText("Reached the end - started again from the top")
        self.current = m
        self.pos = (self.order(m, nums)[0], m.start + 1)
        self.go_to(m)
        return m

    def replace_current(self):
        m = self.current
        if m is None or str(m.field.cont[m.field.key])[m.start:m.end].lower() != self.find.text().lower():
            m = self.find_next()
            if m is None:
                return
        nums = self.field_numbers()
        replace_one(m, self.repl.text())
        self.pos = (nums[(id(m.field.cont), m.field.key)], m.start + len(self.repl.text()))
        self.current = None
        self.after_change("Replace")
        self.find_next()

    def do_replace_all(self):
        a = self.args()
        n = replace_all(self.win.doc, a["query"], self.repl.text(), a["match_case"],
                        a["whole_word"], a["page_index"])
        self.after_change("Replace all")
        self.status.setText("Replaced %d" % n if n else "Not found")

    def after_change(self, label):
        w = self.win
        keep = {o.d["id"] for o in w.selected()}
        w.reload(keep)
        w.commit_if_changed(label)
