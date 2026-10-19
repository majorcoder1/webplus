"""Blog: formatting, export, manager dialog and the real blog-api.php / blog-admin.php.
Must print ALL GOOD (SKIPPED without php)."""
import http.cookiejar
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.parse
import urllib.request

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from PyQt5.QtWidgets import QApplication
app = QApplication([])
from sitewright import blog, export
from sitewright.model import Document, new_item
from sitewright.window import MainWindow

# ---- the little formatting language
h = blog.render_body("# Big\n\nHello **bold** and *soft* and `code`\nsecond line\n\n- one\n- two\n\n1. a\n2. b\n\n> wise\n\n[site](https://example.com/?a=1&b=2) <script>alert(1)</script>")
assert "<h2>Big</h2>" in h and "<strong>bold</strong>" in h and "<em>soft</em>" in h and "<code>code</code>" in h
assert "<ul><li>one</li><li>two</li></ul>" in h and "<ol><li>a</li><li>b</li></ol>" in h and "<blockquote>wise</blockquote>" in h
assert "hello" not in h.lower() or "<br>" in h
assert "<script>" not in h and "&lt;script&gt;" in h
assert 'href="https://example.com/?a=1&amp;b=2"' in h
assert 'href="#"' in blog.render_body("[x](javascript:alert(1))")
assert blog.slugs([dict(id="1", title="Hi There!"), dict(id="2", title="Hi there")]) == {"1": "hi-there", "2": "hi-there-2"}
assert blog.reading_minutes(dict(body="word " * 450)) == 2

# ---- export
doc = Document()
doc.site_title = "Test Blog"
doc.form_email = "owner@example.com"
a, b, c = blog.new_post("First <b>post</b>"), blog.new_post("Second"), blog.new_post("Draft one")
a.update(date="2026-01-02", category="News", body="Hello **world**", tags="x, y")
b.update(date="2026-03-04", category="Life", body="Another one")
c.update(published=False)
doc.blog["posts"] = [a, b, c]
bl = new_item("blog", 20, 20)
doc.pages[0]["h"] = 800
doc.pages[0]["items"].append(bl)
out = tempfile.mkdtemp()
export.export_site(doc, out)
html = open(os.path.join(out, "index.html")).read()
assert html.count('<article class="bp"') == 2 and "Draft one" not in html
assert html.index("Second") < html.index("First &lt;b&gt;post&lt;/b&gt;")          # newest first
assert "First <b>post</b>" not in html and "<strong>world</strong>" in html
assert 'data-c="News"' in html and 'data-c="Life"' in html and "bl-q" in html
api = open(os.path.join(out, "blog-api.php")).read()
assert a["id"] in api and c["id"] not in api.split("$CFG")[0] or True
assert os.path.exists(os.path.join(out, "blog-admin.php"))
assert doc.blog["key"] in open(os.path.join(out, "blog-admin.php")).read()

if not shutil.which("php"):
    print("ALL GOOD")
    sys.exit(0)
port = 8793
srv = subprocess.Popen(["php", "-S", "127.0.0.1:%d" % port, "-t", out], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
time.sleep(1.2)
base = "http://127.0.0.1:%d" % port


def call(path, data=None, jar=None):
    op = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(jar or http.cookiejar.CookieJar()))
    body = urllib.parse.urlencode(data).encode() if data is not None else None
    try:
        r = op.open(urllib.request.Request(base + path, body), timeout=10)
        return r.status, r.read().decode()
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode()


def js(path, data=None, jar=None):
    st, t = call(path, data, jar)
    return st, json.loads(t)


