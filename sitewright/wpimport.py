"""Read WebPlus-style packages (.wpack, and any zip with the same XML layout).

Only the published container layout is used: a zip of XML parts (summary,
pp-pages/<guid>.xml, resources/<id>.xml, story/N.xml).  The result is a plain
Sitewright Document - nothing here depends on, or reproduces, the original
program.  Vector clip-art (.smf) and slider panels are not converted; they are
counted in the report so the owner can rebuild them.
"""
import os
import re
import zipfile
import xml.etree.ElementTree as ET

from . import model

UNIT = 750.0          # layout units per screen pixel (720000 units = a 960 px page)


def _px(v):
    return int(round(v / UNIT))


def _floats(s):
    return [float(x) for x in re.split(r"[,;]", s) if x != ""]


def _mat(el):
    """Affine matrix (a, b, tx, c, d, ty) from a Transform attribute."""
    t = el.get("Transform")
    if not t:
        return (1, 0, 0, 0, 1, 0)
    return tuple(_floats(t.split(":", 2)[2])[:6])


def _compose(outer, inner):
    a, b, tx, c, d, ty = outer
    A, B, TX, C, D, TY = inner
    return (a * A + b * C, a * B + b * D, a * TX + b * TY + tx,
            c * A + d * C, c * B + d * D, c * TX + d * TY + ty)


def _rect(el, m):
    """Pixel box (x, y, w, h) of the element's BBox under matrix m."""
    bb = _floats(el.get("BBox", "0,0,0,0"))
    xs, ys = [], []
    for px, py in ((bb[0], bb[1]), (bb[2], bb[1]), (bb[2], bb[3]), (bb[0], bb[3])):
        xs.append(m[0] * px + m[1] * py + m[2])
        ys.append(m[3] * px + m[4] * py + m[5])
    return (_px(min(xs)), _px(min(ys)), max(1, _px(max(xs) - min(xs))),
            max(1, _px(max(ys) - min(ys))))


def _hex(rgb):
    n = int(rgb)                       # stored as a Windows BGR integer
    return "#%02x%02x%02x" % (n & 255, (n >> 8) & 255, (n >> 16) & 255)


class _Pack:
    def __init__(self, path, image_dirs):
        self.z = zipfile.ZipFile(path)
        self.names = set(self.z.namelist())
        self.dirs = list(image_dirs) + [os.path.dirname(os.path.abspath(path))]
        self.scheme = []
        self.resources = {}
        self.stories = {}
        self.report = dict(pages=0, objects=0, vectors=0, sliders=0,
                           missing_pictures=[], found_pictures=0)
        self._load_support()

    def xml(self, name):
        raw = self.z.read(name).decode("utf-8-sig")
        return ET.fromstring(raw)

    def _load_support(self):
        self.refs = {}                 # any element that others point at with _ref
        for n in self.names:
            if not n.endswith(".xml"):
                continue
            if n.startswith("resources/") or n == "resources.xml":
                for o in self.xml(n).iter("_object"):
                    self.resources[o.get("_id")] = o
            elif n.startswith("story/") or n == "story.xml":
                root = self.xml(n)
                for o in root.iter("_object"):
                    self.stories[o.get("_id")] = o
                for e in root.iter():
                    if e.get("_id"):
                        self.refs[e.get("_id")] = e
            elif n.startswith(("spreads/", "masterspreads/")) or n == "document.xml":
                for e in self.xml(n).iter():
                    if e.get("_id"):
                        self.refs[e.get("_id")] = e

    def scheme_from(self, root):
        if self.scheme:
            return
        for s in root.iter("scheme"):
            cols = [c.get("rgb") for c in s.iter("_item") if c.get("rgb") is not None]
            if len(cols) >= 8:
                self.scheme = [_hex(c) for c in cols][:12]
                return

    def colour(self, el):
        """Colour element -> '#rrggbb' (scheme slots resolved)."""
        if el is None:
            return ""
        cls = el.get("_class")
        if cls == "CRGBColour":
            return _hex(el.get("rgb", "0"))
        if cls == "CHSLColour":
            import colorsys
            r, g, b = colorsys.hls_to_rgb(float(el.get("hue", "0")) / 360.0,
                                          float(el.get("lum", "0")), float(el.get("sat", "0")))
            return "#%02x%02x%02x" % (round(r * 255), round(g * 255), round(b * 255))
        if cls == "SchemeColour":
            i = int(el.get("index", "0"))
            if self.scheme and i < len(self.scheme):
                return self.scheme[i]
        return ""

    def fill(self, el):
        b = el.find("BrushFill")
        if b is None or b.get("_class") in (None, "CFillNone"):
            return ""
        if b.get("_class") == "CFillLinear":
            first = b.find("colours/_item")
            return self.colour(first)
        return self.colour(b.find("colour"))

    def find_picture(self, resource_id):
        r = self.resources.get(resource_id)
        if r is None:
            return ""
        data = (r.get("Data") or "").replace("\\", "/").replace("_bin_", "")
        if data and data in self.names:
            return "ZIP:" + data
        base = re.split(r"[\\/]", r.get("FileName", ""))[-1]
        for d in self.dirs:
            for sub in (d, os.path.join(d, "Images")):
                try:
                    for f in os.listdir(sub):
                        if f.lower() == base.lower():
                            return os.path.join(sub, f)
                except OSError:
                    pass
        return ""

    def story_colour(self, st):
        for e in st.iter():
            if e.tag == "_second" and e.get("_ref") in self.refs:
                e = self.refs[e.get("_ref")]
            if e.get("_class") == "ColourAtt":
                c = self.colour(e.find("Fill/colour"))
                if c:
                    return c
        return ""

    def story_by_ref(self, el, path="Layout/Story"):
        ref = el.find(path)
        return self.stories.get(ref.get("_ref")) if ref is not None else None

    def story_text(self, el):
        st = self.story_by_ref(el)
        if st is None:
            return "", 16, False
        paras, size, bold = [], 0, False
        for p in st.iter("p"):
            paras.append("".join(s.text or "" for s in p.iter("span")))
            for s in p.iter("span"):
                if s.get("Height") and not size:
                    size = max(8, _px(float(s.get("Height"))))
            if "Heading" in (p.get("Style") or ""):
                bold = True
        text = "\n".join(paras).strip()
        return text, size or (28 if bold else 16), bold


