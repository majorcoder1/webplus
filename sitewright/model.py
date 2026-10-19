"""Document model: a site is a list of pages plus a shared master page."""
import base64
import copy
import json
import os

VERSION = 1

DEFAULT_SCHEME = ["#ffffff", "#222222", "#1f3a5f", "#2b7de9", "#e0813a", "#4a90d9",
                  "#2e9e5b", "#d64545", "#7a4fd1", "#4b5868", "#9aa3ad", "#f3f5f8"]

from .basics import TEXT_BASE, new_id  # noqa: E402,F401

DEFAULTS = {
    "text": dict(w=260, h=80, text="Your text here", fill="", stroke="", sw=0,
                 radius=0, link="", autoh=True, listtype="", overflow="hidden", **TEXT_BASE),
    "rect": dict(w=200, h=120, fill="#4a90d9", stroke="", sw=0, radius=0, link=""),
    "ellipse": dict(w=160, h=160, fill="#e0813a", stroke="", sw=0, link=""),
    "line": dict(w=200, h=0, stroke="#333333", sw=2, link=""),
    "image": dict(w=240, h=160, asset="", alt="", fit="cover", radius=0, link="",
                  hover_asset="", hover_effect="swap", lightbox=False, lightbox_asset="",
                  caption=""),
    "navbar": dict(w=600, h=44, fill="#1f3a5f", stroke="", sw=0, radius=0,
                   link="", orient="horizontal", gap=4, hover="#9cc4ff",
                   ifill="", ihover="#2f5a8f", hcolor="#ffffff", iradius=0,
                   ipad=16, uline="", active="#2f5a8f", acolor="#ffffff",
                   **dict(TEXT_BASE, color="#ffffff", size=15, bold=True)),
    "table": dict(w=480, h=150, rows=3, cols=3, header=True, fill="#ffffff",
                  hfill="#1f3a5f", hcolor="#ffffff", stroke="#c8ced6", sw=1,
                  link="",
                  cells=[["Header", "Header", "Header"], ["", "", ""], ["", "", ""]],
                  band="", sel=[0, 0, 0, 0], colw=[], rowh=[], merges=[], fmt={},
                  **dict(TEXT_BASE, size=15)),
    "gallery": dict(w=600, h=300, assets=[], cols=3, gap=10, fit="cover",
                    radius=0, link=""),
    "video": dict(w=480, h=270, url="", link=""),
    "map": dict(w=480, h=300, address="", zoom=14, link=""),
    "audio": dict(w=320, h=48, asset="", url="", link=""),
    "field": dict(w=260, h=36, ftype="text", label="", name="field", options="",
                  required=False, fill="#ffffff", stroke="#9aa3ad", sw=1,
                  radius=4, link="", answer="", rc_site="", rc_secret="",
                  **dict(TEXT_BASE, size=15)),
    "social": dict(w=260, h=40, nets=["facebook", "instagram", "x", "email"],
                   instagram_url="", youtube_url="", link=""),
    "html": dict(w=300, h=120, code="<p>Your HTML here</p>", link=""),
    "frame": dict(w=480, h=320, url="", link=""),
    "slider": dict(w=760, h=340, anim="slide", autoplay=True, loop=5000, speed=600,
                   arrows=True, dots=True, pause=True, start=1, link="",
                   panels=[dict(asset="", bg="#1f3a5f", heading="Welcome", color="#ffffff",
                                text="A few words about what you do.", btn="Learn more", link="",
                                align="left", overlay="#000000", overlay_op=0),
                           dict(asset="", bg="#2e7d4f", heading="Our work", color="#ffffff",
                                text="Show a highlight, an offer or a message.", btn="", link="",
                                align="center", overlay="#000000", overlay_op=0),
                           dict(asset="", bg="#7a4fd1", heading="Get in touch", color="#ffffff",
                                text="Tell people what to do next.", btn="Contact us", link="",
                                align="right", overlay="#000000", overlay_op=0)]),
    "search": dict(w=320, h=42, label="Search this site", btn="Search", fill="#ffffff",
                   stroke="#9aa3ad", sw=1, radius=4, btnfill="#2b7de9", btncolor="#ffffff",
                   link="", **dict(TEXT_BASE, size=15)),
    "searchresults": dict(w=620, h=320, empty="No pages matched your search.", link="",
                          **dict(TEXT_BASE, size=16)),
    "subscribe": dict(w=420, h=44, label="Your email address", btn="Subscribe", fill="#ffffff",
                      stroke="#9aa3ad", sw=1, radius=4, btnfill="#2b7de9", btncolor="#ffffff",
                      thanks="Thank you - you are on the list.", link="",
                      **dict(TEXT_BASE, size=15)),
    "login": dict(w=300, h=190, title="Members' login", btn="Log in", fill="#ffffff",
                  stroke="#9aa3ad", sw=1, radius=6, btnfill="#2b7de9", btncolor="#ffffff",
                  link="", **dict(TEXT_BASE, size=15)),
    "marquee": dict(w=500, h=40, text="Scrolling message", speed=10, fill="",
                    stroke="", sw=0, radius=0, link="", **TEXT_BASE),
    "arttext": dict(w=420, h=200, text="Artistic text", fill="", stroke="", sw=0, link="",
                    shape="arc", curve=45,
                    **dict(TEXT_BASE, size=44, bold=True, color="#1f3a5f", align="center")),
    "rssreader": dict(w=360, h=260, url="", count=5, show_date=True, show_desc=True, link="",
                      **dict(TEXT_BASE, size=15)),
    "hotspot": dict(w=140, h=90, shape="rect", link="", tip=""),
    "shape": dict(w=160, h=160, nodes=[], closed=True, preset="star", fill="#2b7de9", stroke="#1f3a5f", sw=2,
                  shadow=False, link=""),
    "repeater": dict(w=300, h=120, db="", cols=1, gap=16, limit=0, sort="", desc=False),
    "popup": dict(w=220, h=150, asset="", fit="cover", pop_asset="", pop_text="", pop_w=260,
                  pop_h=180, side="right", link="", alt=""),
    "button": dict(w=160, h=46, text="Button", fill="#2b7de9", stroke="", sw=0,
                   radius=6, link="", fill2="", hfill="#1f64c0", hcolor="#ffffff",
                   pfill="#174f98", shadow=False,
                   **dict(TEXT_BASE, color="#ffffff", size=16, bold=True,
                          align="center")),
}

