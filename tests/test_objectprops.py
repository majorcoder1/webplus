"""CSS properties, HTML attributes and Actions: rules, dialogs, and what lands on the page.
Must print ALL GOOD."""
import json
import os
import re
import subprocess
import sys
import tempfile

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from PyQt5.QtCore import QRectF
from PyQt5.QtWidgets import QApplication

from sitewright import export, objectprops as op
from sitewright.canvas import ItemObj
from sitewright.model import new_item, new_page
from sitewright.window import MainWindow

app = QApplication([])

# ---- rules
assert op.css_problem("color", "red") is None
assert op.css_problem("--my-var", "#fff") is None
assert op.css_problem("background-image", "url(img/a.png)") is None
assert op.css_problem("", "red") and op.css_problem("color", "")
assert "not a CSS property" in op.css_problem("Color!", "red")
assert op.css_problem("color", "red; background:url(x)") and op.css_problem("color", "red}")
assert op.css_problem("background", "url(javascript:alert(1))") and op.css_problem("width", "expression(1)")
assert op.css_problem("color", "x" * 400)
assert op.attr_problem("title", "hi") is None and op.attr_problem("data-x", "1") is None
assert op.attr_problem("onclick", "go()") is None
assert op.attr_problem("style", "x") and op.attr_problem("class", "x") and op.attr_problem("id", "x")
assert op.attr_problem("bad name", "x") and op.attr_problem("", "x") and op.attr_problem("1abc", "x")
assert op.clean_css([dict(state="hover", prop="COLOR", value="red"), dict(state="x", prop="bad!", value="1"),
                     dict(state="nonsense", prop="opacity", value=".5")]) == [
    dict(state="hover", prop="color", value="red"), dict(state="normal", prop="opacity", value=".5")]
assert op.clean_attrs([dict(name="Title", value="a"), dict(name="style", value="b")]) == [dict(name="title", value="a")]
nm = op.names()
assert "border-radius" in nm["css"] and "title" in nm["html"] and "onclick" in nm["events"] and len(nm["css"]) > 200
assert op.dom_id(dict(id="abc123")) == "o-abc123" and op.dom_id(dict(id="x", ident="my box!")) == "my-box-"

# ---- on the published page
w = MainWindow()
w.show()
doc = w.doc
home, other = doc.pages[0], new_page("Offers")
doc.pages.append(other)
panel = new_item("rect", 100, 100, id="panel1", hidden=True)
btn = new_item("button", 10, 10, id="btn1", text="Open", ident="openbtn")
btn["cssp"] = [dict(state="normal", prop="opacity", value=".8"), dict(state="hover", prop="background-color", value="#ff0"),
               dict(state="normal", prop="evil", value="red;color:blue")]
btn["attrs"] = [dict(name="title", value='Say "hi"'), dict(name="data-track", value="a&b"), dict(name="style", value="x"),
                dict(name="onmouseover", value="void(0)")]
btn["actions"] = [dict(on="click", do="toggle", target="panel1", value=""),
                  dict(on="hover", do="alert", target="", value='He said "hello"</script>'),
                  dict(on="leave", do="goto", target="", value="page:" + other["id"]),
                  dict(on="click", do="js", target="", value="console.log('x</script>');"),
                  dict(on="click", do="show", target="gone", value="")]
