"""Shop: products, export for every checkout provider, the Stripe PHP (against a pretend Stripe), store imports.
Must print ALL GOOD (the PHP part prints nothing extra without php)."""
import json
import os
import shutil
import subprocess
import sys
import tempfile
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
from http.server import BaseHTTPRequestHandler, HTTPServer

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from PyQt5.QtWidgets import QApplication
app = QApplication([])
from sitewright import export, shop
from sitewright.model import Document, new_item
from sitewright.window import MainWindow

# ---- money and CSV
assert shop.money(1234.5, "USD") == "$1,234.50" and shop.money(1500, "JPY") == "¥1,500" and shop.money(2, "EUR") == "€2.00"
prods = [shop.new_product("Hat <b>"), shop.new_product("Scarf")]
prods[0].update(price=19.99, desc="Warm, \"snug\"", sku="H1")
prods[1].update(price=5, shopify_variant="777", woo_id="42", stripe_link="https://buy.stripe.com/x")
back = shop.products_from_csv(shop.products_to_csv(prods))
assert [p["name"] for p in back] == ["Hat <b>", "Scarf"] and back[0]["price"] == 19.99 and back[0]["desc"] == 'Warm, "snug"'
assert back[1]["shopify_variant"] == "777" and back[1]["woo_id"] == "42"
assert shop.products_from_csv("name,price\nPen,$3.50\n,\nBook,12\n")[0]["price"] == 3.5

SECRET = "sk_live_SUPERSECRET123"
TOKEN = "shpat_TOKEN456"


def build(provider, **over):
    doc = Document()
    doc.site_title = "Shop"
    s = doc.shop
    s.update(provider=provider, currency="USD", shipping=4.5, tax=10, products=[dict(p) for p in prods],
             paypal_client="CLIENT123", paypal_email="me@example.com", stripe_secret=SECRET, shopify_domain="x.myshopify.com",
             shopify_token=TOKEN, woo_url="https://woo.example.com")
    s.update(over)
    pg = doc.pages[0]
    pg["h"] = 900
    pg["items"] += [new_item("product", 20, 20, product=s["products"][0]["id"]),
                    new_item("productgrid", 20, 420), new_item("cart", 700, 20)]
    out = tempfile.mkdtemp()
    export.export_site(doc, out)
    return doc, out


def files_with(out, needle):
    found = set()
    for root, _d, fs in os.walk(out):
        for f in fs:
            full = os.path.join(root, f)
            if f.endswith(".png") or f.endswith(".jpg"):
                continue
            if needle in open(full, errors="replace").read():
                found.add(os.path.relpath(full, out))
    return found


for prov in ("paypal", "stripe", "shopify", "woocommerce"):
    doc, out = build(prov)
    html = open(os.path.join(out, "index.html")).read()
    assert html.count("window.SWSHOP=") == 1 and html.count("var S=window.SWSHOP,") == 1, prov           # the cart script once per page
    assert "Hat &lt;b&gt;" in html and "Hat <b>" not in html                                  # names are escaped
    assert "$19.99" in html and "data-cart" in html and html.count('class="o sw-prod"') == 1
    assert html.count('data-add="') >= 3                                                        # card + grid cards
    j = json.loads(html.split("window.SWSHOP=")[1].split(";</script>")[0])
    assert j["prov"] == prov and j["cur"] == "USD" and j["ship"] == 4.5 and j["tax"] == 10
    assert set(j["p"]) == {p["id"] for p in prods} and j["p"][prods[1]["id"]]["v"] == "777"
    assert SECRET not in html and TOKEN not in html                                           # never in a page
    assert files_with(out, TOKEN) == set()                                                    # the Shopify token is not published at all
    assert files_with(out, SECRET) == ({"shop-private/config.php"} if prov == "stripe" else set())   # secret only in the private folder
    assert os.path.exists(os.path.join(out, "stripe-checkout.php")) == (prov == "stripe")
    if prov == "stripe":
        assert os.path.exists(os.path.join(out, "shop-private", ".htaccess"))
        assert SECRET in open(os.path.join(out, "shop-private", "config.php")).read()
        assert SECRET not in open(os.path.join(out, "stripe-checkout.php")).read()
# a hidden product is not for sale; no Stripe key = no Stripe files
doc, out = build("stripe", stripe_secret="")
assert not os.path.exists(os.path.join(out, "stripe-checkout.php"))
doc, out = build("paypal")
doc.shop["products"][0]["active"] = False
export.export_site(doc, out)
html = open(os.path.join(out, "index.html")).read()
assert "Hat &lt;b&gt;" not in html and html.count('class="o sw-prod"') == 0