ASSET_KEYS = ("asset", "hover_asset", "lightbox_asset", "pop_asset")


def asset_refs(item):
    """Every picture id an object uses, whichever field holds it."""
    out = [item.get(k) for k in ASSET_KEYS if item.get(k)]
    out += [a for a in item.get("assets") or [] if a]
    out += [p.get("asset") for p in item.get("panels") or [] if p.get("asset")]
    return out


def remap_assets(item, mapping):
    """Replace picture ids in place using mapping {old: new}."""
    for k in ASSET_KEYS:
        if item.get(k) in mapping:
            item[k] = mapping[item[k]]
    if item.get("assets"):
        item["assets"] = [mapping.get(a, a) for a in item["assets"]]
    for p in item.get("panels") or []:
        if p.get("asset") in mapping:
            p["asset"] = mapping[p["asset"]]


def default_seo():
    return dict(description="", author="", lang="en", site_url="", analytics="",
                google_verify="", bing_verify="", og_image="", favicon="", head_code="")


def default_feed():
    return dict(enabled=False, title="", description="", link="", author="", email="",
                category="", image="", explicit=False, items=[])


KIND_NAMES = {"text": "Text", "rect": "Rectangle", "ellipse": "Ellipse",
              "line": "Line", "image": "Picture", "button": "Button",
              "navbar": "Navigation bar", "table": "Table",
              "gallery": "Photo gallery", "video": "Video", "map": "Map",
              "audio": "Audio", "field": "Form field", "social": "Social buttons",
              "html": "HTML fragment", "marquee": "Scrolling message", "arttext": "Artistic text", "hotspot": "Hotspot", "rssreader": "RSS reader", "popup": "Pop-up rollover", "repeater": "Repeating area", "shape": "Shape",
              "frame": "Document frame", "slider": "Slider", "search": "Search box",
              "searchresults": "Search results", "subscribe": "Mailing list sign-up",
              "login": "Member login"}

FIELD_TYPES = ["text", "email", "textarea", "select", "checkbox", "radio",
               "date", "file", "captcha", "recaptcha", "submit"]
FIELD_LABELS = {"text": "Edit box", "email": "Email box", "textarea": "Text area",
                "select": "Combo box", "checkbox": "Check box",
                "radio": "Radio button", "date": "Date picker",
                "file": "File upload", "submit": "Submit button",
                "captcha": "CAPTCHA (a question to answer)", "recaptcha": "reCAPTCHA (Google)"}
FIELD_SIZES = {"captcha": (260, 38), "recaptcha": (304, 78), "textarea": (260, 100), "checkbox": (220, 28), "radio": (220, 28),
               "submit": (140, 42), "date": (200, 36)}


def new_item(kind, x=0, y=0, **over):
    d = copy.deepcopy(DEFAULTS[kind])
    d.update(kind=kind, id=new_id(), x=x, y=y, opacity=100, rot=0,
             fx=False, fy=False, locked=False, group="")
    d.update(over)
    return d


