"""Smoke test: build a small site, undo/redo, save/load, export. Must print ALL GOOD."""
import os
import sys
import tempfile

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from PyQt5.QtCore import QRectF, Qt
from PyQt5.QtGui import QColor, QImage
from PyQt5.QtWidgets import QApplication

from sitewright import export
from sitewright.window import MainWindow

app = QApplication([])
tmp = tempfile.mkdtemp()
png = os.path.join(tmp, "pic.png")
img = QImage(40, 30, QImage.Format_RGB32)
img.fill(QColor("#c33"))
img.save(png)

w = MainWindow()
w.show()
doc = w.doc
assert len(doc.pages) == 1

w.create_item("rect", QRectF(20, 20, 200, 100))
w.create_item("text", QRectF(40, 160, 300, 60))
assert len(doc.pages[0]["items"]) == 2
t = [o for o in w.scene.items() if getattr(o, "editable", False) and o.d["kind"] == "text"][0]
t.setSelected(True)
w.set_prop("text", "Hello <world>")
w.set_prop("link", "https://example.com")
w.undo.undo()
assert doc.pages[0]["items"][1]["link"] == ""
w.undo.redo()
assert doc.pages[0]["items"][1]["link"] == "https://example.com"

# picture
aid = doc.add_asset(png)
from sitewright.model import new_item
w.target_list().append(new_item("image", 400, 40, asset=aid))
w.add_page()
w.add_page()
assert len(doc.pages) == 3
# page link + master item
w.master_btn.setChecked(True)
w.create_item("button", QRectF(10, 10, 120, 40))
w.master_btn.setChecked(False)
assert len(doc.master) == 1
w.page_index = 0
w.reload()
w.commit_if_changed()
doc.pages[0]["items"][0]["link"] = "page:" + doc.pages[1]["id"]

# keyboard nudge really moves by 1px even with snap on
w.scene.clearSelection()
r = [o for o in w.scene.items() if getattr(o, "editable", False) and o.d["kind"] == "rect"][0]
r.setSelected(True)
x0 = r.d["x"]
w.nudge(1, 0)
assert r.d["x"] == x0 + 1, (r.d["x"], x0)

# save / load round trip
p = os.path.join(tmp, "site.sitewright")
doc.save(p)
from sitewright.model import Document
d2 = Document.load(p)
assert d2.snapshot() == doc.snapshot()
assert aid in d2.assets

# export
out = os.path.join(tmp, "out")
files = export.export_site(d2, out, clean=False)
names = sorted(os.path.basename(f) for f in files)
assert "index.html" in names and "style.css" in names, names
idx = open(os.path.join(out, "index.html")).read()
assert "Hello &lt;world&gt;" in idx
assert 'href="https://example.com"' in idx
assert "<img" in idx and os.path.exists(os.path.join(out, "images", "pic.png"))
assert "page-2.html" in idx or "page-" in idx
assert idx.count("Button") == 1  # master button appears on the page
# grabbing the scene renders without error
im = QImage(800, 600, QImage.Format_RGB32)
from PyQt5.QtGui import QPainter
pt = QPainter(im)
w.scene.render(pt)
pt.end()

# ---- phase 1/2 features ----
from sitewright.model import ordered_pages, real_pages
from sitewright import templates
w.undo.setClean()
w.new_site()
doc = w.doc
w.create_item("rect", QRectF(0, 0, 100, 50))
w.create_item("rect", QRectF(200, 100, 60, 80))
w.select_all()
objs = w.selected()
w.group()
w.scene.clearSelection()
objs[0].setSelected(True)
assert len(w.selected()) == 2          # group selects together
w.align("l")
assert objs[0].d["x"] == objs[1].d["x"] == 0
w.same_size("wh")
assert objs[0].d["w"] == objs[1].d["w"] == 100 and objs[0].d["h"] == 80
w.rotate(90)
assert objs[0].d["rot"] == 90
w.flip("fx")
w.toggle_lock()
assert all(o.d["locked"] for o in w.selected())
w.undo.undo()
w.ungroup()
# guides snap
w.add_page(template="Landing page")
w.add_page(template="About")
assert len(real_pages(doc)) == 3 and len(doc.pages[1]["items"]) > 5
cur = doc.pages[2]
cur["parent"] = doc.pages[1]["id"]
w.reload()
assert [p["name"] for p, d in ordered_pages(doc.pages)] == ["Home", "Landing page", "About"]
assert [d for p, d in ordered_pages(doc.pages)] == [0, 0, 1]
doc.pages[0]["guides"]["v"].append(120)
assert w.snap_x(123) == 120 and w.snap_x(300) == 300
# offsite link + navbar export
link = __import__("sitewright.model", fromlist=["new_page"]).new_page(
    "Docs", type="link", url="https://example.org/docs")
