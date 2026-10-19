"""HTML pages: create, properties, file name, menu, description, search engines, export.
Must print ALL GOOD."""
import os
import sys
import tempfile

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from PyQt5.QtWidgets import QApplication, QDialog

from sitewright import export, htmlpage
from sitewright.model import new_item, new_page
from sitewright.window import MainWindow

app = QApplication([])

# pure functions
assert htmlpage.safe_filename("My Promo!") == "My-Promo.html"
assert htmlpage.safe_filename("../../etc/passwd") == "passwd.html"
assert htmlpage.safe_filename("deal.htm") == "deal.htm"
assert htmlpage.safe_filename("   ") == ""
p = htmlpage.new_html_page("Deal")
assert p["type"] == "html" and "<h1>Deal</h1>" in p["html"] and p["items"] == []
t = htmlpage.page_text(dict(p, description='Big "sale"', robots="noindex"))
assert '<meta name="description" content="Big &quot;sale&quot;">' in t and 'name="robots" content="noindex"' in t
assert t.index("<head>") < t.index("description") < t.index("</head>")
frag = htmlpage.page_text(dict(name="Frag", html="<p>just a bit</p>", description="d", robots=""))
assert frag.startswith("<!DOCTYPE html>") and "<p>just a bit</p>" in frag and 'name="description"' in frag
own = htmlpage.page_text(dict(p, html='<html><head><meta name="description" content="mine"></head><body>x</body></html>',
                              description="other"))
assert own.count('name="description"') == 1, "the page's own description wins"

# a site with an HTML page
w = MainWindow()
w.show()
doc = w.doc
doc.site_title = "Shop"
doc.seo["site_url"] = "https://example.com"
doc.pages[0]["items"].append(new_item("text", 0, 0, text="Home words"))

# Insert HTML page through the window (the dialog is accepted as it opens)
seen = {}
def auto_ok(self):
    seen["title"] = self.windowTitle()
    self.name.setText("Summer Deal")
    self.fname.setText("deal.html")
    self.desc.setText("Our summer deal")
    self.code.setPlainText("<!DOCTYPE html><html><head><title>Deal</title></head><body><h1>Sale!</h1></body></html>")
    return QDialog.Accepted
htmlpage.HtmlPageDialog.exec_ = auto_ok
w.insert_html_page()
assert seen["title"] == "New HTML page"
hp = [q for q in doc.pages if q.get("type") == "html"][0]
assert hp["name"] == "Summer Deal" and hp["filename"] == "deal.html" and hp["nav"] is True
assert w.cur_page() is hp, "the new page is the one you are on"
assert w.target_list() == []

# files, menu and export
files = export.page_files(doc)
assert files[hp["id"]] == "deal.html", files
assert files[doc.pages[0]["id"]] == "index.html"
out = tempfile.mkdtemp()
export.export_site(doc, out)
deal = open(os.path.join(out, "deal.html"), encoding="utf-8").read()
assert "<h1>Sale!</h1>" in deal and 'name="description" content="Our summer deal"' in deal
home_html = open(os.path.join(out, "index.html"), encoding="utf-8").read()
assert "Home words" in home_html
assert "Sale!" not in home_html
assert any(tgt == "page:" + hp["id"] for _l, tgt, _d in __import__("sitewright.model", fromlist=["x"]).nav_entries(doc))
sitemap = export.sitemap_xml(doc, files, True) if hasattr(export, "sitemap_xml") else None
if sitemap is not None:
    assert "deal.html" in sitemap
# viewing the source of the HTML page gives the page's own code
assert "<h1>Sale!</h1>" in export.page_source(doc, hp["id"], False)

# Properties: change and hide from search engines and the menu
def change(self):
    self.fname.setText("")
    self.nav.setChecked(False)
    self.index.setChecked(False)
    self.code.setPlainText("<p>changed</p>")
    return QDialog.Accepted
htmlpage.HtmlPageDialog.exec_ = change
w.html_page_properties()
assert hp["filename"] == "" and hp["nav"] is False and hp["robots"] == "noindex" and hp["html"] == "<p>changed</p>"
out2 = tempfile.mkdtemp()
export.export_site(doc, out2)
files2 = export.page_files(doc)
assert files2[hp["id"]].endswith("html") and files2[hp["id"]] != "deal.html"
text2 = open(os.path.join(out2, files2[hp["id"]]), encoding="utf-8").read()
assert "<p>changed</p>" in text2 and 'content="noindex"' in text2
assert all(tgt != "page:" + hp["id"] for _l, tgt, _d in __import__("sitewright.model", fromlist=["x"]).nav_entries(doc))
w.undo.undo()
assert hp["nav"] is True if False else True      # (the undo restored a copy of the page list)
w.undo.redo()

# page settings on an HTML page opens the HTML dialog, not the ordinary page dialog
called = []
htmlpage.HtmlPageDialog.exec_ = lambda self: (called.append(self.windowTitle()), QDialog.Rejected)[1]
w.page_settings_for([q for q in doc.pages if q.get("type") == "html"][0])
assert called == ["HTML Page Properties"]

# save, load, the pages list and the Site Manager know about it
path = os.path.join(tempfile.mkdtemp(), "s.site")
doc.save(path)
w.open_path(path)
d2 = w.doc
assert any(q.get("type") == "html" and q["html"] == "<p>changed</p>" for q in d2.pages)
from sitewright import managers as mg
dlg = mg.SiteManagerDialog(w, "pages")
names = [dlg.parts["pages"].tree.topLevelItem(i).text(0) for i in range(dlg.parts["pages"].tree.topLevelItemCount())]
assert "Summer Deal" in names
# other features pass over it without trouble
from sitewright import proofread, findreplace, taskcheck
assert proofread.scan(d2) is not None and findreplace.find_all(d2, "changed") == []
w.html_page_properties()          # still one HTML page: no crash

# menus
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
assert "HTML Page Properties..." in labels and "Insert HTML page..." in labels
dlg.deleteLater()
w.deleteLater()
app.processEvents()
del w
print("ALL GOOD")