def new_page(name="Page", **over):
    p = dict(id=new_id(), name=name, title=name, h=700, bg="#ffffff",
             master=True, items=[], parent="", nav=True, type="page", url="",
             guides=dict(v=[], h=[]), description="", keywords="", robots="",
             og_image="", head_code="", css="", protect=False)
    p.update(over)
    return p


def ordered_pages(pages):
    """Depth-first order: each page followed by its children."""
    ids = {p["id"] for p in pages}
    kids = {}
    for p in pages:
        par = p.get("parent", "")
        kids.setdefault(par if par in ids else "", []).append(p)
    out = []

    def walk(par, depth):
        for p in kids.get(par, []):
            out.append((p, depth))
            walk(p["id"], depth + 1)
    walk("", 0)
    return out


def nav_entries(doc):
    """(label, link target, depth) for every page included in navigation."""
    out = []
    for p, depth in ordered_pages(doc.pages):
        if p.get("nav", True):
            tgt = p.get("url", "") if p.get("type") == "link" else "page:" + p["id"]
            out.append((p["name"], tgt, depth))
    return out


def real_pages(doc):
    return [p for p in doc.pages if p.get("type", "page") == "page"]


def upright(name, data):
    """Phone photos carry a hidden 'turn me' note (EXIF orientation). Browsers obey it and this editor
    does not, so the turning is done once, here, and the note is dropped. Returns the (maybe new) bytes."""
    if not name.lower().endswith((".jpg", ".jpeg", ".tif", ".tiff", ".webp", ".png")):
        return data
    try:
        import io
        from PIL import Image, ImageOps
        im = Image.open(io.BytesIO(data))
        if im.getexif().get(0x0112, 1) in (0, 1):
            return data
        fixed = ImageOps.exif_transpose(im)
        out = io.BytesIO()
        if name.lower().endswith((".jpg", ".jpeg")):
            fixed.convert("RGB").save(out, "JPEG", quality=94)
        elif name.lower().endswith(".webp"):
            fixed.save(out, "WEBP", quality=94)
        elif name.lower().endswith((".tif", ".tiff")):
            fixed.save(out, "TIFF")
        else:
            fixed.save(out, "PNG")
        return out.getvalue()
    except Exception:           # a picture Pillow cannot read is left exactly as it was
        return data