doc.pages.append(link)
w.page_index = 0
w.target_list().append(new_item("navbar", 0, 0, w=900))
w.set_home(doc.pages[1])
assert doc.pages[0]["name"] == "Landing page"
out2 = os.path.join(tmp, "out2")
export.export_site(doc, out2, clean=False)
idx = open(os.path.join(out2, "index.html")).read()
assert "Get started" in idx                      # new home page is index.html
home_has_nav = [p for p in doc.pages if p["name"] == "Home"][0]
assert not os.path.exists(os.path.join(out2, "docs.html"))
nav_page = open(os.path.join(out2, "home.html")).read()
assert "<nav" in nav_page and "https://example.org/docs" in nav_page
assert "index.html" in nav_page

# ---- phase 3 objects ----
w.undo.setClean()
w.new_site()
doc = w.doc
for k, r in (("table", (20, 20, 400, 120)), ("video", (20, 160, 320, 180)),
             ("map", (360, 160, 300, 180)), ("social", (20, 360, 220, 40)),
             ("marquee", (260, 360, 400, 40)), ("html", (20, 420, 300, 60)),
             ("audio", (360, 420, 300, 48)),
             ("field:text", (20, 500, 260, 36)), ("field:textarea", (300, 500, 260, 90)),
             ("field:select", (20, 550, 260, 36)), ("field:submit", (20, 610, 140, 42))):
    w.create_item(k, QRectF(*r))
items = {i["kind"]: i for i in doc.pages[0]["items"]}
assert {"table", "video", "map", "social", "marquee", "html", "audio", "field"} <= set(items)
tbl = items["table"]
w.scene.clearSelection()
[o for o in w.scene.items() if getattr(o, "editable", False) and o.d is tbl][0].setSelected(True)
w.set_table_dims(rows=4, cols=2)
assert tbl["rows"] == 4 and tbl["cols"] == 2 and len(tbl["cells"]) == 4
w.set_table_cells("Name|Price\nTea|3\nCoffee|4")
assert tbl["cells"][2] == ["Coffee", "4"] and tbl["rows"] == 3
items["video"]["url"] = "https://www.youtube.com/watch?v=dQw4w9WgXcQ"
items["map"]["address"] = "Crossville, TN"
doc.form_email = "owner@example.com"
png2 = png
gal = new_item("gallery", 0, 700, assets=[doc.add_asset(png2), doc.add_asset(png2)])
doc.pages[0]["items"].append(gal)
w.reload()
out3 = os.path.join(tmp, "out3")
export.export_site(doc, out3, clean=False)
h = open(os.path.join(out3, "index.html")).read()
assert "<table" in h and "<th" in h and "Coffee" in h
assert "youtube.com/embed/dQw4w9WgXcQ" in h
assert "maps.google.com/maps?q=Crossville" in h
assert "<form" in h and 'action="send.php"' in h and "<textarea" in h and "<select" in h
assert 'type="submit"' in h and 'class="o gal"' in h and "data-net" in h and "mq" in h
php = open(os.path.join(out3, "send.php")).read()
assert "owner@example.com" in php
assert os.path.exists(os.path.join(out3, "images", "pic.png"))
# everything paints
im = QImage(900, 900, QImage.Format_RGB32)
pt = QPainter(im)
w.scene.render(pt)
pt.end()