def _buttonish(el):
    return el.get("_class") in ("ButtonObject", "ButtonDesignObject", "ButtonNavBarObject",
                                "DrawingObject") and el.find(".//*[@_class='ButtonTextObject']") is not None


def _walk(pack, el, m, out, gid=""):
    """Convert one object (and children of groups) into Sitewright items."""
    if el.get("_ref") and not el.get("_class"):
        el = pack.refs.get(el.get("_ref"))
        if el is None:
            return
    before = len(out)
    _walk_one(pack, el, m, out, gid)
    link = el.find("Hyperlink")
    if link is not None and link.get("Type") == "Url" and link.get("LinkText"):
        for it in out[before:]:
            it["link"] = link.get("LinkText")


def _walk_one(pack, el, m, out, gid=""):
    cls = el.get("_class", "")
    m2 = _compose(m, _mat(el)) if el.get("Transform") else m
    if cls == "GroupObject":
        g = model.new_id()
        for ch in el:
            if ch.tag == "_item" and (ch.get("_class") or ch.get("_ref")):
                _walk(pack, ch, m2, out, g)
        return
    x, y, w, h = _rect(el, m2)
    over = dict(w=w, h=h, group=gid)
    pack.report["objects"] += 1
    if _buttonish(el):
        t = el.find(".//*[@_class='ButtonTextObject']")
        st = t.find("Style")
        over.update(text=t.get("Text", "Button"))
        if st is not None:
            over["font"] = st.get("Font", "Sans Serif")
            col = pack.colour(st.find("Colour"))
            if col:
                over["color"] = col
        if cls == "ButtonNavBarObject":
            out.append(model.new_item("navbar", x, y, **over))
        else:
            out.append(model.new_item("button", x, y, **over))
    elif cls == "BitmapObject":
        res = el.find("BitmapResource")
        path = pack.find_picture(res.get("_ref")) if res is not None else ""
        if path:
            pack.report["found_pictures"] += 1
            out.append(model.new_item("image", x, y, w=w, h=h, group=gid,
                                      asset=(path if path.startswith("ZIP:") else "PATH:" + path)))
        else:
            name = ""
            if res is not None and pack.resources.get(res.get("_ref")) is not None:
                name = re.split(r"[\\/]", pack.resources[res.get("_ref")].get("FileName", ""))[-1]
            pack.report["missing_pictures"].append(name or "?")
            out.append(model.new_item("rect", x, y, w=w, h=h, group=gid, fill="#d9dee5"))
    elif cls == "QuickShape":
        kind = "rect"
        qs = el.find("Qs")
        fill = pack.fill(el)
        extra = dict(fill=fill) if fill else dict(fill="")
        if qs is not None and qs.get("_class") == "S2DQuickRect":
            p = qs.find("param")
            if p is not None and p.get("value") not in (None, "0"):
                extra["radius"] = min(w, h) // 4
        out.append(model.new_item(kind, x, y, w=w, h=h, group=gid, **extra))
    elif cls == "Frame":
        text, size, bold = pack.story_text(el)
        if text:
            extra = {}
            st = pack.story_by_ref(el)
            col = pack.story_colour(st) if st is not None else ""
            if col:
                extra["color"] = col
            out.append(model.new_item("text", x, y, w=w, h=max(h, size + 8), group=gid,
                                      text=text, size=size, bold=bold, **extra))
    elif cls == "TableObject":
        cells = {}
        for c in el.iter("TableCellProxy"):
            col, row = (int(v) for v in c.get("Coord", "0,0").split(","))
            st = pack.story_by_ref(c, "Layout/Story")
            cells[(row, col)] = "\n".join("".join(sp.text or "" for sp in pp.iter("span"))
                                          for pp in st.iter("p")).strip() if st is not None else ""
        rows = 1 + max(r for r, _ in cells) if cells else 1
        cols = 1 + max(c for _, c in cells) if cells else 1
        grid = [[cells.get((r, c), "") for c in range(cols)] for r in range(rows)]
        out.append(model.new_item("table", x, y, w=w, h=h, group=gid, rows=rows, cols=cols,
                                  cells=grid, header=False))
    elif cls == "SMetaFileObject":
        pack.report["vectors"] += 1
    elif cls in ("WebSliderObject", "WebSliderPanelObject"):
        pack.report["sliders"] += 1
    elif cls.startswith(("WebForm", "Facebook", "GoogleMaps", "Twitter", "SocialNet")):
        pack.report.setdefault("other", []).append(cls)
    else:
        for ch in el:
            if ch.tag == "_item" and ch.get("_class"):
                _walk(pack, ch, m2, out, gid)