class Document:
    def __init__(self):
        self.site_title = "My Website"
        self.width = 960
        self.pages = [new_page("Home")]
        self.master = []
        self.masters = []               # more master pages: [{id, name, items}]
        self.assets = {}
        self.form_email = ""
        self.scheme = list(DEFAULT_SCHEME)
        self.styles = {}
        self.user = {}
        self.swatches = []
        self.publish = {}
        self.seo = default_seo()
        self.clean_urls = True
        self.feed = default_feed()
        self.members = []               # [{name, salt, hash}] - passwords are never stored
        self.list_key = ""              # secret that opens the subscriber list page
        self.form_mode = "php"          # php | mailto | custom
        self.form_action = ""
        self.databases = []             # Database Merge: [{id, name, fields, rows}]
        from .blog import default_blog
        self.blog = default_blog()     # the blog: settings and posts
        from .shop import default_shop
        self.shop = default_shop()     # the shop: settings and products
        self.path = ""

    # undo snapshots cover everything except the (append-only) asset store
    def snapshot(self):
        return json.dumps(dict(title=self.site_title, width=self.width,
                               pages=self.pages, master=self.master, masters=self.masters,
                               form_email=self.form_email, scheme=self.scheme,
                               styles=self.styles, user=self.user,
                               swatches=self.swatches, seo=self.seo,
                               clean_urls=self.clean_urls, feed=self.feed,
                               form_mode=self.form_mode, form_action=self.form_action,
                               members=self.members, list_key=self.list_key,
                               databases=self.databases, blog=self.blog, shop=self.shop),
                          sort_keys=True)

    def restore(self, snap):
        d = json.loads(snap)
        self.site_title, self.width = d["title"], d["width"]
        self.pages, self.master = d["pages"], d["master"]
        self.masters = d.get("masters", [])
        self.databases = d.get("databases", [])
        if d.get("blog"):
            self.blog = d["blog"]
        if d.get("shop"):
            self.shop = d["shop"]
        self.form_email = d.get("form_email", "")
        self.scheme = d.get("scheme") or list(DEFAULT_SCHEME)
        self.styles = d.get("styles", {})
        self.user = d.get("user", {})
        self.swatches = d.get("swatches", [])
        self.seo = dict(default_seo(), **d.get("seo", {}))
        self.clean_urls = d.get("clean_urls", True)
        self.feed = dict(default_feed(), **d.get("feed", {}))
        self.form_mode = d.get("form_mode", "php")
        self.form_action = d.get("form_action", "")
        self.members = d.get("members", [])
        self.list_key = d.get("list_key", "")

    # -- master pages: the main one (self.master) and any extra ones (self.masters)
    def all_masters(self):
        """[(id, name, items)]; the main master page has the id ''."""
        return [("", "Master page", self.master)] + [(m["id"], m["name"], m["items"]) for m in self.masters]

    def all_master_lists(self):
        return [items for _i, _n, items in self.all_masters()]

    def master_list(self, mid):
        if not mid:
            return self.master
        for m in self.masters:
            if m["id"] == mid:
                return m["items"]
        return self.master

    def master_items(self, page):
        """The objects of the master page a page uses (none when it uses no master page)."""
        m = page.get("master", True)
        if m is False or m is None:
            return []
        return self.master if m is True or m == "" else self.master_list(m)

    def used_assets_all(self):
        return list(self.assets)

    def add_asset(self, path):
        with open(path, "rb") as f:
            data = upright(os.path.basename(path), f.read())
        aid = new_id()
        self.assets[aid] = dict(name=os.path.basename(path),
                                data=base64.b64encode(data).decode())
        return aid

    def add_asset_bytes(self, name, data):
        data = upright(name, data)
        aid = new_id()
        self.assets[aid] = dict(name=name, data=base64.b64encode(data).decode())
        return aid

    def asset_bytes(self, aid):
        a = self.assets.get(aid)
        return base64.b64decode(a["data"]) if a else b""

    def used_assets(self):
        used = set()
        for p in self.pages:
            used.update(i.get("asset") for i in p["items"])
        used.update(i.get("asset") for lst in self.all_master_lists() for i in lst)
        used.add(self.seo.get("og_image", ""))
        used.add(self.seo.get("favicon", ""))
        used.add(self.feed.get("image", ""))
        used.update(i.get("asset", "") for i in self.feed.get("items", []))
        used.update(p.get("og_image", "") for p in self.pages)
        used.update((p.get("sound") or {}).get("asset", "") for p in self.pages)
        used.update(p.get("asset", "") for p in self.blog["posts"])
        used.update(p.get("asset", "") for p in self.shop["products"])
        for lst in [p["items"] for p in self.pages] + self.all_master_lists():
            for i in lst:
                used.update(asset_refs(i))
        return {k: v for k, v in self.assets.items() if k in used}

    def save(self, path):
        data = dict(version=VERSION, title=self.site_title, width=self.width,
                    form_email=self.form_email, scheme=self.scheme,
                    styles=self.styles, user=self.user, swatches=self.swatches,
                    publish=self.publish, seo=self.seo, clean_urls=self.clean_urls,
                    feed=self.feed, form_mode=self.form_mode,
                    form_action=self.form_action, members=self.members,
                    list_key=self.list_key, databases=self.databases, blog=self.blog, shop=self.shop,
                    pages=self.pages, master=self.master, masters=self.masters,
                    assets=self.used_assets())
        tmp = path + ".tmp"
        with open(tmp, "w") as f:
            json.dump(data, f)
        os.replace(tmp, path)
        self.path = path

    @classmethod
    def load(cls, path):
        with open(path) as f:
            d = json.load(f)
        doc = cls()
        doc.site_title = d.get("title", "My Website")
        doc.width = d.get("width", 960)
        doc.pages = d.get("pages") or [new_page("Home")]
        doc.master = d.get("master", [])
        doc.masters = d.get("masters", [])
        doc.databases = d.get("databases", [])
        if d.get("blog"):
            doc.blog = d["blog"]
        if d.get("shop"):
            doc.shop = d["shop"]
        doc.form_email = d.get("form_email", "")
        doc.scheme = d.get("scheme") or list(DEFAULT_SCHEME)
        doc.styles = d.get("styles", {})
        doc.user = d.get("user", {})
        doc.swatches = d.get("swatches", [])
        doc.publish = d.get("publish", {})
        doc.seo = dict(default_seo(), **d.get("seo", {}))
        doc.clean_urls = d.get("clean_urls", True)
        doc.feed = dict(default_feed(), **d.get("feed", {}))
        doc.form_mode = d.get("form_mode", "php")
        doc.form_action = d.get("form_action", "")
        doc.members = d.get("members", [])
        doc.list_key = d.get("list_key", "")
        doc.assets = d.get("assets", {})
        for a in doc.assets.values():           # photos saved sideways by an older version are turned upright now
            if a["name"].lower().endswith((".jpg", ".jpeg", ".tif", ".tiff", ".webp")):
                raw = base64.b64decode(a["data"])
                fixed = upright(a["name"], raw)
                if fixed is not raw:
                    a["data"] = base64.b64encode(fixed).decode()
        doc.path = path
        return doc


from . import webapps  # noqa: E402
webapps.install(DEFAULTS, KIND_NAMES)
