"""Proof Reader: the small slips a spell checker cannot see - doubled words, double spaces,
spaces before commas, a missing space after a full stop, a sentence that starts with a small
letter, 'a' where 'an' belongs, and a few more."""
import re

from PyQt5.QtWidgets import (QDialog, QHBoxLayout, QLabel, QPushButton, QTreeWidget,
                             QTreeWidgetItem, QVBoxLayout)

from . import findreplace

TOKEN = re.compile(r"%\w+%")
A_EXCEPT = ("uni", "use", "usu", "uti", "eu", "one", "once", "ubiq")          # sound like "yoo/won"
AN_EXCEPT = ("hour", "honest", "honor", "honour", "heir")                      # silent h


def issues(text):
    """[(start, end, problem, replacement)] for one string. Positions are in the original text."""
    masked = TOKEN.sub(lambda m: "_" * len(m.group(0)), text)         # %tokens% are left alone
    out = []

    def add(m, problem, repl):
        out.append((m.start(), m.end(), problem, repl))

    for m in re.finditer(r"\b([A-Za-z']+)(\s+)\1\b", masked, re.IGNORECASE):
        if m.group(1).lower() not in ("had", "that"):                  # "had had" and "that that" can be right
            add(m, 'The word "%s" is repeated' % m.group(1), m.group(1))
    for m in re.finditer(r"(?<=\S)[ ]{2,}(?=\S)", masked):
        add(m, "Two or more spaces in a row", " ")
    for m in re.finditer(r"[ ]+([,;:!?]|\.(?=\s|$))", masked):
        add(m, "A space before %s" % m.group(1), m.group(1))
    for m in re.finditer(r"(?<=[a-z])([.!?])([A-Z][a-z])", masked):
        add(m, "No space after %s" % m.group(1), m.group(1) + " " + m.group(2))
    for m in re.finditer(r"(?<=[a-z0-9,;])([,;])(?=[A-Za-z])", masked):
        add(m, "No space after %s" % m.group(1), m.group(1) + " ")
    for m in re.finditer(r"(?<![.])([.!?]\s+)([a-z])", masked):
        before = masked[max(0, m.start() - 4):m.start() + 1].lower()
        if re.search(r"\b(e\.g|i\.e|etc|vs|mr|mrs|dr)\.$", before):
            continue
        add(m, "A sentence should start with a capital letter", m.group(1) + m.group(2).upper())
    for m in re.finditer(r"\b(a)\s+([aeiouAEIOU]\w*)", masked, re.IGNORECASE):
        w = m.group(2).lower()
        if not w.startswith(A_EXCEPT):
            add(m, 'Use "an" before "%s"' % m.group(2), ("An" if m.group(1) == "A" else "an")
                + masked[m.end(1):m.start(2)] + text[m.start(2):m.end(2)])
    for m in re.finditer(r"\b(an)\s+([bcdfgjklmnpqrstvwxzBCDFGJKLMNPQRSTVWXZ]\w*)", masked, re.IGNORECASE):
        w = m.group(2).lower()
        if not (w.startswith(AN_EXCEPT) or (len(w) <= 3 and w.isupper())):
            add(m, 'Use "a" before "%s"' % m.group(2), ("A" if m.group(1) == "An" else "a")
                + masked[m.end(1):m.start(2)] + text[m.start(2):m.end(2)])
    for m in re.finditer(r"(?<![\w'])i(?![\w'.])(?=\s)", masked):
        add(m, 'The word "I" should be a capital', "I")
    for m in re.finditer(r"([!?,;:])\1+", masked):
        add(m, "Repeated punctuation", m.group(1))
    for m in re.finditer(r"[ \t]+$", masked, re.MULTILINE):
        add(m, "Spaces at the end of a line", "")
    for pair in ("()", "[]", "{}"):
        if masked.count(pair[0]) != masked.count(pair[1]):
            out.append((0, 0, "Brackets %s do not match up" % pair, None))
    if masked.count('"') % 2:
        out.append((0, 0, "A quotation mark is not closed", None))
    out.sort(key=lambda x: (x[0], x[1]))
    # drop any that overlap an earlier one so fixes can be applied safely
    clean, last = [], -1
    for it in out:
        if it[3] is None or it[0] >= last:
            clean.append(it)
            last = max(last, it[1]) if it[3] is not None else last
    return clean


