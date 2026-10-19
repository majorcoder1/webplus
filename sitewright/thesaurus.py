"""Thesaurus: words with a similar meaning, grouped by meaning, from WordNet 3 (Princeton
University, licence in library/LICENSE-wordnet.txt)."""
import gzip
import json
import os
import re

from PyQt5.QtWidgets import (QDialog, QHBoxLayout, QLabel, QLineEdit, QListWidget,
                             QPushButton, QVBoxLayout)

PATH = os.path.join(os.path.dirname(__file__), "library", "thesaurus.json.gz")
POS_NAMES = {"n": "noun", "v": "verb", "a": "adjective", "r": "adverb"}
_data = None
_TAG = re.compile(r"\((a|p|ip)\)$")


def data():
    global _data
    if _data is None:
        try:
            with gzip.open(PATH, "rt", encoding="utf-8") as f:
                _data = json.load(f)
        except (OSError, ValueError):
            _data = {}
    return _data


def candidates(word):
    """The word and plain guesses at its root form (plurals, -ed, -ing, -er, -est, -ly)."""
    w = word.strip().lower()
    out = [w]
    for suf, add in (("ies", "y"), ("ied", "y"), ("es", ""), ("s", ""), ("ed", ""), ("ed", "e"),
                     ("ing", ""), ("ing", "e"), ("er", ""), ("er", "e"), ("est", ""), ("est", "e"),
                     ("ly", ""), ("ily", "y")):
        if w.endswith(suf) and len(w) - len(suf) >= 2:
            root = w[:-len(suf)] + add
            out.append(root)
            if len(root) > 2 and root[-1] == root[-2]:      # running -> runn -> run
                out.append(root[:-1])
    seen = []
    for c in out:
        if c not in seen:
            seen.append(c)
    return seen


def lookup(word):
    """[(part of speech, meaning, [similar words])] for the word, or [] if unknown."""
    d = data()
    for c in candidates(word):
        entry = d.get(c)
        if entry:
            out = []
            for pos in "nvar":
                for gloss, syns in entry.get(pos, []):
                    out.append((POS_NAMES[pos], gloss, [_TAG.sub("", s) for s in syns]))
            return out
    return []


def match_case(old, new):
    """Give the replacement the same capital letters as the word it replaces."""
    if old.isupper() and len(old) > 1:
        return new.upper()
    if old[:1].isupper():
        return new[:1].upper() + new[1:]
    return new


class ThesaurusDialog(QDialog):
    def __init__(self, win, word=""):
        super().__init__(win)
        self.win = win
        self.setWindowTitle("Thesaurus")
        self.resize(560, 420)
        self.old = word
        v = QVBoxLayout(self)
        top = QHBoxLayout()
        top.addWidget(QLabel("Look up:"))
        self.word = QLineEdit(word)
        self.word.returnPressed.connect(self.search)
        top.addWidget(self.word, 1)
        go = QPushButton("Look up")
        go.clicked.connect(self.search)
        top.addWidget(go)
        v.addLayout(top)
        cols = QHBoxLayout()
        left = QVBoxLayout()
        left.addWidget(QLabel("Meanings"))
        self.senses = QListWidget()
        self.senses.currentRowChanged.connect(self.show_synonyms)
        left.addWidget(self.senses)
        right = QVBoxLayout()
        right.addWidget(QLabel("Words with a similar meaning"))
        self.syns = QListWidget()
        self.syns.itemDoubleClicked.connect(lambda it: self.replace())
        right.addWidget(self.syns)
        cols.addLayout(left, 1)
        cols.addLayout(right, 1)
        v.addLayout(cols, 1)
        self.note = QLabel("")
        v.addWidget(self.note)
        row = QHBoxLayout()
        self.rep = QPushButton("Replace the word")
        self.rep.clicked.connect(self.replace)
        again = QPushButton("Look up this word")
        again.clicked.connect(self.look_up_chosen)
        close = QPushButton("Close")
        close.clicked.connect(self.close)
        for b in (self.rep, again, close):
            row.addWidget(b)
        v.addLayout(row)
        self.results = []
        if word:
            self.search()

    def search(self):
        w = self.word.text().strip()
        self.results = lookup(w)
        self.senses.clear()
        self.syns.clear()
        for pos, gloss, syns in self.results:
            self.senses.addItem("%s: %s" % (pos, gloss))
        if self.results:
            self.senses.setCurrentRow(0)
            self.note.setText("Double-click a word to put it in your text.")
        else:
            self.note.setText('No words found for "%s".' % w if w else "Type a word to look up.")

    def show_synonyms(self, row):
        self.syns.clear()
        if 0 <= row < len(self.results):
            for s in self.results[row][2]:
                self.syns.addItem(s)

    def chosen(self):
        it = self.syns.currentItem()
        return it.text() if it else ""

    def look_up_chosen(self):
        c = self.chosen()
        if c:
            self.word.setText(c)
            self.search()

    def replace(self):
        new = self.chosen()
        if not new:
            return
        old = self.old or self.word.text().strip()
        if replace_word_in_selection(self.win, old, new):
            self.old = new
            self.note.setText('Replaced with "%s".' % new)
        else:
            self.note.setText("Select a text box first.")


def replace_word_in_selection(win, old, new):
    """Swap one word for another in the chosen text box. Uses the highlighted words in the
    Properties panel when there are some, else the first place the word appears."""
    objs = [o for o in win.selected() if o.d["kind"] in ("text", "button", "marquee")]
    if not objs:
        return False
    box = win.props.w.get("text")
    if box is not None and box.isVisible():
        cur = box.textCursor()
        sel = cur.selectedText()
        if sel and sel.strip().lower() == old.strip().lower():
            cur.insertText(match_case(sel, new))
            return True
    pat = re.compile(r"(?<!\w)%s(?!\w)" % re.escape(old), re.IGNORECASE)
    for o in objs:
        t = o.d.get("text", "")
        m = pat.search(t)
        if m:
            win.set_prop("text", t[:m.start()] + match_case(m.group(0), new) + t[m.end():])
            if box is not None:
                box.blockSignals(True)
                box.setPlainText(o.d["text"])
                box.blockSignals(False)
            return True
    return False