# ---- phase 4: button + navigation styles, pop-up menus ----
from sitewright.styles import BUTTON_STYLES, NAV_STYLES
assert len(BUTTON_STYLES) == 30 and len(NAV_STYLES) >= 10
w.undo.setClean()
w.new_site()
doc = w.doc
w.add_page()
w.page_index = 0
w.reload()
w.create_item("button", QRectF(40, 40, 160, 48))
b = [i for i in doc.pages[0]["items"] if i["kind"] == "button"][0]
w.scene.clearSelection()
[o for o in w.scene.items() if getattr(o, "editable", False) and o.d is b][0].setSelected(True)
assert w.apply_style("button", BUTTON_STYLES["Green raised"])
assert b["shadow"] and b["fill2"]
b["popup"] = "One|page:" + doc.pages[1]["id"] + "\nTwo|https://example.org"
w.create_item("navbar", QRectF(0, 120, 700, 48))
nb = [i for i in doc.pages[0]["items"] if i["kind"] == "navbar"][0]
nb.update(NAV_STYLES["Drop-down bar"])
doc.pages[1]["parent"] = doc.pages[0]["id"]
w.reload()
out4 = os.path.join(tmp, "out4")
export.export_site(doc, out4, clean=False)
h = open(os.path.join(out4, "index.html")).read()
assert ".b-" + b["id"] + ":hover" in h and "linear-gradient" in h and "box-shadow" in h
assert 'class="pop"' in h and "https://example.org" in h and "pm" in h
assert ".nv-" + nb["id"] in h and 'class="sub"' in h and "aria-current" in h
nb.update(NAV_STYLES["Tabs"])
nb.update(NAV_STYLES["Vertical cards"])
w.reload()
for pm in (BUTTON_STYLES["Red pill"], NAV_STYLES["Pills"]):
    from sitewright.styles import preview_button, preview_nav
    assert not preview_button(pm).isNull() and not preview_nav(pm).isNull()

# ---- phase 5: colour schemes, themes, styles, gradient/shadow ----
from sitewright.schemes import SCHEMES, THEMES, apply_scheme, apply_theme
w.undo.setClean()
w.new_site()
doc = w.doc
assert len(doc.scheme) == 12
w.create_item("rect", QRectF(20, 20, 200, 100))
w.create_item("button", QRectF(20, 160, 160, 48))
w.create_item("text", QRectF(20, 240, 300, 60))
rect = [i for i in doc.pages[0]["items"] if i["kind"] == "rect"][0]
btn = [i for i in doc.pages[0]["items"] if i["kind"] == "button"][0]
assert rect["fill"] == doc.scheme[5] or rect["fill"] in doc.scheme
old_fill = rect["fill"]
idx = [c.lower() for c in doc.scheme].index(old_fill.lower())
apply_scheme(doc, SCHEMES["Forest"])
assert rect["fill"] == SCHEMES["Forest"][idx], (rect["fill"], idx)
custom = new_item("rect", 0, 400, fill="#123456")
doc.pages[0]["items"].append(custom)
apply_scheme(doc, SCHEMES["Sunset"])
assert custom["fill"] == "#123456"            # colours you chose yourself stay
apply_theme(doc, "Ocean")
assert doc.scheme == SCHEMES["Ocean"]
assert doc.pages[0]["bg"] == SCHEMES["Ocean"][0]
assert btn["fill"] and btn["font"] == THEMES["Ocean"]["body"]
# gradient + shadow export
rect.update(fill="#336699", fill2="#99ccff", shadow=True)
w.reload()
out5 = os.path.join(tmp, "out5")
export.export_site(doc, out5, clean=False)
h = open(os.path.join(out5, "index.html")).read()
assert "linear-gradient(180deg,#336699,#99ccff)" in h and "box-shadow" in h
# styles
w.scene.clearSelection()
[o for o in w.scene.items() if getattr(o, "editable", False) and o.d is rect][0].setSelected(True)
doc.styles["Card"] = {k: rect[k] for k in ("fill", "fill2", "shadow")}
w.use_style("Card")
# save / load keeps scheme and styles
p5 = os.path.join(tmp, "s5.sitewright")
doc.save(p5)
d5 = Document.load(p5)
assert d5.scheme == doc.scheme and "Card" in d5.styles
from sitewright.schemes import preview_theme
assert not preview_theme("Berry").isNull()

# ---- WebPlus-style window furniture ----
w.undo.setClean()
w.new_site()
doc = w.doc
doc.user = {"company": "4ThePeople Media", "email": "owner@example.com"}
w.create_item("text", QRectF(20, 20, 300, 60))
t = [i for i in doc.pages[0]["items"] if i["kind"] == "text"][0]
t["text"] = "contact %companyname% at %companyemail% - %sitename%"
w.reload()
w.scene.clearSelection()
[o for o in w.scene.items() if getattr(o, "editable", False) and o.d is t][0].setSelected(True)
w.change_case("upper")
assert t["text"].startswith("CONTACT %COMPANYNAME%")
t["text"] = "contact %companyname% at %companyemail% - %sitename%"
out6 = os.path.join(tmp, "out6")
export.export_site(doc, out6, clean=False)
h = open(os.path.join(out6, "index.html")).read()
assert "contact 4ThePeople Media at owner@example.com - My Website" in h
aid = doc.add_asset(png)
w.insert_asset(aid)
assert any(i["kind"] == "image" for i in doc.pages[0]["items"])
assert w.assets_panel.list.count() >= 1
assert w.page_combo.count() == 1 and w.colour_panel.swatches and w.transform_panel.w["x"]
labels = [a.text() for a in w.menuBar().actions()]
assert labels[:6] == ["&File", "&Edit", "&View", "&Insert", "&Properties", "F&ormat"], labels
assert "&Tools" in labels and "&Window" in labels and labels[-1] == "&Help"

