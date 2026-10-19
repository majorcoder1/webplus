"""Proof Reader and Thesaurus. Must print ALL GOOD."""
import os
import sys

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from PyQt5.QtCore import QRectF
from PyQt5.QtWidgets import QApplication

from sitewright import proofread, thesaurus
from sitewright.canvas import ItemObj
from sitewright.model import new_item
from sitewright.window import MainWindow

app = QApplication([])


def fixed(text):
    """Apply every fix to a string the way the dialog does."""
    class F:
        pass
    f = F()
    f.cont, f.key = {"t": text}, "t"
    entries = [(f, s, e, p, r) for s, e, p, r in proofread.issues(text)]
    proofread.apply_fixes(entries)
    return f.cont["t"], [p for _s, _e, p, _r in proofread.issues(text)]


# each kind of slip is found and fixed
assert fixed("This is is a test.")[0] == "This is a test."
assert fixed("Two  spaces here.")[0] == "Two spaces here."
assert fixed("Hello , world !")[0] == "Hello, world!"
assert fixed("It ended.Then it began.")[0] == "It ended. Then it began."
assert fixed("a,b and c")[0] == "a, b and c"
assert fixed("First one. second one.")[0] == "First one. Second one."
assert fixed("She ate a apple and an banana.")[0] == "She ate an apple and a banana."
assert fixed("I think i can.")[0] == "I think I can."
assert fixed("Wow!!! Really??")[0] == "Wow! Really?"
assert fixed("trailing   \nnext")[0] == "trailing\nnext"

# things that are fine are left alone
for ok in ("A university and an hour.", "That that is fine.", "He had had enough.",
           "Visit example.com or www.site.org today.", "Price 3.50 each.", "Call 555-1234.",
           "e.g. this and i.e. that", "Hello... wait", "Use %sitename% here."):
    assert proofread.issues(ok) == [], (ok, proofread.issues(ok))

# unmatched brackets/quotes are reported but have no automatic fix
bad = proofread.issues('He said "hello (and left')
assert any(r is None for _s, _e, _p, r in bad) and len(bad) == 2

# tokens like %sitename% are never "fixed"
assert fixed("%sitename%  is  here")[0] == "%sitename% is here"

# the whole site: scan, fix one, fix all, undo
w = MainWindow()
w.show()
w.create_item("text", QRectF(20, 20, 300, 60))
t = [o for o in w.scene.items() if isinstance(o, ItemObj) and o.editable][0]
t.setSelected(True)
w.set_prop("text", "the the cat  sat .")
w.doc.pages[0]["items"].append(new_item("table", 0, 200))
w.doc.pages[0]["items"][-1]["cells"][1][1] = "a egg"
w.reload()
w.commit_if_changed("setup")
dlg = proofread.ProofReaderDialog(w)
n0 = len(dlg.entries)
assert n0 >= 4, n0
assert dlg.tree.topLevelItemCount() == n0
dlg.tree.setCurrentItem(dlg.tree.topLevelItem(0))
dlg.fix_one()
assert len(dlg.entries) == n0 - 1
dlg.fix_all()
assert dlg.entries == []
assert w.doc.pages[0]["items"][0]["text"] == "The cat sat." or w.doc.pages[0]["items"][0]["text"] == "the cat sat."
assert w.doc.pages[0]["items"][-1]["cells"][1][1] == "an egg"
w.undo.undo()
assert proofread.scan(w.doc) != []

# thesaurus: words come back grouped by meaning, with plain word-form guesses
r = thesaurus.lookup("happy")
assert r and r[0][0] == "adjective" and any("glad" in syns for _p, _g, syns in r)
assert thesaurus.lookup("running") and thesaurus.lookup("cities") and thesaurus.lookup("Quickly")
assert thesaurus.lookup("xqzvbn") == []
assert all("(a)" not in s for _p, _g, syns in thesaurus.lookup("laughing") for s in syns)
assert thesaurus.match_case("Happy", "glad") == "Glad" and thesaurus.match_case("HAPPY", "glad") == "GLAD"
assert thesaurus.match_case("happy", "glad") == "glad"

# the dialog finds the word and replaces it in the chosen text box
t = [o for o in w.scene.items() if isinstance(o, ItemObj) and o.editable and o.d["kind"] == "text"][0]
for o in w.scene.selectedItems():
    o.setSelected(False)
t.setSelected(True)
w.set_prop("text", "We are Happy today, happy!")
td = thesaurus.ThesaurusDialog(w, "Happy")
assert td.senses.count() >= 2 and td.syns.count() >= 1
td.syns.setCurrentRow(0)
chosen = td.chosen()
td.replace()
txt = [o for o in w.scene.items() if isinstance(o, ItemObj) and o.editable and o.d["kind"] == "text"][0].d["text"]
assert txt.startswith("We are %s today, happy!" % (chosen[:1].upper() + chosen[1:])), txt

# menu entries
labels = []
def walk(m):
    for a in m.actions():
        if a.menu():
            walk(a.menu())
        else:
            labels.append(a.text().replace("&", ""))
for a in w.menuBar().actions():
    if a.menu():
        walk(a.menu())
assert "Proof reader..." in labels and "Thesaurus..." in labels
w.deleteLater()
app.processEvents()
del w
print("ALL GOOD")