def scan(doc, page_index=None):
    """[(Field, start, end, problem, replacement)] over the whole site (or one page)."""
    found = []
    for f in findreplace.fields(doc, page_index):
        text = str(f.cont[f.key])
        for start, end, problem, repl in issues(text):
            found.append((f, start, end, problem, repl))
    return found


def apply_fixes(entries):
    """Make the chosen fixes (those with a replacement). Works from the end so positions hold."""
    by_field = {}
    for e in entries:
        if e[4] is not None:
            by_field.setdefault((id(e[0].cont), e[0].key), []).append(e)
    n = 0
    for group in by_field.values():
        f = group[0][0]
        text = str(f.cont[f.key])
        for _f, start, end, _p, repl in sorted(group, key=lambda e: -e[1]):
            text = text[:start] + repl + text[end:]
            n += 1
        f.cont[f.key] = text
    return n


class ProofReaderDialog(QDialog):
    def __init__(self, win):
        super().__init__(win)
        self.win = win
        self.setWindowTitle("Proof Reader")
        self.resize(660, 420)
        v = QVBoxLayout(self)
        self.info = QLabel("")
        v.addWidget(self.info)
        self.tree = QTreeWidget()
        self.tree.setHeaderLabels(["Page", "Problem", "In the text"])
        self.tree.setRootIsDecorated(False)
        self.tree.setColumnWidth(0, 110)
        self.tree.setColumnWidth(1, 270)
        self.tree.itemDoubleClicked.connect(lambda it, c: self.go_to())
        v.addWidget(self.tree, 1)
        row = QHBoxLayout()
        for label, fn in (("Fix this", self.fix_one), ("Fix all", self.fix_all),
                          ("Go to it", self.go_to), ("Check again", self.rescan), ("Close", self.close)):
            b = QPushButton(label)
            b.clicked.connect(fn)
            row.addWidget(b)
        v.addLayout(row)
        self.entries = []
        self.rescan()

    def rescan(self):
        self.entries = scan(self.win.doc)
        self.tree.clear()
        for e in self.entries:
            f, start, end, problem, repl = e
            text = str(f.cont[f.key])
            snippet = text[max(0, start - 12):end + 12].replace("\n", " ")
            it = QTreeWidgetItem([f.page_name, problem, snippet])
            self.tree.addTopLevelItem(it)
        self.info.setText("%d thing(s) to look at" % len(self.entries) if self.entries
                          else "Nothing found. Your words look tidy.")

    def current(self):
        i = self.tree.indexOfTopLevelItem(self.tree.currentItem())
        return self.entries[i] if 0 <= i < len(self.entries) else None

    def changed(self, label):
        w = self.win
        keep = {o.d["id"] for o in w.selected()}
        w.reload(keep)
        w.commit_if_changed(label)
        self.rescan()

    def fix_one(self):
        e = self.current()
        if e is None:
            return
        if e[4] is None:
            self.info.setText("That one needs you to fix it by hand: use Go to it.")
            return
        apply_fixes([e])
        self.changed("Proof read")

    def fix_all(self):
        n = apply_fixes(self.entries)
        self.changed("Proof read all")
        self.info.setText("Fixed %d. %s" % (n, self.info.text()))

    def go_to(self):
        e = self.current()
        if e is None:
            return
        from .findreplace import FindReplaceDialog, Match
        d = getattr(self.win, "_find_dialog", None) or FindReplaceDialog(self.win)
        d.go_to(Match(e[0], e[1], e[2]))
