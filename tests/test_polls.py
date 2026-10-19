"""Web polls: object, export and the real poll.php. Must print ALL GOOD (SKIPPED without php)."""
import json
import os
import shutil
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.parse
import urllib.request
import http.cookiejar

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
if not shutil.which("php"):
    print("SKIPPED (php not installed)")
    sys.exit(0)

from PyQt5.QtWidgets import QApplication
app = QApplication([])
from sitewright import export, polls
from sitewright.model import Document, new_item
from sitewright.window import MainWindow

doc = Document()
poll = new_item("poll", 20, 20, question="Best <b>colour</b>?", options="Red\nGreen\nBlue", results="always")
multi = new_item("poll", 20, 320, question="Pick many", options="A\nB\nC", multi=True)
closed = new_item("poll", 20, 620, question="Over", options="Yes\nNo", closed=True)
doc.pages[0]["h"] = 900
doc.pages[0]["items"] += [poll, multi, closed]
out = tempfile.mkdtemp()
files = export.export_site(doc, out)
assert os.path.exists(os.path.join(out, "poll.php"))
html = open(os.path.join(out, "index.html")).read()
assert "Best &lt;b&gt;colour&lt;/b&gt;?" in html and "<b>colour</b>" not in html     # question is escaped
assert html.count('class="o pl"') == 3 and 'type="radio"' in html and 'type="checkbox"' in html
assert "fetch(api" in html

port = 8792
srv = subprocess.Popen(["php", "-S", "127.0.0.1:%d" % port, "-t", out], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
time.sleep(1.2)
base = "http://127.0.0.1:%d/poll.php" % port
pid, mid, cid = polls.key(poll), polls.key(multi), polls.key(closed)


def call(url, data=None, jar=None):
    op = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(jar or http.cookiejar.CookieJar()))
    body = urllib.parse.urlencode(data, doseq=True).encode() if data is not None else None
    try:
        r = op.open(urllib.request.Request(url, body), timeout=10)
        return r.status, json.loads(r.read())
    except urllib.error.HTTPError as e:
        return e.code, json.loads(e.read())


try:
    st, d = call(base + "?id=" + pid)
    assert st == 200 and d["counts"] == [0, 0, 0] and d["total"] == 0 and d["voted"] is False, d
    jar = http.cookiejar.CookieJar()
    st, d = call(base, {"id": pid, "c[]": [1]}, jar)
    assert st == 200 and d["counts"] == [0, 1, 0] and d["voted"], d
    st, d = call(base, {"id": pid, "c[]": [2]}, jar)                       # same visitor again
    assert st == 409 and d["counts"] == [0, 1, 0], (st, d)
    st, d = call(base + "?id=" + pid)                                       # same address, no cookie: still counted once
    assert d["voted"] is True and d["total"] == 1
    # a different visitor: forget the address record
    f = os.path.join(out, "poll-data", pid + ".json")
    j = json.load(open(f)); j["ips"] = []; json.dump(j, open(f, "w"))
    st, d = call(base, {"id": pid, "c[]": [0]})
    assert st == 200 and d["counts"] == [1, 1, 0] and d["total"] == 2, d
    # bad input
    assert call(base, {"id": pid, "c[]": [7]})[0] == 400
    assert call(base, {"id": pid})[0] == 400
    assert call(base, {"id": pid, "c[]": [0, 1]})[0] in (400, 409)         # single-choice poll refuses two
    assert call(base + "?id=nope")[0] == 404
    assert call(base, {"id": cid, "c[]": [0]})[0] == 403                    # closed
    st, d = call(base, {"id": mid, "c[]": [0, 2]})                          # multiple choice accepts two
    assert st == 200 and d["counts"] == [1, 0, 1], d
    # data folder is closed to visitors
    assert os.path.exists(os.path.join(out, "poll-data", ".htaccess"))
finally:
    srv.terminate()

# the editor draws it and the dialog knows it
w = MainWindow()
w._sel_guard = True
from sitewright import webapps
webapps.insert.__doc__
w.doc.pages[0]["items"].append(new_item("poll", 40, 40))
w.reload()
from sitewright.propdialog import SCHEMA
assert "poll" in SCHEMA
print("ALL GOOD")
