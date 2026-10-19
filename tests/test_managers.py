"""Site Manager (links, fonts, files, text, pages) and the Master Page Manager.
Must print ALL GOOD."""
import base64
import os
import sys
import tempfile

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from PyQt5.QtCore import QRectF
from PyQt5.QtGui import QColor, QImage
from PyQt5.QtWidgets import QApplication

from sitewright import export, managers as mg
from sitewright.canvas import ItemObj
from sitewright.model import new_item, new_page
from sitewright.window import MainWindow

app = QApplication([])
w = MainWindow()
w.show()
doc = w.doc
home = doc.pages[0]
about = new_page("About")
doc.pages.append(about)
doc.pages.append(new_page("Shop", type="link", url="https://old-shop.example.com/store"))
ident = new_item("rect", 0, 0)
ident["ident"] = "top"
home["items"] += [
    new_item("text", 0, 0, text="Hello home", font="Georgia", link="page:" + about["id"]),
    new_item("button", 0, 80, text="Gone", font="Arial", link="page:deadbeef"),
    new_item("button", 0, 160, text="Web", font="Comic Neue Sans", link="https://example.com/a"),
    new_item("text", 0, 240, text="mail", link="mailto:me@example.com"),
    new_item("text", 0, 300, text="badmail", link="mailto:nonsense"),
    new_item("text", 0, 340, text="anchor ok", link="anchor:%s#top" % home["id"]),
    new_item("text", 0, 380, text="anchor gone", link="anchor:%s#nowhere" % home["id"]),
    new_item("text", 0, 420, text="partial", link="http://x"),
    ident]
sl = new_item("slider", 0, 500)
sl["panels"][0]["link"] = "page:" + about["id"]
home["items"].append(sl)
doc.master.append(new_item("text", 0, 0, text="Logo", font="Georgia", link="https://example.com/logo"))
w.reload()

# ---- hyperlinks
refs = mg.links(doc)
labels = [r.label for r in refs]
assert len(refs) >= 11, len(refs)
assert any(r.label.startswith("Offsite link") for r in refs) and any("Slider panel 1" in l for l in labels)
st = {r.holder.get(r.key): mg.status(r.holder.get(r.key), doc) for r in refs}
assert st["page:" + about["id"]] == "ok"
assert st["page:deadbeef"] == "The page was deleted"
assert st["https://example.com/a"] == "web"
assert st["mailto:me@example.com"] == "ok" and st["mailto:nonsense"] == "Not an email address"
assert st["anchor:%s#top" % home["id"]] == "ok"
assert st["anchor:%s#nowhere" % home["id"]] == "The anchor is gone"
assert st["http://x"] == "Not a full web address"
assert mg.describe("page:" + about["id"], doc) == 'Page "About"'
assert mg.describe("page:deadbeef", doc).startswith("(a page that was deleted")
assert mg.check_web("https://example.com", opener=lambda req, timeout: type("R", (), {"status": 200, "__enter__": lambda s: s, "__exit__": lambda s, *a: None})()) == "ok"
assert mg.check_web("https://nope.invalid", opener=lambda req, timeout: (_ for _ in ()).throw(OSError("no network"))).startswith("Could not reach")

n = mg.replace_in_links(doc, "example.com", "newsite.org")
assert n >= 3
assert any(r.holder.get(r.key) == "https://newsite.org/a" for r in mg.links(doc))
assert any(r.holder.get(r.key) == "https://old-shop.newsite.org/store" for r in mg.links(doc))
r0 = [r for r in mg.links(doc) if r.holder.get(r.key) == "page:deadbeef"][0]
mg.set_link(r0, "page:" + home["id"])
assert mg.status(r0.holder[r0.key], doc) == "ok"

# the dialog tabs
dlg = mg.SiteManagerDialog(w, "links")
assert dlg.tabs.currentIndex() == 1
lt = dlg.parts["links"]
assert lt.tree.topLevelItemCount() == len(mg.links(doc))
lt.problems.setChecked(True)
assert 0 < lt.tree.topLevelItemCount() < len(mg.links(doc))
assert all(lt.state(r) not in ("ok",) for r in lt.entries)
lt.problems.setChecked(False)
lt.web.clear()
lt.check_all(opener=lambda req, timeout: type("R", (), {"status": 200, "__enter__": lambda s: s, "__exit__": lambda s, *a: None})())
assert all(v == "ok" for v in lt.web.values()) and lt.web

# ---- fonts
use = mg.font_usage(doc)
assert use["Georgia"][0] == 2 and "Master page" in use["Georgia"][1]
assert use["Comic Neue Sans"][0] == 1
ft = dlg.parts["fonts"]
ft.refresh()
shown = {ft.tree.topLevelItem(i).text(0): ft.tree.topLevelItem(i) for i in range(ft.tree.topLevelItemCount())}
assert shown["Arial"].text(3) == "yes" and shown["Comic Neue Sans"].text(3).startswith("no")
assert mg.substitute_font(doc, "Comic Neue Sans", "Verdana") == 1
assert "Comic Neue Sans" not in mg.font_usage(doc) and mg.font_usage(doc)["Verdana"][0] == 1