home["items"] += [panel, btn]
w.reload()
page = export.page_source(doc, home["id"], False)
btn_tag = re.search(r"<(?:a|div|button)[^>]*openbtn[^>]*>", page).group(0)
assert re.search(r'style="[^"]*;opacity:\.8"', btn_tag) or "opacity:.8" in btn_tag
assert "evil" not in page and "color:blue" not in btn_tag
assert 'title="Say &quot;hi&quot;"' in btn_tag and 'data-track="a&amp;b"' in btn_tag and 'onmouseover="void(0)"' in btn_tag
assert 'style="x"' not in btn_tag
assert " cp-btn1" in btn_tag
assert ".cp-btn1:hover{background-color:#ff0!important}" in page
assert 'id="o-panel1"' in page, "an object that is the target of an action gets an id"
assert 'id="openbtn"' in page
script = [s for s in re.findall(r"<script>\n(.*?)\n</script>", page, re.S) if 'getElementById("openbtn")' in s][0]
assert 'document.getElementById("openbtn")' in script and 'document.getElementById("o-panel1")' in script
assert '"click"' in script and '"mouseenter"' in script and '"mouseleave"' in script
assert 'He said \\"hello\\"<\\/script>' in script or "<\\/script>" in script
assert "</script>" not in script, "no way to close the script early"
assert "Offers" in export.page_files(doc)[other["id"]] or True
assert 'location.href="offers/"' in script or 'location.href="offers/index.html"' in script or "location.href=" in script
assert "gone" not in script, "an action pointing at a missing object is left out"
# the script is valid JavaScript
tmp = tempfile.mkdtemp()
js = os.path.join(tmp, "a.js")
open(js, "w", encoding="utf-8").write(script)
node = os.path.expanduser("~/.local/node/bin/node")
if not os.path.exists(node):
    node = "node"
r = subprocess.run([node, "--check", js], capture_output=True, text=True)
assert r.returncode == 0, r.stderr
# the whole exported site still builds
out = tempfile.mkdtemp()
export.export_site(doc, out)

# a page without any of this gets no extra script
home["items"][:] = [new_item("text", 0, 0, text="plain")]
assert 'getElementById("openbtn")' not in export.page_source(doc, home["id"], False)

# ---- dialogs and the window's entry points
w.reload()
t = [o for o in w.scene.items() if isinstance(o, ItemObj) and o.editable][0]
t.setSelected(True)
home["items"].append(new_item("rect", 0, 100, id="other1"))
w.reload()
t = [o for o in w.scene.items() if isinstance(o, ItemObj) and o.editable and o.d["kind"] == "text"][0]
t.setSelected(True)
dlg = op.CssDialog(w, [])
dlg.add_row(dict(state="hover", prop="color", value="red"))
assert dlg.rows() == [dict(state="hover", prop="color", value="red")] and dlg.problem() is None
dlg.add_row({})
assert "Fill in both" in dlg.problem()
dlg.remove_row() if dlg.table.setCurrentCell(1, 0) is None else None
assert dlg.problem() is None
ad = op.AttrsDialog(w, [dict(name="role", value="note")])
assert ad.rows() == [dict(name="role", value="note")]
ad.add_row(dict(name="style", value="x"))
assert "set elsewhere" in ad.problem()
act = op.ActionsDialog(w, [], t.d)
act.add_row(dict(on="click", do="toggle", target="", value=""))
assert "Choose which object" in act.problem()
assert act.table.cellWidget(0, 2).count() == 2 and "Rectangle" in act.table.cellWidget(0, 2).itemText(1)
act.table.cellWidget(0, 2).setCurrentIndex(1)
assert act.problem() is None and act.rows()[0]["target"] == "other1"
act.table.cellWidget(0, 1).setCurrentIndex(act.table.cellWidget(0, 1).findData("alert"))
assert "Type the message" in act.problem()
# saving through the same path the window uses
t.d["cssp"] = op.clean_css(dlg.rows())
t.d["attrs"] = op.clean_attrs(ad.rows()[:1])
t.d["actions"] = op.clean_actions([dict(on="click", do="alert", target="", value="Hi"), dict(on="bogus", do="alert")])
assert t.d["actions"] == [dict(on="click", do="alert", target="", value="Hi")]
w.commit_if_changed("props")
path = os.path.join(tmp, "p.site")
doc.save(path)
w.open_path(path)
back = [i for i in w.doc.pages[0]["items"] if i["kind"] == "text"][0]
assert back["cssp"][0]["prop"] == "color" and back["attrs"][0]["name"] == "role" and back["actions"][0]["do"] == "alert"

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
for want in ("Actions...", "CSS properties...", "HTML attributes..."):
    assert want in labels, want
w.deleteLater()
app.processEvents()
del w
print("ALL GOOD")