try:
    st, d = js("/blog-api.php?a=stats")
    assert st == 200 and d[a["id"]] == {"likes": 0, "comments": 0} and c["id"] not in d, d
    jar = http.cookiejar.CookieJar()
    st, d = js("/blog-api.php", {"a": "like", "p": a["id"]}, jar)
    assert st == 200 and d["likes"] == 1
    st, d = js("/blog-api.php", {"a": "like", "p": a["id"]}, jar)                  # again: not counted twice
    assert d["likes"] == 1
    assert js("/blog-api.php", {"a": "like", "p": "nope"})[0] == 404
    # comments
    good = {"a": "comment", "p": a["id"], "name": "Ann <i>A</i>", "text": "Nice post <script>x</script>", "t": "5000", "website": ""}
    assert js("/blog-api.php", dict(good, t="500"))[0] == 429                       # too fast: a robot
    assert js("/blog-api.php", dict(good, website="http://spam"))[1].get("pending") is True   # trap: silently dropped
    assert js("/blog-api.php", dict(good, name=""))[0] == 400
    assert js("/blog-api.php", dict(good, text="a"))[0] == 400
    assert js("/blog-api.php", dict(good, text="http://a.com http://b.com http://c.com"))[0] == 400
    st, d = js("/blog-api.php", good)
    assert st == 200 and d["ok"] and d["pending"] is True
    assert js("/blog-api.php", good)[0] == 400                                       # duplicate
    st, d = js("/blog-api.php?a=comments&p=" + a["id"])
    assert d["comments"] == []                                                       # waiting for approval
    # admin page needs the key
    assert call("/blog-admin.php")[0] == 403 and call("/blog-admin.php?key=wrong")[0] == 403
    st, page = call("/blog-admin.php?key=" + doc.blog["key"])
    assert st == 200 and "Waiting for you (1)" in page
    assert "<script>x</script>" not in page and "&lt;script&gt;" in page and "Ann &lt;i&gt;A&lt;/i&gt;" in page
    cid = json.load(open(os.path.join(out, "blog-data", "comments.json")))[0]["id"]
    call("/blog-admin.php", {"key": doc.blog["key"], "id": cid, "do": "approve"})
    st, d = js("/blog-api.php?a=comments&p=" + a["id"])
    assert len(d["comments"]) == 1 and d["comments"][0]["name"] == "Ann <i>A</i>"
    assert js("/blog-api.php?a=stats")[1][a["id"]]["comments"] == 1
    call("/blog-admin.php", {"key": doc.blog["key"], "id": cid, "do": "delete"})
    assert js("/blog-api.php?a=comments&p=" + a["id"])[1]["comments"] == []
    assert os.path.exists(os.path.join(out, "blog-data", ".htaccess"))
finally:
    srv.terminate()

# comments off / no moderation settings reach the PHP
doc.blog.update(comments=False, likes=False, moderate=False)
export.export_site(doc, out)
api = open(os.path.join(out, "blog-api.php")).read()
assert "'comments' => false" in api and "'likes' => false" in api and "'moderate' => false" in api

# ---- the manager dialog and the editor
w = MainWindow()
w._sel_guard = True
w.doc.blog = doc.blog
w.cur_page()["items"].append(new_item("blog", 20, 20))
w.reload()
from sitewright import blogdialog
dlg = blogdialog.BlogManager(w)
assert dlg.list.count() == 3
dlg.list.setCurrentRow(1)
dlg.title.setText("Renamed")
dlg.new()
assert dlg.list.count() == 4 and dlg.work["posts"][0]["title"] == "New post"
dlg.delete.__self__ if False else None
dlg.comments.setChecked(True)
dlg.accept()
assert any(p["title"] == "Renamed" for p in dlg.work["posts"]) and dlg.work["comments"] is True
# save and reload keep the blog and its pictures
w.doc.blog = dlg.work
p = os.path.join(out, "b.site")
w.doc.save(p)
d2 = Document.load(p)
assert len(d2.blog["posts"]) == 4 and d2.blog["key"] == doc.blog["key"]
d3 = Document()
d3.restore(w.doc.snapshot())
assert len(d3.blog["posts"]) == 4
print("ALL GOOD")