def _layer_items(pack, layer, out):
    for ch in layer:
        if ch.tag == "_item" and (ch.get("_class") or ch.get("_ref")):
            _walk(pack, ch, (1, 0, 0, 0, 1, 0), out)


def _spread_of(page_root):
    return page_root.find("_item/Objects/_item/DrawObject")


def _convert_page(pack, root):
    sp = _spread_of(root)
    master, items, bottom = [], [], 0
    if sp is None:
        return master, items, 700
    for lay in sp.findall("_item"):
        if lay.get("_class") != "Layer":
            continue
        for ms in lay.findall("MasterSpreads/_item"):
            for ml in ms.findall("_item"):
                if ml.get("_class") == "Layer":
                    _layer_items(pack, ml, master)
        if not (lay.find("Info") is not None and lay.find("Info").get("Name", "").startswith("Master Layer")):
            _layer_items(pack, lay, items)
    for i in items:
        bottom = max(bottom, i["y"] + i["h"])
    return master, items, max(700, bottom + 40)


def _spread_layers(root):
    sp = root if root.get("_class") == "Spread" else root.find("_item")
    return sp


def _convert_spread(pack, root):
    sp = _spread_layers(root)
    items, master = [], []
    if sp is not None:
        for lay in sp.findall("_item"):
            if lay.get("_class") == "Layer":
                _layer_items(pack, lay, items)
    return items


def _bottom(items):
    return max([i["y"] + i["h"] for i in items] + [0])


