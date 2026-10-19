"""RSS reader: drawn in the editor, exported with a small PHP helper that only fetches the
feeds the site uses, and run for real against a local feed. Must print ALL GOOD."""
import json
import os
import socket
import subprocess
import sys
import tempfile
import time
import urllib.request

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from PyQt5.QtCore import QRectF
from PyQt5.QtGui import QImage, QPainter
from PyQt5.QtWidgets import QApplication

from sitewright import export, extras, taskcheck
from sitewright.canvas import ItemObj
from sitewright.model import KIND_NAMES, new_item, new_page
from sitewright.propdialog import PropertiesDialog
from sitewright.window import MainWindow

app = QApplication([])
w = MainWindow()
w.show()
doc = w.doc
assert KIND_NAMES["rssreader"] == "RSS reader"


def objs():
    return [o for o in w.scene.items() if isinstance(o, ItemObj) and o.editable]


w.create_item("rssreader", QRectF(20, 20, 360, 260))
r = objs()[0]
assert r.d["kind"] == "rssreader" and r.d["count"] == 5 and r.d["show_date"] is True
img = QImage(380, 280, QImage.Format_ARGB32)
img.fill(0xffffffff)
pp = QPainter(img)
extras.paint_rssreader(pp, QRectF(0, 0, 360, 260), dict(r.d, url="https://news.example.org/feed"), w)
pp.end()
assert any(img.pixelColor(x, y).lightness() < 120 for x in range(10, 300) for y in range(36, 120)), "headline text is drawn"

# task monitor: no address
assert any("no feed address" in t[0] for t in taskcheck.check(doc))
r.setSelected(True)

# export: two readers on two pages, three boxes, two different feeds
doc.pages.append(new_page("News"))
feedA, feedB = "https://a.example.org/feed.xml", "https://b.example.org/rss"
r.d["url"] = feedA
doc.pages[0]["items"].append(new_item("rssreader", 0, 300, url=feedB, count=3, show_date=False, show_desc=False))
doc.pages[1]["items"].append(new_item("rssreader", 0, 0, url=feedA, count=8))
out = tempfile.mkdtemp()
export.export_site(doc, out)
php = open(os.path.join(out, "rss-reader.php"), encoding="utf-8").read()
assert "1 => 'https://a.example.org/feed.xml'" in php and "2 => 'https://b.example.org/rss'" in php
assert php.count("=> 'https") == 2, "each feed is listed once"
home = open(os.path.join(out, "index.html"), encoding="utf-8").read()
assert 'rss-reader.php?f=1&n=5' in home and 'rss-reader.php?f=2&n=3' in home
assert 'class="o rss"' in home and "Loading headlines" in home
news = open(os.path.join(out, "news", "index.html"), encoding="utf-8").read()
assert "../rss-reader.php?f=1&n=8" in news or "rss-reader.php?f=1&n=8" in news
assert "feed.xml" not in home, "the page never carries the feed address"
assert "textContent" in home and "innerHTML" not in home.split("rss-")[-1], "headlines are put in as plain text"

# no readers -> no helper file
doc3 = MainWindow().doc
out3 = tempfile.mkdtemp()
export.export_site(doc3, out3)
assert not os.path.exists(os.path.join(out3, "rss-reader.php"))

# real PHP run against a local feed
site = tempfile.mkdtemp()
open(os.path.join(site, "feed.xml"), "w", encoding="utf-8").write("""<?xml version="1.0"?>
<rss version="2.0"><channel><title>T</title>
<item><title>First &amp; best</title><link>https://example.com/1</link><description>&lt;p&gt;Hello &lt;b&gt;world&lt;/b&gt;, this is item one.&lt;/p&gt;</description><pubDate>Sat, 10 Oct 2026 10:00:00 GMT</pubDate></item>
<item><title>Second</title><link>javascript:alert(1)</link><description>Two</description><pubDate>Fri, 09 Oct 2026 10:00:00 GMT</pubDate></item>
<item><title>Third</title><link>https://example.com/3</link><description>Three</description></item>
</channel></rss>""")
open(os.path.join(site, "atom.xml"), "w", encoding="utf-8").write("""<?xml version="1.0"?>
<feed xmlns="http://www.w3.org/2005/Atom"><title>A</title>
<entry><title>Atom one</title><link rel="alternate" href="https://example.com/a1"/><summary>Short</summary><updated>2026-10-08T12:00:00Z</updated></entry>
</feed>""")
s = socket.socket()
s.bind(("127.0.0.1", 0))
port = s.getsockname()[1]
s.close()
ids = {"http://127.0.0.1:%d/feed.xml" % port: 1, "http://127.0.0.1:%d/atom.xml" % port: 2}
open(os.path.join(site, "rss-reader.php"), "w", encoding="utf-8").write(extras.rss_php(ids))
srv = subprocess.Popen(["php", "-S", "127.0.0.1:%d" % port, "-t", site], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                       env=dict(os.environ, PHP_CLI_SERVER_WORKERS="4"))   # the helper fetches from this same server
try:
    for _ in range(50):
        try:
            socket.create_connection(("127.0.0.1", port), timeout=0.2).close()
            break
        except OSError:
            time.sleep(0.1)

    def get(q):
        with urllib.request.urlopen("http://127.0.0.1:%d/rss-reader.php?%s" % (port, q), timeout=15) as resp:
            return json.loads(resp.read().decode("utf-8"))
    items = get("f=1&n=2")
    assert len(items) == 2 and items[0]["title"] == "First & best"
    assert items[0]["desc"] == "Hello world, this is item one." and items[0]["date"] == "Oct 10, 2026"
    assert items[0]["link"] == "https://example.com/1"
    assert items[1]["link"] == "javascript:alert(1)"      # the page's script refuses it (only http/https become links)
    assert len(get("f=1&n=20")) == 3 and get("f=1&n=20")[2]["date"] == ""
    atom = get("f=2")
    assert atom == [dict(title="Atom one", link="https://example.com/a1", desc="Short", date="Oct 8, 2026")]
    # only listed feeds can be asked for
    try:
        get("f=9")
        raise AssertionError("an unlisted feed must not be fetched")
    except urllib.error.HTTPError as e:
        assert e.code == 404
finally:
    srv.terminate()
assert "/^https?:\\/\\//i" in extras.RSS_JS

d = PropertiesDialog(w, new_item("rssreader", 0, 0))
assert {"url", "count", "show_date", "show_desc"} <= set(d.getters)
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
assert "RSS reader (headlines from a feed)" in labels
w.deleteLater()
app.processEvents()
del w
print("ALL GOOD")