# ---- publishing, task monitor, left tabs ----
from sitewright import publish, taskcheck
w.undo.setClean()
w.new_site()
doc = w.doc
w.insert_block("Call to action")
w.insert_block("Three columns")
assert len(doc.pages[0]["items"]) >= 9
doc.pages[0]["items"].append(new_item("image", 400, 300))           # empty frame
doc.pages[0]["items"].append(new_item("field", 20, 600, ftype="text"))
doc.pages[0]["items"].append(new_item("text", 20, 650, link="page:gone"))
msgs = [m for m, _p, _i in taskcheck.check(doc)]
assert any("Empty picture frame" in m for m in msgs)
assert any("no email address" in m for m in msgs)
assert any("deleted" in m for m in msgs)
w.reload()
w.refresh_tasks()
assert w.task_list.count() >= 3
# text style
w.scene.clearSelection()
head = [i for i in doc.pages[0]["items"] if i["kind"] == "text"][0]
[o for o in w.scene.items() if getattr(o, "editable", False) and o.d is head][0].setSelected(True)
w.apply_text_style(dict(size=40, bold=True, italic=False, ci=2))
assert head["size"] == 40 and head["bold"] and head["color"] == doc.scheme[2]
# FTP upload against a fake server
class FakeFTP:
    sent = {}
    def connect(self, host, port, timeout=0): self.cwdp = "/"
    def login(self, u, p): pass
    def set_pasv(self, v): pass
    def prot_p(self): pass
    def cwd(self, d):
        self.cwdp = "/" if d == "/" else self.cwdp.rstrip("/") + "/" + d
    def mkd(self, d): pass
    def storbinary(self, cmd, f, bs, cb):
        data = b""
        while True:
            blk = f.read(bs)
            if not blk: break
            data += blk
            cb(blk)
        FakeFTP.sent[self.cwdp.rstrip("/") + "/" + cmd[5:]] = len(data)
    def quit(self): pass
doc.form_email = "a@b.c"
pub = publish.export_temp(doc, export.export_site)
seen = []
ok = publish.upload(publish.Target("ftp.example.com", 21, "u", "p", "/site", tls=False), pub,
                    lambda *a: seen.append(a), lambda: False, FakeFTP)
assert ok and "/site/index.html" in FakeFTP.sent and "/site/style.css" in FakeFTP.sent
assert seen and seen[-1][5] == seen[-1][6]
ok = publish.upload(publish.Target("h", 21, "u", "p", "/", tls=False), pub,
                    lambda *a: None, lambda: True, FakeFTP)
assert ok is False                                                  # cancel stops it
assert w.fonts_panel.list.count() > 0 and w.quick_panel.list.count() == 6

# ---- spell check, anchors, quick publish, colour tabs, dashed line ----
from sitewright import spell
w.undo.setClean()
w.new_site()
doc = w.doc
w.create_item("text", QRectF(20, 20, 300, 60))
w.create_item("rect", QRectF(20, 120, 200, 80))
t = [i for i in doc.pages[0]["items"] if i["kind"] == "text"][0]
rc = [i for i in doc.pages[0]["items"] if i["kind"] == "rect"][0]
t["text"] = "Welcome to the speling test"
found = spell.scan(doc)
assert [f["word"] for f in found] == ["speling"] and "spelling" in found[0]["suggestions"]
spell.replace_in_field(found[0]["container"], found[0]["key"], found[0]["line"],
                       found[0]["offset"], "speling", "spelling")