def import_site(pack, path):
    """A saved WebPlus site (.wpp): spreads/N.xml, masterspreads/1.xml, document.xml."""
    doc_root = pack.xml("document.xml")
    pack.scheme_from(doc_root)
    names = []
    for pp in doc_root.iter("PageProperties"):
        if pp.get("PageName") is not None:
            nm = pp.get("PageName")
            names.append((nm if nm != "<Untitled>" else "", pp.get("TitleText", ""),
                          pp.get("FileName", "")))
    doc = model.Document()
    doc.site_title = os.path.splitext(os.path.basename(path))[0]
    try:
        sm = pack.xml("summary.xml").find("Summary")
        if sm is not None and sm.get("SiteName"):
            doc.site_title = sm.get("SiteName")
    except KeyError:
        pass
    doc.pages = []
    if "masterspreads/1.xml" in pack.names:
        sp = pack.xml("masterspreads/1.xml")
        doc.master = _convert_spread(pack, sp)
    n = 1
    while "spreads/%d.xml" % n in pack.names:
        items = _convert_spread(pack, pack.xml("spreads/%d.xml" % n))
        nm, title, fname = names[n - 1] if n - 1 < len(names) else ("", "", "")
        label = nm or (os.path.splitext(fname)[0] if fname else "Page %d" % n)
        doc.pages.append(model.new_page(label, title=title or label,
                                        h=max(700, _bottom(items) + 40), items=items))
        pack.report["pages"] += 1
        n += 1
    if not doc.pages:
        raise ValueError("No pages could be read from this file.")
    return doc


def _embed_assets(pack, doc):
    if pack.scheme:
        doc.scheme = (pack.scheme + model.DEFAULT_SCHEME)[:12]
    import base64
    for lst in [p["items"] for p in doc.pages] + [doc.master]:
        for i in lst:
            a = str(i.get("asset", ""))
            if a.startswith("PATH:"):
                i["asset"] = doc.add_asset(a[5:])
            elif a.startswith("ZIP:"):
                aid = model.new_id()
                doc.assets[aid] = dict(name=os.path.basename(a[4:]),
                                       data=base64.b64encode(pack.z.read(a[4:])).decode())
                i["asset"] = aid


def import_pack(path, image_dirs=()):
    """Return (Document, report dict) for a WebPlus pack (.wpack) or site (.wpp)."""
    pack = _Pack(path, image_dirs)
    if "document.xml" in pack.names and "spreads/1.xml" in pack.names:
        doc = import_site(pack, path)
        _embed_assets(pack, doc)
        return doc, pack.report
    if "summary.xml" not in pack.names or not any(n.startswith("pp-pages/") for n in pack.names):
        raise ValueError("This file has no page data in the layout this importer reads.")
    for n in sorted(pack.names):          # the colour scheme is written out in full once
        if n.startswith(("pp-pages/", "pp-graphics/")) and not pack.scheme:
            pack.scheme_from(pack.xml(n))
    summary = pack.xml("summary.xml")
    order = []
    for it in summary.findall("pp-pages/_item"):
        tag = it.find("Tags/tag")
        label = (tag.text or "").split(";")[0] if tag is not None else "Page"
        order.append((it.get("Guid", "").strip("{}"), label or "Page", it.get("Master") == "1"))
    name = os.path.splitext(os.path.basename(path))[0]
    try:
        nm = pack.xml("document.xml").find("Name/name")
        if nm is not None and nm.text:
            name = nm.text
    except KeyError:
        pass
    doc = model.Document()
    doc.site_title = name
    doc.pages = []
    master_done = False
    for guid, label, is_master in order:
        part = "pp-pages/%s.xml" % guid
        if part not in pack.names:
            continue
        root = pack.xml(part)
        pack.scheme_from(root)
        master, items, h = _convert_page(pack, root)
        if not master_done and master:
            doc.master, master_done = master, True
        if is_master:
            continue
        doc.pages.append(model.new_page(label, h=h, items=items))
        pack.report["pages"] += 1
    if not doc.pages:
        raise ValueError("No pages could be read from this file.")
    _embed_assets(pack, doc)
    return doc, pack.report


def describe(report):
    bits = ["%d pages, %d objects" % (report["pages"], report["objects"])]
    if report["found_pictures"]:
        bits.append("%d pictures found" % report["found_pictures"])
    if report["missing_pictures"]:
        bits.append("%d pictures missing (grey boxes)" % len(report["missing_pictures"]))
    if report["vectors"]:
        bits.append("%d vector graphics skipped" % report["vectors"])
    if report.get("other"):
        bits.append("%d forms/maps/social objects skipped" % len(report["other"]))
    if report["sliders"]:
        bits.append("%d slider panels skipped" % report["sliders"])
    return ", ".join(bits)