# ---- the Stripe PHP, against a pretend Stripe
seen = []


class Fake(BaseHTTPRequestHandler):
    def do_POST(self):
        body = self.rfile.read(int(self.headers.get("Content-Length", 0))).decode()
        seen.append((self.path, self.headers.get("Authorization"), urllib.parse.parse_qs(body)))
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(json.dumps({"id": "cs_1", "url": "https://checkout.stripe.com/c/pay/cs_1"}).encode())

    def log_message(self, *a):
        pass


if shutil.which("php"):
    fake = HTTPServer(("127.0.0.1", 8795), Fake)
    threading.Thread(target=fake.serve_forever, daemon=True).start()
    doc, out = build("stripe")
    cfgp = os.path.join(out, "shop-private", "config.php")
    cfg = open(cfgp).read().replace("return array(", "return array(\n    'stripe_api' => 'http://127.0.0.1:8795',", 1)
    open(cfgp, "w").write(cfg)
    srv = subprocess.Popen(["php", "-S", "127.0.0.1:8794", "-t", out], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    time.sleep(1.2)

    def post(data):
        req = urllib.request.Request("http://127.0.0.1:8794/stripe-checkout.php", json.dumps(data).encode(),
                                     {"Content-Type": "application/json"})
        try:
            r = urllib.request.urlopen(req, timeout=10)
            return r.status, json.loads(r.read())
        except urllib.error.HTTPError as e:
            return e.code, json.loads(e.read())
    try:
        hid, sid = prods[0]["id"], prods[1]["id"]
        # the buyer's browser tries to set its own price: ignored, only ids and quantities count
        st, d = post({"items": [{"id": hid, "q": 2, "price": 0.01}, {"id": sid, "q": 1}], "back": "http://127.0.0.1:8794/shop/"})
        assert st == 200 and d["url"].startswith("https://checkout.stripe.com/"), (st, d)
        path, auth, f = seen[-1]
        assert path == "/v1/checkout/sessions" and auth.startswith("Basic ")
        import base64
        assert base64.b64decode(auth.split()[1]).decode() == SECRET + ":"
        assert f["line_items[0][price_data][unit_amount]"] == ["1999"] and f["line_items[0][quantity]"] == ["2"]
        assert f["line_items[1][price_data][unit_amount]"] == ["500"]
        assert f["line_items[2][price_data][product_data][name]"] == ["Shipping"] and f["line_items[2][price_data][unit_amount]"] == ["450"]
        assert f["line_items[3][price_data][product_data][name]"] == ["Tax"] and f["line_items[3][price_data][unit_amount]"] == ["450"]   # 10% of 4498 cents
        assert f["mode"] == ["payment"] and f["success_url"] == ["http://127.0.0.1:8794/shop/?paid=1"] and f["cancel_url"] == ["http://127.0.0.1:8794/shop/"]
        # a "back" address on another site is not trusted
        post({"items": [{"id": sid, "q": 1}], "back": "https://evil.example/steal"})
        assert seen[-1][2]["success_url"] == ["http://127.0.0.1:8794/?paid=1"]
        n = len(seen)
        assert post({"items": [{"id": "nope", "q": 1}]})[0] == 400
        assert post({"items": [{"id": sid, "q": 0}]})[0] == 400
        assert post({"items": [{"id": sid, "q": 500}]})[0] == 400
        assert post({"items": []})[0] == 400 and post({})[0] == 400
        assert len(seen) == n                                                  # bad carts never reach Stripe
        # the private folder is not readable and the PHP page alone shows no key
        try:
            urllib.request.urlopen("http://127.0.0.1:8794/shop-private/config.php", timeout=10)
            body = ""
        except urllib.error.HTTPError:
            body = ""
        assert SECRET not in (body or "")
        assert SECRET not in urllib.request.urlopen("http://127.0.0.1:8794/shop-private/config.php", timeout=10).read().decode()
    finally:
        srv.terminate()
        fake.shutdown()

# ---- store imports against pretend stores
class Store(BaseHTTPRequestHandler):
    def do_POST(self):
        assert self.headers.get("X-Shopify-Storefront-Access-Token") == "tok"
        self.rfile.read(int(self.headers.get("Content-Length", 0)))
        body = {"data": {"products": {"edges": [
            {"node": {"id": "gid://shopify/Product/1", "title": "Mug", "description": "A <b>big</b> mug", "featuredImage": {"url": "http://127.0.0.1:8796/img.png"},
                      "variants": {"edges": [{"node": {"id": "gid://shopify/ProductVariant/9001", "price": {"amount": "12.50", "currencyCode": "EUR"}}}]}}},
            {"node": {"id": "gid://shopify/Product/2", "title": "No variant", "description": "", "featuredImage": None, "variants": {"edges": []}}}]}}}
        self.send_response(200); self.send_header("Content-Type", "application/json"); self.end_headers()
        self.wfile.write(json.dumps(body).encode())

    def do_GET(self):
        if self.path.startswith("/wp-json/wc/store/v1/products"):
            body = [{"id": 42, "name": "Tea &amp; Cup", "short_description": "<p>Nice</p>", "prices": {"price": "1999", "currency_minor_unit": 2, "currency_code": "GBP"},
                     "images": [{"src": "http://127.0.0.1:8796/img.png"}]}]
            self.send_response(200); self.send_header("Content-Type", "application/json"); self.end_headers()
            self.wfile.write(json.dumps(body).encode())
        else:                                                  # the picture
            from PIL import Image
            import io
            b = io.BytesIO(); Image.new("RGB", (8, 8), (255, 0, 0)).save(b, "PNG")
            self.send_response(200); self.send_header("Content-Type", "image/png"); self.end_headers()
            self.wfile.write(b.getvalue())

    def log_message(self, *a):
        pass


st = HTTPServer(("127.0.0.1", 8796), Store)
threading.Thread(target=st.serve_forever, daemon=True).start()
items, cur = shop.import_shopify("x", "tok", api_base="http://127.0.0.1:8796")
assert cur == "EUR" and len(items) == 1 and items[0]["name"] == "Mug" and items[0]["price"] == 12.5
assert items[0]["shopify_variant"] == "9001" and items[0]["desc"] == "A big mug"
items2, cur2 = shop.import_woocommerce("http://127.0.0.1:8796")
assert cur2 == "GBP" and items2[0]["price"] == 19.99 and items2[0]["woo_id"] == "42" and items2[0]["name"] == "Tea & Cup" or items2[0]["name"] == "Tea &amp; Cup"
d = Document()
shop.fetch_image(d, items[0])
assert items[0]["asset"] in d.assets and items[0]["image_url"] == ""
st.shutdown()

# ---- the manager dialog, editor drawing, save/load
w = MainWindow()
w._sel_guard = True
w.doc.shop.update(products=[dict(p) for p in prods])
w.cur_page()["items"] += [new_item("product", 20, 20, product=prods[0]["id"]), new_item("productgrid", 20, 400), new_item("cart", 600, 20)]
w.reload()
from sitewright import shopdialog
dlg = shopdialog.ShopManager(w)
assert dlg.list.count() == 2
dlg.list.setCurrentRow(0)
dlg.price.setValue(25)
dlg.new()
dlg.provider.setCurrentIndex(dlg.provider.findData("stripe"))
dlg.st_key.setText("sk_test_x")
dlg.accept()
assert dlg.work["products"][0]["price"] == 25 and len(dlg.work["products"]) == 3 and dlg.work["provider"] == "stripe"
w.doc.shop = dlg.work
p = os.path.join(tempfile.mkdtemp(), "s.site")
w.doc.save(p)
assert len(Document.load(p).shop["products"]) == 3
d2 = Document()
d2.restore(w.doc.snapshot())
assert d2.shop["provider"] == "stripe"
print("ALL GOOD")

# the Task Monitor notices an unfinished shop, blog or poll
from sitewright import taskcheck
dd = Document()
dd.shop.update(provider="stripe", products=[dict(shop.new_product("Free"), price=0)])
dd.pages[0]["items"] += [new_item("product", 0, 0), new_item("cart", 0, 100), new_item("poll", 0, 200, options="Only one"),
                         new_item("blog", 0, 300)]
msgs = " | ".join(m for m, _p, _i in taskcheck.check(dd))
for needle in ("no product chosen", "Stripe is chosen but has no secret key", "has no price", "at least two choices", "no published posts"):
    assert needle in msgs, (needle, msgs)
dd.shop.update(provider="shopify", shopify_domain="x.myshopify.com")
assert "not linked to Shopify" in " | ".join(m for m, _p, _i in taskcheck.check(dd))
print("ALL GOOD")
