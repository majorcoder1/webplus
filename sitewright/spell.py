"""Spell checker built on the system's aspell, plus the Spell Checker dialog."""
import re
import shutil
import subprocess

from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import (QComboBox, QDialog, QHBoxLayout, QLabel,
                             QPushButton, QTreeWidget, QTreeWidgetItem,
                             QVBoxLayout)

TOKEN = re.compile(r"%\w+%")


def available():
    return shutil.which("aspell") is not None


def misspellings(lines, lang="en"):
    """For each text line return [(word, offset, [suggestions])].

    Uses aspell's pipe mode so suggestions come back in one process call."""
    if not lines:
        return []
    clean = [TOKEN.sub(lambda m: " " * len(m.group(0)), ln.replace("\n", " "))
             for ln in lines]
    payload = "!\n" + "\n".join("^" + ln for ln in clean) + "\n"
    try:
        out = subprocess.run(["aspell", "-a", "-l", lang], input=payload, text=True,
                             capture_output=True, timeout=30).stdout
    except (OSError, subprocess.SubprocessError):
        return [[] for _ in lines]
    results, cur, started = [], [], False
    for raw in out.splitlines():
        if raw.startswith("@(#)"):
            started = True
            continue
        if not started:
            continue
        if raw == "":
            results.append(cur)
            cur = []
            continue
        if raw[0] == "&":
            head, _, sugg = raw.partition(":")
            parts = head.split()
            cur.append((parts[1], int(parts[3]) - 1,
                        [s.strip() for s in sugg.split(",") if s.strip()][:8]))
        elif raw[0] == "#":
            parts = raw.split()
            cur.append((parts[1], int(parts[2]) - 1, []))
    while len(results) < len(lines):
        results.append([])
    return results[:len(lines)]


def text_fields(doc):
    """(page name, container, key) for every string worth checking."""
    pages = [(p["name"], p["items"]) for p in doc.pages
             if p.get("type", "page") == "page"] + [(name, items) for _m, name, items in doc.all_masters()]
    for name, items in pages:
        for it in items:
            if it["kind"] in ("text", "button", "marquee", "arttext") and it.get("text"):
                yield name, it, "text"
            if it["kind"] == "table":
                for row in it.get("cells", []):
                    for j, c in enumerate(row):
                        if c:
                            yield name, row, j
            if it["kind"] == "field" and it.get("label"):
                yield name, it, "label"


def scan(doc):
    """List of dicts: page, container, key, word, offset, suggestions."""
    fields = list(text_fields(doc))
    # one aspell call per field line keeps offsets simple
    flat, owners = [], []
    for page, cont, key in fields:
        for ln_no, ln in enumerate(str(cont[key]).split("\n")):
            flat.append(ln)
            owners.append((page, cont, key, ln_no))
    found = []
    for (page, cont, key, ln_no), res in zip(owners, misspellings(flat)):
        for word, off, sugg in res:
            found.append(dict(page=page, container=cont, key=key, line=ln_no,
                              word=word, offset=off, suggestions=sugg))
    return found


def replace_in_field(cont, key, line, offset, old, new):
    lines = str(cont[key]).split("\n")
    ln = lines[line]
    if ln[offset:offset + len(old)] == old:
        lines[line] = ln[:offset] + new + ln[offset + len(old):]
    else:
        lines[line] = ln.replace(old, new, 1)
    cont[key] = "\n".join(lines)


def replace_everywhere(doc, old, new):
    n = 0
    pat = re.compile(r"\b%s\b" % re.escape(old))
    for _page, cont, key in text_fields(doc):
        s = str(cont[key])
        s2, k = pat.subn(new, s)
        if k:
            cont[key] = s2
            n += k
    return n


class SpellDialog(QDialog):
    """Walks the site's text: pick a suggestion, then Replace / Ignore."""

    def __init__(self, parent, doc, on_change):
        super().__init__(parent)
        self.doc, self.on_change = doc, on_change
        self.setWindowTitle("Spell Checker")
        self.resize(560, 420)
        v = QVBoxLayout(self)
        self.status = QLabel("")
        v.addWidget(self.status)
        self.tree = QTreeWidget()
        self.tree.setHeaderLabels(["Word", "Where", "Suggestions"])
        self.tree.setRootIsDecorated(False)
        self.tree.currentItemChanged.connect(self.show_suggestions)
        v.addWidget(self.tree, 1)
        row = QHBoxLayout()
        row.addWidget(QLabel("Change to:"))
        self.combo = QComboBox()
        self.combo.setEditable(True)
        row.addWidget(self.combo, 1)
        v.addLayout(row)
        row = QHBoxLayout()
        for text, fn in (("Replace", self.replace), ("Replace all", self.replace_all),
                         ("Ignore", self.ignore), ("Ignore all", self.ignore_all),
                         ("Close", self.accept)):
            b = QPushButton(text)
            b.clicked.connect(fn)
            row.addWidget(b)
        v.addLayout(row)
        self.ignored = set()
        self.reload()

    def reload(self):
        self.found = [f for f in scan(self.doc) if f["word"].lower() not in self.ignored]
        self.tree.clear()
        for f in self.found:
            it = QTreeWidgetItem([f["word"], f["page"], ", ".join(f["suggestions"][:4])])
            it.setData(0, Qt.UserRole, f)
            self.tree.addTopLevelItem(it)
        self.status.setText("%d possible mistake(s) found." % len(self.found)
                            if self.found else "No spelling mistakes found.")
        if self.found:
            self.tree.setCurrentItem(self.tree.topLevelItem(0))
        else:
            self.combo.clear()

    def current(self):
        it = self.tree.currentItem()
        return it.data(0, Qt.UserRole) if it else None

    def show_suggestions(self, *_):
        f = self.current()
        self.combo.clear()
        if f:
            self.combo.addItems(f["suggestions"])
            self.combo.setCurrentText(f["suggestions"][0] if f["suggestions"] else f["word"])

    def replace(self):
        f = self.current()
        if f:
            replace_in_field(f["container"], f["key"], f["line"], f["offset"],
                             f["word"], self.combo.currentText())
            self.on_change("Spelling")
            self.reload()

    def replace_all(self):
        f = self.current()
        if f:
            replace_everywhere(self.doc, f["word"], self.combo.currentText())
            self.on_change("Spelling")
            self.reload()

    def ignore(self):
        it = self.tree.currentItem()
        if it:
            self.tree.takeTopLevelItem(self.tree.indexOfTopLevelItem(it))

    def ignore_all(self):
        f = self.current()
        if f:
            self.ignored.add(f["word"].lower())
            self.reload()
