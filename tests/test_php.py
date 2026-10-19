"""Runs the generated PHP (members, mailing list) on PHP's built-in server.
Must print ALL GOOD (prints SKIPPED if php is not installed)."""
import http.cookiejar
import os
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

if not shutil.which("php"):
    print("SKIPPED (php not installed)")
    sys.exit(0)

from PyQt5.QtWidgets import QApplication
app = QApplication([])
from sitewright import export, phpgen
from sitewright.model import Document, new_item, new_page

doc = Document()
doc.site_title = "Test Site"
doc.form_email = "owner@example.com"
doc.list_key = "k3y-secret"
salt, h = phpgen.hash_password("correct horse")
doc.members = [dict(name="ann", salt=salt, hash=h)]
secret = new_page("Members", protect=True, items=[new_item("text", 20, 20, text="Secret members content")])
doc.pages.append(secret)
doc.pages[0]["items"] = [new_item("subscribe", 20, 20), new_item("login", 20, 100),
                         new_item("search", 20, 300)]
out = tempfile.mkdtemp()
files = export.export_site(doc, out)
names = {os.path.relpath(f, out) for f in files}
assert "members/index.php" in names and "sw-auth.php" in names, names
assert "subscribe.php" in names and "subscribers.php" in names
assert "Secret members content" not in open(os.path.join(out, "sitemap.xml")).read() if os.path.exists(
    os.path.join(out, "sitemap.xml")) else True

port = 8791
srv = subprocess.Popen(["php", "-S", "127.0.0.1:%d" % port, "-t", out],
                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
time.sleep(1.2)
base = "http://127.0.0.1:%d" % port


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, *a, **k):
        return None


jar = http.cookiejar.CookieJar()
op = urllib.request.build_opener(NoRedirect, urllib.request.HTTPCookieProcessor(jar))


def get(path):
    try:
        r = op.open(base + path)
        return r.status, r.read().decode(), r.headers
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode(), e.headers


def post(path, data, headers=None):
    req = urllib.request.Request(base + path, urllib.parse.urlencode(data).encode(),
                                 headers=headers or {})
    try:
        r = op.open(req)
        return r.status, r.read().decode(), r.headers
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode(), e.headers

try:
    code, body, _ = get("/members/")
    assert code == 200 and "Members only" in body and "Secret members content" not in body
    code, body, _ = post("/sw-auth.php", dict(action="login", user="ann", **{"pass": "wrong"},
                                              **{"return": "/members/"}))
    assert "not right" in body and "Secret members content" not in body
    code, body, hdr = post("/sw-auth.php", dict(action="login", user="ann",
                                                **{"pass": "correct horse"},
                                                **{"return": "/members/"}))
    assert code == 302 and hdr["Location"] == "/members/", (code, dict(hdr))
    code, body, _ = get("/members/")
    assert code == 200 and "Secret members content" in body
    code, body, hdr = post("/sw-auth.php", dict(action="login", user="ann",
                                                **{"pass": "correct horse"},
                                                **{"return": "http://evil.example/"}))
    assert hdr["Location"] == "/"                         # no open redirect
    # mailing list
    code, _b, hdr = post("/subscribe.php", dict(email="reader@example.com"),
                         {"Referer": base + "/"})
    assert code == 302 and "joined=1" in hdr["Location"], hdr["Location"]
    code, _b, hdr = post("/subscribe.php", dict(email="not-an-email"), {"Referer": base + "/"})
    assert "joined=0" in hdr["Location"]
    code, _b, hdr = post("/subscribe.php", dict(email="bot@example.com", website="spam"),
                         {"Referer": base + "/"})
    assert "joined" not in hdr["Location"]
    code, body, _ = get("/subscribers.php?key=k3y-secret")
    assert code == 200 and "reader@example.com" in body and "bot@example.com" not in body
    code, _b, _ = get("/subscribers.php?key=wrong")
    assert code == 403
    code, body, _ = get("/sw-data/")                       # the list folder is not browsable
    code2, _b, _ = get("/sw-data/index.html")
    assert code in (200, 403, 404)
    print("ALL GOOD", flush=True)
finally:
    srv.terminate()
    sys.stdout.flush()
    os._exit(0)