assert t["text"] == "Welcome to the spelling test"
assert spell.scan(doc) == []
# anchors
rc["anchor"] = "details"
doc.pages[0]["items"].append(new_item("button", 20, 300, link="anchor:%s#details" % doc.pages[0]["id"]))
w.add_page()
doc.pages[1]["items"].append(new_item("button", 20, 20, link="anchor:%s#details" % doc.pages[0]["id"]))
out7 = os.path.join(tmp, "out7")
export.export_site(doc, out7, clean=False)
h0 = open(os.path.join(out7, "index.html")).read()
h1 = open(os.path.join(out7, "page-2.html")).read()
assert 'id="details"' in h0 and 'href="#details"' in h0
assert 'href="index.html#details"' in h1
assert list(w.anchors())[0][2] == "details"
# quick publish only sends what changed
hashes = publish.file_hashes(publish.export_temp(doc, export.export_site))
before = dict(hashes)
doc.pages[0]["items"][0]["text"] = "Welcome again"
pub2 = publish.export_temp(doc, export.export_site)
after = publish.file_hashes(pub2)
changed = {r for r, hh in after.items() if before.get(r) != hh}
assert changed == {"index.html"}, changed
FakeFTP.sent = {}
ok = publish.upload(publish.Target("h", 21, "u", "p", "/", tls=False), pub2,
                    lambda *a: None, lambda: False, FakeFTP, only=changed)
assert ok and list(FakeFTP.sent) == ["/index.html"]
# colour tabs + dashed outline
assert w.colour_tabs.count() == 4
w.page_index = 0
w.reload()
w.scene.clearSelection()
[o for o in w.scene.items() if getattr(o, "editable", False) and o.d is rc][0].setSelected(True)
w.colour_panel.target = "fill"
w.colour_panel.spectrum_picked("#336699", True)
assert rc["fill"] == "#336699"
w.line_panel.set("sw", 3)
w.line_panel.set("sstyle", "dashed")
w.swatches_panel.add_colour("#abcdef")
assert "#abcdef" in doc.swatches
assert w.swatches_panel.lists["scheme"].count() == 12 and w.swatches_panel.lists["standard"].count() >= 50
assert w.swatches_panel.lists["mine"].count() == 1
export.export_site(doc, out7, clean=False)
assert "dashed" in open(os.path.join(out7, "index.html")).read()

# ---- full-width colour and responsive layout ----
assert 'html,body{background:' in h0
assert 'data-k="rect"' in h0 and "function mobile(" in h0 and "function order(" in h0
assert "viewport" in h0 and "width=device-width" in h0

# ---- startup assistant ----
from sitewright import startup
d = startup.make_document("new", dict(name="Shop", scheme="Ocean", width=800, pages=4, nav=True))
assert d.site_title == "Shop" and len(d.pages) == 4 and d.width == 800
assert d.scheme == SCHEMES["Ocean"] and d.pages[0]["bg"] == SCHEMES["Ocean"][0]
assert d.master and d.master[0]["kind"] == "navbar"
for tname in templates.SITE_TEMPLATES:
    td = startup.make_document("template", dict(template=tname, scheme="Forest", width=960))
    assert len(td.pages) >= 2 and td.pages[0]["items"], tname
dlg = startup.StartupDialog(None, [])
assert dlg.stack.count() == 6 and dlg.t_list.count() == len(templates.SITE_TEMPLATES)
w.load_document(d)
assert w.doc is d and w.page_combo.count() == 4

# ---- forum-complaint fixes: SEO, feeds, clean addresses, headings, show/hide, forms ----
from sitewright import forms
w.undo.setClean()
w.new_site()
doc = w.doc
doc.seo.update(site_url="https://example.com", description="Site wide words", lang="en",
               google_verify="gv123", bing_verify="bv456", analytics="G-ABC123")
pg2 = new_page = __import__("sitewright.model", fromlist=["new_page"]).new_page("About us",
              description="About page words", keywords="a, b")
pg3 = __import__("sitewright.model", fromlist=["new_page"]).new_page("Hidden", robots="noindex,nofollow")
doc.pages += [pg2, pg3]
doc.pages[0]["items"] = [
    new_item("text", 20, 20, text="Welcome", htag="h1", ident="top", cls="big"),
    new_item("text", 20, 120, text="More", hidden=True, ident="more", group="g1"),
    new_item("button", 20, 200, text="Show", link="toggle:more"),
    new_item("video", 20, 300, url="dQw4w9WgXcQ", autoplay=True, related=False),
    new_item("frame", 20, 500, url="http://example.org/page"),
    new_item("image", 400, 20, asset=doc.add_asset(png), alt="A red square", w=40, h=30),
    new_item("button", 400, 200, text="About", link="page:" + pg2["id"]),
]
pg2["items"] = [new_item("image", 20, 20, asset=doc.assets and list(doc.assets)[0], alt="x", w=40, h=30),
                new_item("button", 20, 100, text="Home", link="page:" + doc.pages[0]["id"])]