# ---- files
img = QImage(30, 20, QImage.Format_RGB32)
img.fill(QColor("#c33"))
tmp = tempfile.mkdtemp()
png = os.path.join(tmp, "red.png")
img.save(png)
used_id = doc.add_asset(png)
free_id = doc.add_asset(png)
home["items"].append(new_item("image", 0, 600, asset=used_id))
usage = mg.file_usage(doc)
assert "Home" in usage[used_id] or home["name"] in usage[used_id]
assert free_id not in usage
assert mg.asset_kb(doc, used_id) > 0
out = os.path.join(tmp, "copy.png")
mg.save_asset(doc, used_id, out)
assert open(out, "rb").read() == base64.b64decode(doc.assets[used_id]["data"])
blue = QImage(30, 20, QImage.Format_RGB32)
blue.fill(QColor("#33c"))
bp = os.path.join(tmp, "blue.png")
blue.save(bp)
mg.replace_asset(doc, used_id, bp)
assert doc.assets[used_id]["name"] == "blue.png"
assert mg.delete_unused(doc) == 1 and free_id not in doc.assets and used_id in doc.assets
dlg.parts["files"].refresh()
assert dlg.parts["files"].tree.topLevelItemCount() == len(doc.assets)

# ---- text
rows = mg.text_rows(doc)
assert any(f.item.get("text") == "Hello home" for f, _t in rows)
assert mg.word_count("Hello there, world's end") == 4
tt = dlg.parts["text"]
tt.refresh()
assert tt.tree.topLevelItemCount() == len(rows)
tt.find.setText("hello")
assert tt.tree.topLevelItemCount() == 1
tt.find.setText("")
f0 = [f for f, _t in mg.text_rows(doc) if f.cont.get("text") == "Hello home"][0]
f0.cont[f0.key] = "Edited home"
assert any(t == "Edited home" for _f, t in mg.text_rows(doc))
assert mg.go_to(w, f0.page_index, f0.item)

# ---- pages tab
pt = dlg.parts["pages"]
pt.refresh()
assert pt.tree.topLevelItemCount() == len(doc.pages)
assert pt.tree.topLevelItem(0).text(4) == "Master page"

# ---- master pages
assert [m[1] for m in doc.all_masters()] == ["Master page"]
mid = mg.add_master(doc, "Landing")
assert [m[1] for m in doc.all_masters()] == ["Master page", "Landing"]
doc.master_list(mid).append(new_item("text", 0, 0, text="Landing banner"))
mg.assign_master(doc, mid, {about["id"]})
assert about["master"] == mid
assert [i["text"] for i in doc.master_items(about)] == ["Landing banner"]
assert [i["text"] for i in doc.master_items(home)] == ["Logo"]
assert doc.master_items(dict(home, master=False)) == []
assert mg.master_users(doc, mid) == ["About"] and "Home" in mg.master_users(doc, "")
# the published page uses its own master page
html_ = export.page_source(doc, about["id"], False)
assert "Landing banner" in html_ and "Logo" not in html_
assert "Logo" in export.page_source(doc, home["id"], False)
# duplicate, rename, save/load, undo
mid2 = mg.duplicate_master(doc, mid)
assert mg.rename_master(doc, mid2, "Landing 2")
assert not mg.rename_master(doc, "", "x")
w.commit_if_changed("masters")
path = os.path.join(tmp, "m.site")
doc.save(path)
w.open_path(path)
d2 = w.doc
assert [m[1] for m in d2.all_masters()] == ["Master page", "Landing", "Landing 2"]
assert [i["text"] for i in d2.master_items(d2.pages[1])] == ["Landing banner"]
# editing a chosen master page puts its objects in the editor
w.page_index = 1
w.reload()
w.edit_master(d2.masters[0]["id"])
assert w.master_mode and [i["text"] for i in w.target_list()] == ["Landing banner"]
w.master_btn.setChecked(False)
assert not w.master_mode
# delete: pages go back to the main master page
assert mg.delete_master(d2, d2.masters[0]["id"]) == 1
assert d2.pages[1]["master"] is True and [m[1] for m in d2.all_masters()] == ["Master page", "Landing 2"]
assert mg.delete_master(d2, "nothing") == -1

# page settings has a master page choice; the master manager dialog lists them
from sitewright.window import PageDialog
pd = PageDialog(w, d2.pages[0], d2)
assert [pd.master.itemText(i) for i in range(pd.master.count())] == ["No master page", "Master page", "Landing 2"]
mm = mg.MasterManagerDialog(w)
assert mm.tree.topLevelItemCount() == 2
mm.deleteLater()

labels2 = []
def walk(m):
    for a in m.actions():
        if a.menu():
            walk(a.menu())
        else:
            labels2.append(a.text().replace("&", ""))
for a in w.menuBar().actions():
    if a.menu():
        walk(a.menu())
for want in ("Hyperlink Manager...", "Font Manager...", "File Manager...", "Text Manager...",
             "Master Page Manager..."):
    assert want in labels2, want
dlg.deleteLater()
w.deleteLater()
app.processEvents()
del w
print("ALL GOOD")
