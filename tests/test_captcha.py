"""CAPTCHA (a question) and reCAPTCHA in forms: page, send.php, and a real PHP run.
Must print ALL GOOD."""
import os
import socket
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.parse
import urllib.request

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from PyQt5.QtCore import QRectF
from PyQt5.QtGui import QImage, QPainter
from PyQt5.QtWidgets import QApplication

from sitewright import export, extras, taskcheck
from sitewright.canvas import ItemObj
from sitewright.model import FIELD_LABELS, FIELD_TYPES, new_item
from sitewright.window import MainWindow

app = QApplication([])
w = MainWindow()
w.show()
doc = w.doc
doc.site_title, doc.form_email, doc.form_mode = "Garden Club", "owner@example.com", "php"


def objs():
    return [o for o in w.scene.items() if isinstance(o, ItemObj) and o.editable]


assert "captcha" in FIELD_TYPES and "recaptcha" in FIELD_TYPES
assert FIELD_LABELS["captcha"].startswith("CAPTCHA") and FIELD_LABELS["recaptcha"].startswith("reCAPTCHA")

# the fields get sensible starting values
w.create_item("field:captcha", QRectF(20, 20, 4, 4))
c = objs()[0]
assert c.d["ftype"] == "captcha" and c.d["label"] == "What is 3 plus 4?" and c.d["answer"] == "7"
assert (c.d["w"], c.d["h"]) == (260, 38)
for o in w.scene.selectedItems():
    o.setSelected(False)
w.create_item("field:recaptcha", QRectF(20, 80, 4, 4))
rc = [o for o in objs() if o.d["ftype"] == "recaptcha"][0]
assert (rc.d["w"], rc.d["h"]) == (304, 78)
w.create_item("field:submit", QRectF(20, 180, 200, 40))

# both draw
for it in (c, rc):
    img = QImage(320, 90, QImage.Format_ARGB32)
    img.fill(0xffffffff)
    pp = QPainter(img)
    extras.paint_field(pp, QRectF(2, 2, it.d["w"] - 4, min(it.d["h"], 86)), it.d, w)
    pp.end()
    assert any(img.pixelColor(x, 20).lightness() < 250 for x in range(0, 300)), it.d["ftype"]

# page: the question box and the hash of the right answer (never the answer itself)
rc.d["rc_site"], rc.d["rc_secret"] = "SITEKEY123", "SECRETKEY456"
salt = extras.captcha_salt("Garden Club", "owner@example.com")
assert len(salt) == 20 and salt != extras.captcha_salt("Other", "owner@example.com")
assert extras.captcha_hash(" Seven ", salt) == extras.captcha_hash("seven", salt)
page = export.page_source(doc, doc.pages[0]["id"], False)
assert 'name="captcha_answer"' in page and 'placeholder="What is 3 plus 4?"' in page
assert 'name="_cap" value="%s"' % extras.captcha_hash("7", salt) in page
assert 'value="7"' not in page and ">7<" not in page
assert 'class="o g-recaptcha" data-sitekey="SITEKEY123"' in page
assert page.count("www.google.com/recaptcha/api.js") == 1
assert "SECRETKEY456" not in page, "the secret key must never be on the page"
assert "sent=captcha" in page

# send.php carries the checks
php = extras.send_php(doc.form_email, doc)
assert "hash('sha256', $ans . '%s')" % salt in php
assert "'SECRETKEY456'" in php and "siteverify" in php
plain = extras.send_php("a@b.c")
assert "_cap" not in plain.split("$lines")[0] and "siteverify" not in plain
# a site with neither field does not get the checks
doc2_php = extras.send_php("a@b.c", type("D", (), dict(pages=[dict(items=[])], site_title="x", form_email="a@b.c",
                                                      all_master_lists=lambda self: []))())
assert "siteverify" not in doc2_php and "'_cap'" in doc2_php.split("foreach")[1]

# task monitor warnings
tasks = [t[0] for t in taskcheck.check(doc)]
assert not any("CAPTCHA" in t for t in tasks)
c.d["answer"] = ""
rc.d["rc_site"] = ""
doc.form_mode = "mailto"
tasks = [t[0] for t in taskcheck.check(doc)]
assert any("no answer set" in t for t in tasks) and any("site key" in t for t in tasks)
assert any("only works when the form is sent by the PHP" in t for t in tasks)
c.d["answer"], rc.d["rc_site"], doc.form_mode = "7", "SITEKEY123", "php"

# a real PHP run: wrong answer is sent back; right answer gets through the check
out = tempfile.mkdtemp()
export.export_site(doc, out)
assert os.path.isfile(os.path.join(out, "send.php"))
s = socket.socket()
s.bind(("127.0.0.1", 0))
port = s.getsockname()[1]
s.close()
srv = subprocess.Popen(["php", "-S", "127.0.0.1:%d" % port, "-t", out], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
try:
    for _ in range(50):
        try:
            socket.create_connection(("127.0.0.1", port), timeout=0.2).close()
            break
        except OSError:
            time.sleep(0.1)

    class NoRedirect(urllib.request.HTTPRedirectHandler):
        def redirect_request(self, *a, **k):
            return None
    opener = urllib.request.build_opener(NoRedirect)

    def post(data):
        req = urllib.request.Request("http://127.0.0.1:%d/send.php" % port, urllib.parse.urlencode(data).encode(),
                                     headers={"Referer": "http://127.0.0.1:%d/" % port})
        try:
            opener.open(req, timeout=10)
            return ""
        except urllib.error.HTTPError as e:
            return e.headers.get("Location", "")
    good_hash = extras.captcha_hash("7", salt)
    base = {"name": "A", "email": "a@b.co", "_cap": good_hash}
    assert "sent=captcha" in post(dict(base, captcha_answer="8", **{"g-recaptcha-response": "x"}))
    assert "sent=captcha" in post(dict(base, captcha_answer=""))
    # right answer passes the CAPTCHA check; then reCAPTCHA (no network to Google here) turns it away
    r = post(dict(base, captcha_answer=" 7 ", **{"g-recaptcha-response": "token"}))
    assert "sent=captcha" in r                      # reCAPTCHA could not be confirmed
    # without reCAPTCHA configured, the right answer is let through to the mail step
    rc.d["rc_secret"] = ""
    export.export_site(doc, out)
    r = post(dict(base, captcha_answer="SEVEN?"))
    assert "sent=captcha" in r
    r = post(dict(base, captcha_answer="7"))
    assert "sent=0" in r or "sent=1" in r, r
finally:
    srv.terminate()

w.deleteLater()
app.processEvents()
del w
print("ALL GOOD")