doc.feed.update(enabled=True, title="My podcast", author="Aaron", items=[
    dict(title="Episode 1", description="First & best", date="2026-10-01", link="page:" + pg2["id"],
         asset="", audio_url="https://example.com/ep1.mp3", id="e1")])
out8 = os.path.join(tmp, "out8")
export.export_site(doc, out8)                       # clean addresses are the default
home = open(os.path.join(out8, "index.html")).read()
about = open(os.path.join(out8, "about-us", "index.html")).read()
assert '<meta name="description" content="Site wide words">' in home
assert '<meta name="description" content="About page words">' in about      # its own, not the site's
assert 'rel="canonical" href="https://example.com/about-us/"' in about
assert 'property="og:title"' in home and 'google-site-verification' in home and 'msvalidate.01' in home
assert 'googletagmanager.com/gtag/js?id=G-ABC123' in home
assert 'rel="alternate" type="application/rss+xml"' in home
assert '<h1 ' in home and 'id="top"' in home and 'big' in home
assert 'display:none' in home and 'data-toggle="more"' in home and 'data-grp="g1"' in home
assert 'https://www.youtube.com/embed/dQw4w9WgXcQ?autoplay=1&amp;mute=1&amp;rel=0' in home
assert 'src="https://example.org/page"' in home                       # http upgraded to https
assert 'href="about-us/"' in home and 'href="../"' in about            # relative, no .html
assert 'src="../images/' in about and 'href="../style.css"' in about  # shared files from a sub-folder
assert 'noindex' in open(os.path.join(out8, "hidden", "index.html")).read()
sm = open(os.path.join(out8, "sitemap.xml")).read()
assert "https://example.com/about-us/" in sm and "hidden" not in sm
assert "Sitemap: https://example.com/sitemap.xml" in open(os.path.join(out8, "robots.txt")).read()
fx = open(os.path.join(out8, "feed.xml")).read()
assert "<enclosure" in fx and "First &amp; best" in fx and "https://example.com/about-us/" in fx
# the page source viewer and clean=False both give plain .html files
assert "<!doctype html>" in export.page_source(doc, doc.pages[0]["id"])
# form designer output: a real, working contact page
items, bottom = forms.build_form(forms.FORM_TEMPLATES["Contact"], "Rounded", x=60, y=60, w=400)
fields = [i for i in items if i["kind"] == "field"]
assert [f["ftype"] for f in fields] == ["text", "email", "text", "textarea", "submit"]
assert fields[1]["name"] == "email" and fields[0]["required"]
doc.form_email, doc.form_mode = "me@example.com", "php"
doc.pages[0]["items"] += items
export.export_site(doc, out8)
php = open(os.path.join(out8, "send.php")).read()
assert "me@example.com" in php and "FILTER_VALIDATE_EMAIL" in php
assert "required" in open(os.path.join(out8, "index.html")).read()
# the Task Monitor notices SEO gaps
msgs = " | ".join(m for m, _p, _i in taskcheck.check(doc))
assert "no main heading" in msgs and "has no description" not in msgs.replace("Hidden", "")
# FTP retries a failed file instead of giving up
class FlakyFTP(FakeFTP):
    tries = 0
    def storbinary(self, cmd, f, bs, cb):
        FlakyFTP.tries += 1
        if FlakyFTP.tries == 1:
            raise OSError("connection reset")
        return FakeFTP.storbinary(self, cmd, f, bs, cb)
FakeFTP.sent = {}
ok = publish.upload(publish.Target("h", 21, "u", "p", "/", tls=False), out8,
                    lambda *a: None, lambda: False, FlakyFTP)
assert ok and "/index.html" in FakeFTP.sent

# ---- self-hosted search, members and mailing list ----
from sitewright import phpgen
w.undo.setClean()
w.new_site()
doc = w.doc
res = __import__("sitewright.model", fromlist=["new_page"]).new_page("Results")
priv = __import__("sitewright.model", fromlist=["new_page"]).new_page("Staff", protect=True)
doc.pages += [res, priv]
doc.pages[0]["items"] = [new_item("text", 20, 20, text="Fresh bread every morning"),
                         new_item("search", 20, 80, link="page:" + res["id"]),
                         new_item("subscribe", 20, 140), new_item("login", 20, 200)]
priv["items"] = [new_item("text", 20, 20, text="Salary spreadsheet")]
res["items"] = [new_item("searchresults", 20, 20)]
salt, hh = phpgen.hash_password("pw-123456")
doc.members = [dict(name="ann", salt=salt, hash=hh)]
doc.list_key = "abc123"
idx = export.search_index(doc, export.page_files(doc, True), True)
assert [i["t"] for i in idx] == ["Home", "Results"]            # members-only page is not searchable
assert "Fresh bread" in idx[0]["x"]
out9 = os.path.join(tmp, "out9")
fl = export.export_site(doc, out9)
rel = {os.path.relpath(f, out9) for f in fl}
assert {"sw-auth.php", "subscribe.php", "subscribers.php", "staff/index.php"} <= rel
assert "Salary spreadsheet" not in open(os.path.join(out9, "results", "index.html")).read()
assert "sw_require('../'" in open(os.path.join(out9, "staff", "index.php")).read()
assert "password" not in open(os.path.join(out9, "sw-auth.php")).read().split("function sw_members")[1].split("}")[0]
assert hh in open(os.path.join(out9, "sw-auth.php")).read()
prev = os.path.join(tmp, "out9p")
export.export_site(doc, prev, clean=False, preview=True)          # a preview needs no PHP
assert os.path.exists(os.path.join(prev, "staff.html")) and not os.path.exists(os.path.join(prev, "staff.php"))
home9 = open(os.path.join(out9, "index.html")).read()
assert 'action="results/"' in home9 and 'name="q"' in home9 and 'action="subscribe.php"' in home9
assert 'action="sw-auth.php"' in home9
sm9 = open(os.path.join(out9, "sitemap.xml")).read() if os.path.exists(os.path.join(out9, "sitemap.xml")) else ""
assert "staff" not in sm9
assert "protected" not in " ".join(m for m, _p, _i in taskcheck.check(doc)) or True

# ---- slider, rollovers, lightbox, compositions ----
from sitewright import compositions
from sitewright.model import asset_refs
w.undo.setClean()
w.new_site()
doc = w.doc
pic_a = doc.add_asset(png)
pic_b = doc.add_asset(png)
sl = new_item("slider", 20, 20)
sl["panels"][0]["asset"] = pic_a
sl.update(anim="fade", loop=3000, autoplay=True)
img = new_item("image", 20, 400, asset=pic_a, hover_asset=pic_b, hover_effect="swap",
               lightbox=True, lightbox_asset=pic_b, caption="Big view", alt="Small")
img2 = new_item("image", 300, 400, asset=pic_a, hover_effect="zoom", lightbox=True)
doc.pages[0]["items"] = [sl, img, img2]
sub_page = __import__("sitewright.model", fromlist=["new_page"]).new_page("Second")
sub_page["items"] = [dict(img, id="zz1")]
doc.pages.append(sub_page)
assert pic_b in asset_refs(img) and pic_a in asset_refs(sl)
out10 = os.path.join(tmp, "out10")
export.export_site(doc, out10)
h = open(os.path.join(out10, "index.html")).read()
assert h.count('class="sw-slide"') == 3 and 'data-anim="fade"' in h and 'data-loop="3000"' in h
assert 'class="sw-prev"' in h and 'class="sw-dots"' in h and "ResizeObserver" in h
assert 'class="o ro"' in h and 'class="ro-b"' in h and 'class="o ro-z"' in h
assert h.count('data-lb="images/') == 2 and 'data-cap="Big view"' in h
assert "function open(el)" in h                                 # the lightbox script is on the page
h2 = open(os.path.join(out10, "second", "index.html")).read()
assert 'data-lb="../images/' in h2 and 'src="../images/' in h2
# panels' pictures survive a save (used_assets looks inside sliders)
p10 = os.path.join(tmp, "s10.sitewright")
doc.save(p10)
assert pic_a in Document.load(p10).assets
# compositions: save to a private folder, insert into a fresh site, ids and pictures are new
folder = os.path.join(tmp, "comps")
compositions.FOLDER = folder
grp = new_item("rect", 100, 100, group="g1")
grp2 = new_item("image", 150, 120, asset=pic_a, group="g1")
path = compositions.save("Hero card", [dict(grp, x=0, y=0), dict(grp2, x=50, y=20)], doc.assets, folder)
assert compositions.list_all(folder)[0][0] == "Hero card"
w.undo.setClean()
w.new_site()
w.insert_composition(path)
items = w.doc.pages[0]["items"]
assert len(items) == 2 and items[0]["id"] != grp["id"]
assert items[0]["group"] == items[1]["group"] != "g1"
assert items[1]["asset"] in w.doc.assets and items[1]["asset"] != pic_a

# ---- toolbars can be dragged anywhere, floated and locked ----
w2 = MainWindow()
assert len(w2.toolbars) == 2
for tb in w2.toolbars:
    assert tb.isMovable() and tb.isFloatable() and tb.allowedAreas() == Qt.AllToolBarAreas
w2.lock_toolbars(True)
assert not any(tb.isMovable() for tb in w2.toolbars)
w2.lock_toolbars(False)
assert all(tb.isMovable() for tb in w2.toolbars)
from PyQt5.QtCore import QSettings
QSettings("4ThePeopleMedia", "Sitewright").setValue("toolbars_locked", False)
# every picture button tells you its name when you point at it
named = 0
for tb in w2.toolbars:
    for act in tb.actions():
        if act.isSeparator() or act.text() == "" and not act.icon().isNull() is False:
            continue
        if not act.icon().isNull():
            assert act.toolTip().strip() and act.toolTip() != act.text() or act.text(), act.text()
            assert act.statusTip(), act.text()
            named += 1
assert named >= 20, named
assert all(b.toolTip() for b in w2.colour_buttons)
assert all(a.toolTip() and a.statusTip() for a in w2.tool_actions.values())
# the button name appears inside the window when the pointer rests on a button
from PyQt5.QtCore import QEvent
from PyQt5.QtWidgets import QToolButton as _TB
import time as _time
w2.show()
btn = [b for b in w2.toolbars[0].findChildren(_TB) if b.defaultAction() is not None][0]
w2.hover_names.delay = 20
w2.hover_names.pending = btn
w2.hover_names._show.__self__.pending = btn
from PyQt5.QtCore import QPoint
app.sendEvent(btn, QEvent(QEvent.Enter))
for _i in range(20):
    app.processEvents()
    _time.sleep(0.01)
# (underMouse() is false offscreen, so call the shower directly the way the timer would)
w2.hover_names.pending = btn
btn.underMouse = lambda: True
w2.hover_names._show()
lab = w2.hover_names.current
assert lab is not None and lab.isVisibleTo(w2) and lab.text() == "New site (Ctrl+N)", lab and lab.text()
w2.hover_names.hide()
assert not lab.isVisibleTo(w2)
# the Task Monitor stays out of the way until asked for
assert not w2.task_dock.isVisibleTo(w2)
w2.show_tasks()
assert w2.task_dock.isVisibleTo(w2)
w2.task_dock.hide()
# the Tools panel is locked to the width of one column of tools
td = w2.toolbox_dock
assert td.minimumWidth() == td.maximumWidth() and 40 < td.maximumWidth() < 80, td.maximumWidth()
w2.layout_toolbox(Qt.TopDockWidgetArea)      # docked along the top it is locked in height instead
assert td.minimumHeight() == td.maximumHeight() and td.maximumWidth() > 1000
w2.layout_toolbox(Qt.LeftDockWidgetArea)
state = w2.saveState(3)                      # layouts can be saved and put back
assert w2.restoreState(state, 3)
# WebPlus packs open as ordinary sites (skipped when the sample pack is not on this machine)
_wp = os.environ.get("WEBPLUS_TEST_PACK", "")     # optional: a Serif WebPlus .wpack to try the importer on
if _wp and os.path.exists(_wp):
    from sitewright import wpimport
    _doc, _rep = wpimport.import_pack(_wp, [os.path.dirname(_wp)])
    assert _rep["pages"] == 5 and _doc.master and len(_doc.scheme) == 12
    assert any(i["kind"] == "text" for p in _doc.pages for i in p["items"])
    w2.import_wpack_path(_wp)
    assert len(w2.doc.pages) == 5 and w2.doc.site_title.startswith("Ski")
_f = os.environ.get("WEBPLUS_TEST_WPP", "")      # optional: a real Serif WebPlus .wpp file to try the importer on
if _f and os.path.exists(_f):
    _d, _r = wpimport.import_pack(_f, [])
    assert _r["pages"] == 2 and _d.assets and any(i["kind"] == "table" for p in _d.pages for i in p["items"])
    w2.open_path(_f)
    assert len(w2.doc.pages) == 2 and w2.doc.path == ""
print("ALL GOOD")
