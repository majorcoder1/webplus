"""Write a finished website: one HTML file per page, one style.css, images/."""
import hashlib
import html
import os
import re

from . import extras as _extras
from . import phpgen
from . import objectprops
from .extras import EXTRA_KINDS, export_extra, send_php

SERIF_HINTS = ("serif", "times", "georgia", "garamond", "playfair", "merriweather",
               "palatino", "cambria", "book", "lora")


def slug(name):
    s = re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")
    return s or "page"


def page_files(doc, clean=None, php=True):
    """Map page id -> file path; the first page is index.html. With clean
    addresses every other page is name/index.html, so the web address is /name/."""
    if clean is None:
        clean = getattr(doc, "clean_urls", True)
    out, used, first = {}, set(), True
    for p in doc.pages:
        if p.get("type", "page") == "link":
            out[p["id"]] = p.get("url", "")
            continue
        if p.get("type") == "html" and p.get("filename") and not first:
            fn = p["filename"]
            stem = fn.rsplit(".", 1)[0]
            while stem in used:
                stem += "-2"
            used.add(stem)
            out[p["id"]] = stem + fn[len(fn.rsplit(".", 1)[0]):]
            continue
        base = "index" if first else slug(p["name"])
        name, k = base, 2
        while name in used:
            name, k = "%s-%d" % (base, k), k + 1
        used.add(name)
        ext = "php" if (php and p.get("protect")) else "html"
        if first:
            out[p["id"]] = "index." + ext
        elif clean:
            out[p["id"]] = name + "/index." + ext
        else:
            out[p["id"]] = name + "." + ext
        first = False
    return out


def page_urls(files, cur, clean):
    """The address of every page as seen from the page file `cur`."""
    import posixpath
    cur_dir = posixpath.dirname(cur)
    out = {}
    for pid, f in files.items():
        if not f or "://" in f or f.startswith(("mailto:", "tel:", "#")):
            out[pid] = f
            continue
        target = f
        if clean and target.endswith(("index.html", "index.php")):
            target = target[:target.rfind("index.")]
        rel = posixpath.relpath(target or ".", cur_dir or ".")
        if (target == "" or target.endswith("/")) and not rel.endswith("/"):
            rel += "/"
        out[pid] = rel
    return out


def generic_family(font):
    f = font.lower()
    if "mono" in f or "courier" in f:
        return "monospace"
    if "sans" not in f and any(h in f for h in SERIF_HINTS):
        return "serif"
    return "sans-serif"


def css_color(c):
    return c if c else "transparent"


def asset_names(doc):
    names, used = {}, set()
    for aid, a in doc.assets.items():
        base = re.sub(r"[^A-Za-z0-9._-]", "_", a["name"]) or aid
        name, k = base, 2
        while name in used:
            stem, ext = os.path.splitext(base)
            name, k = "%s-%d%s" % (stem, k, ext), k + 1
        used.add(name)
        names[aid] = name
    return names


def resolve_link(link, files):
    if link.startswith("toggle:"):
        return "#"
    if link.startswith("page:"):
        return files.get(link[5:], "")
    if link.startswith("anchor:"):
        pid, _, name = link[7:].partition("#")
        if pid == _current:
            return "#" + name
        return files.get(pid, "") + "#" + name
    return link


def href_for(d, files):
    return resolve_link(d.get("link", ""), files)


from . import imagefx  # noqa: E402

_page_css = []      # extra CSS rules collected while one page is being written
_page_js = []       # script lines for objects' Actions, collected the same way
_page_items = {}    # id -> object, for the page being written
_derived = {}       # file name -> picture object that needs its own processed file
_current = None     # id of the page being written (for the "on" menu state)


def popup_html(d, files):
    rows = []
    for line in (d.get("popup") or "").splitlines():
        if not line.strip():
            continue
        label, _, target = line.partition("|")
        href = resolve_link(target.strip(), files)
        rows.append('<a href="%s">%s</a>' % (html.escape(href, quote=True), html.escape(label.strip())))
    return '<div class="pop">%s</div>' % "".join(rows) if rows else ""


USER_TOKENS = {"name": "username", "company": "companyname", "job": "companyjob",
               "address1": "companyaddress1", "address2": "companyaddress2",
               "address3": "companyaddress3", "address4": "companyaddress4",
               "phone": "companyphone", "mobile": "companymobile",
               "email": "companyemail", "web": "companyweb", "motto": "companymotto"}


def token_values(doc, page=None):
    """Everything a %token% can turn into when the site is published."""
    import datetime
    now = datetime.datetime.now()
    hour12 = now.hour % 12 or 12
    values = {
        "sitename": doc.site_title, "sitetitle": doc.site_title,
        "sitepages": str(sum(1 for p in doc.pages if p.get("type", "page") == "page")),
        "siteurl": (getattr(doc, "seo", {}) or {}).get("site_url", ""),
        "date": "%s %d, %d" % (now.strftime("%B"), now.day, now.year),
        "shortdate": "%d/%d/%d" % (now.month, now.day, now.year),
        "isodate": now.strftime("%Y-%m-%d"),
        "weekday": now.strftime("%A"), "month": now.strftime("%B"),
        "day": str(now.day), "year": str(now.year),
        "time": "%d:%02d %s" % (hour12, now.minute, "AM" if now.hour < 12 else "PM"),
        "time24": now.strftime("%H:%M"),
    }
    pages = [p for p in doc.pages if p.get("type", "page") == "page"]
    if page is not None:
        values["pagename"] = page["name"]
        values["pagetitle"] = page.get("title") or page["name"]
        values["pagenumber"] = str(pages.index(page) + 1) if page in pages else ""
        values["pagecount"] = str(len(pages))
    for k, token in USER_TOKENS.items():
        values[token] = (getattr(doc, "user", {}) or {}).get(k, "")
    return values


def replace_tokens(text, values):
    for token, val in values.items():
        text = text.replace("%" + token + "%", val)
    return text


def fill_tokens(d, doc):
    """Replace %companyname%, %sitename%, %date% ... in an item's text fields."""
    if doc is None:
        return d
    page = next((p for p in doc.pages if p["id"] == _current), None)
    values = token_values(doc, page)
    out = None
    for key in ("text", "code", "label", "address"):
        v = d.get(key)
        if isinstance(v, str) and "%" in v:
            v = replace_tokens(v, values)
            if v != d[key]:
                out = out or dict(d)
                out[key] = v
    if d.get("kind") == "table" and any("%" in c for row in d.get("cells", []) for c in row):
        cells = [[replace_tokens(c, values) for c in row] for row in d["cells"]]
        if cells != d["cells"]:
            out = out or dict(d)
            out["cells"] = cells
    return out or d


def item_html(d, files, anames, doc=None):
    d = fill_tokens(d, doc)
    out = item_html_inner(d, files, anames, doc)
    if out.startswith("<"):
        out = re.sub(r"^<(\w+)", r'<\1 data-k="%s"' % d["kind"], out, 1)
    ident = d.get("ident") or d.get("anchor")
    if ident and out.startswith("<"):
        name = re.sub(r"[^A-Za-z0-9_-]", "-", ident)
        out = re.sub(r"^<(\w+)", r'<\1 id="%s"' % name, out, 1)
    if d.get("cls") and 'class="o' in out:
        out = out.replace('class="o', 'class="o ' + re.sub(r"[^A-Za-z0-9_ -]", "", d["cls"]), 1)
    if d.get("group") and out.startswith("<"):
        out = re.sub(r"^<(\w+)", r'<\1 data-grp="%s"' % d["group"], out, 1)
    if d.get("link", "").startswith("toggle:") and out.startswith("<"):
        out = re.sub(r"^<(\w+)", r'<\1 data-toggle="%s"'
                     % re.sub(r"[^A-Za-z0-9_-]", "-", d["link"][7:]), out, 1)
    if d.get("hidden"):
        out = out.replace('style="', 'style="display:none;', 1)
    if d.get("tab") and d["kind"] == "field":
        out = re.sub(r"<(input|select|textarea|button)\b", r'<\1 tabindex="%d"' % d["tab"], out, 1)
    flt = imagefx.css_filter(d.get("effects")) if d.get("effects") else ""
    if d.get("shadow") and d["kind"] == "shape":
        flt = (flt + " drop-shadow(0 3px 4px rgba(0,0,0,.35))").strip()
    if flt and out.startswith("<") and 'style="' in out:
        out = out.replace('style="', 'style="filter:%s;' % flt, 1)
    pop = popup_html(d, files) if d["kind"] not in ("navbar", "line", "field") else ""
    if pop and "</" in out:
        i = out.rfind("</")
        out = out[:i] + pop + out[i:]
        out = out.replace('class="o', 'class="o pm', 1)
        m = re.match(r'<\w+[^>]*?style="([^"]*)"', out)
        if m and "overflow:hidden" in m.group(1):          # the menu hangs below the object, so it must not be clipped
            out = out.replace(m.group(1), m.group(1).replace("overflow:hidden", "overflow:visible"), 1)
    return objectprops.markup(out, d, _page_css, _page_js, _page_items, lambda v: resolve_link(v, files))


def item_html_inner(d, files, anames, doc=None):
    kind = d["kind"]
    st = ["left:%dpx" % round(d["x"]), "top:%dpx" % round(d["y"]),
          "width:%dpx" % round(d["w"]), "height:%dpx" % round(d["h"])]
    tf = []
    if d.get("rot"):
        tf.append("rotate(%ddeg)" % d["rot"])
    if d.get("fx") or d.get("fy"):
        tf.append("scale(%d,%d)" % (-1 if d.get("fx") else 1, -1 if d.get("fy") else 1))
    if tf:
        st.append("transform:" + " ".join(tf))
    if d.get("opacity", 100) != 100:
        st.append("opacity:%.2f" % (d["opacity"] / 100))
    href = "" if d.get("popup") else href_for(d, files)
    tag = "a" if href else "div"
    attr = ' href="%s"' % html.escape(href, quote=True) if href else ""
    if href and re.match(r"https?:", href):
        attr += ' rel="noopener"'

    if kind == "navbar":
        return navbar_html(d, st, files, doc)
    if kind in EXTRA_KINDS:
        return export_extra(d, st, tag, attr, files, anames)

    if kind == "line":
        w, h = max(d["w"], 1), max(d["h"], 1)
        sw = max(d.get("sw", 2), 1)
        st[3] = "height:%dpx" % round(max(d["h"], sw))
        svg = ('<svg width="%d" height="%d" viewBox="0 0 %d %d" style="overflow:visible">'
               '<line x1="0" y1="0" x2="%d" y2="%d" stroke="%s" stroke-width="%d"/></svg>'
               % (w, max(d["h"], sw), w, max(d["h"], sw), d["w"], d["h"],
                  d.get("stroke") or "#000", sw))
        return '<%s class="o"%s style="%s">%s</%s>' % (tag, attr, ";".join(st), svg, tag)

    if kind == "image" and d.get("asset") not in anames and not d.get("asset") and not d.get("srcurl"):
        return ""                      # an empty picture frame is left out of the published page
    if kind == "image":
        src = "images/" + anames.get(d.get("asset"), "missing.png")
        if d.get("srcurl"):
            src = d["srcurl"]
        if imagefx.is_derived(doc, d):
            key = imagefx.cache_key(doc, d, imagefx.export_width(d))
            fname = "fx-%s.png" % hashlib.md5(key.encode()).hexdigest()[:10]
            _derived[fname] = d
            src = "images/" + fname
        fit = {"cover": "cover", "contain": "contain", "fill": "fill"}.get(d.get("fit"), "cover")
        clip, extra = "", ""
        if d.get("cropshape"):
            # the picture itself is cut to the shape, so a glow or shadow on the frame follows the shape
            from . import shapes
            nodes, closed = shapes.shape_nodes(d["cropshape"])
            cid = "cs-" + re.sub(r"[^A-Za-z0-9_-]", "", d["id"])
            clip = "clip-path:url(#%s);" % cid
            extra = ('<svg width="0" height="0" style="position:absolute"><clipPath id="%s" clipPathUnits="objectBoundingBox">'
                     '<path d="%s"/></clipPath></svg>' % (cid, shapes.svg_d(nodes, closed, 1, 1)))
            if d.get("bw"):
                extra += ('<svg viewBox="0 0 %d %d" preserveAspectRatio="none" style="position:absolute;left:0;top:0;'
                          'width:100%%;height:100%%;overflow:visible;pointer-events:none"><path d="%s" fill="none" '
                          'stroke="%s" stroke-width="%s" stroke-linejoin="round" vector-effect="non-scaling-stroke"/></svg>'
                          % (round(d["w"]), round(d["h"]), shapes.svg_d(nodes, closed, max(d["w"], 1), max(d["h"], 1)),
                             d.get("bcolor") or "#000", d["bw"]))
        else:
            if d.get("radius"):
                if d.get("popup"):
                    clip = "border-radius:%dpx;" % d["radius"]         # round the picture, not the frame the menu hangs from
                else:
                    st.append("border-radius:%dpx;overflow:hidden" % d["radius"])
            if d.get("bw"):
                st.append("border:%dpx solid %s;box-sizing:border-box" % (d["bw"], d.get("bcolor") or "#000"))
        img = '<img src="%s" alt="%s" style="%swidth:100%%;height:100%%;object-fit:%s;display:block">' % (
            html.escape(src, quote=True), html.escape(d.get("alt", ""), quote=True), clip, fit)
        cls_ = "o"
        effect = d.get("hover_effect", "swap")
        if d.get("hover_asset") in anames and effect in ("swap", "fade"):
            alt_src = "images/" + anames[d["hover_asset"]]
            img += ('<img class="ro-b" src="%s" alt="" aria-hidden="true" style="position:absolute;'
                    'left:0;top:0;%swidth:100%%;height:100%%;object-fit:%s;display:block">'
                    % (html.escape(alt_src, quote=True), clip, fit))
            cls_ = "o ro"
        elif effect in ("zoom", "bright"):
            cls_ = "o ro-" + ("z" if effect == "zoom" else "br")
        if d.get("lightbox"):
            big = d.get("lightbox_asset") if d.get("lightbox_asset") in anames else d.get("asset")
            if big in anames:
                st.append("cursor:zoom-in")
                attr += ' data-lb="images/%s" data-cap="%s"' % (
                    html.escape(anames[big], quote=True),
                    html.escape(d.get("caption") or d.get("alt", ""), quote=True))
        if cls_ != "o" and (cls_ == "o ro-z" or not d.get("cropshape")):
            st.append("overflow:hidden")
        return '<%s class="%s"%s style="%s">%s%s</%s>' % (tag, cls_, attr, ";".join(st), img, extra, tag)

    if kind in ("button", "rect", "ellipse", "text") and d.get("fill2") and d.get("fill"):
        st.append("background:linear-gradient(180deg,%s,%s)" % (d["fill"], d["fill2"]))
    else:
        st.append("background:" + css_color(d.get("fill", "")))
    if d.get("sw") and d.get("stroke"):
        st.append("border:%dpx %s %s;box-sizing:border-box"
                  % (d["sw"], {"dashed": "dashed", "dotted": "dotted"}.get(
                      d.get("sstyle"), "solid"), d["stroke"]))
    cls = "o"
    if d.get("shadow") and kind in ("button", "rect", "ellipse", "text"):
        st.append("box-shadow:0 3px 6px rgba(0,0,0,.3)")
    if kind == "button":
        cls = "o b-" + d["id"]
        st.append("transition:background .15s,color .15s")
        if d.get("hfill") or d.get("hcolor"):
            _page_css.append(".b-%s:hover{%s%s}" % (
                d["id"], ("background:" + d["hfill"] + ";") if d.get("hfill") else "",
                ("color:" + d["hcolor"]) if d.get("hcolor") else ""))
        if d.get("pfill"):
            _page_css.append(".b-%s:active{background:%s}" % (d["id"], d["pfill"]))
    if kind == "ellipse":
        st.append("border-radius:50%")
    elif d.get("radius"):
        st.append("border-radius:%dpx" % d["radius"])
    body = ""
    if kind in ("text", "button"):
        st.append("font-family:'%s',%s" % (d["font"], generic_family(d["font"])))
        st.append("font-size:%dpx" % d["size"])
        st.append("color:" + d["color"])
        st.append("text-align:" + d["align"])
        st.append("font-weight:" + ("bold" if d.get("bold") else "normal"))
        st.append("font-style:" + ("italic" if d.get("italic") else "normal"))
        ov = d.get("overflow", "hidden") if kind == "text" else "hidden"
        st.append("overflow:%s;white-space:pre-wrap;overflow-wrap:anywhere;word-break:break-word" % ov)
        if kind == "button":
            st.append("display:flex;align-items:center;justify-content:%s;text-decoration:none"
                      % {"left": "flex-start", "right": "flex-end"}.get(d["align"], "center"))
            tag = "a" if href else "div"
        body = html.escape(d.get("text", ""))
        from .textlayout import LIST_BY_VALUE
        ls = LIST_BY_VALUE.get(d.get("listtype", ""))
        if kind == "text" and ls and ls[3] and d.get("htag") not in ("h1", "h2", "h3", "h4", "h5", "h6"):
            items = "".join("<li>%s</li>" % html.escape(line) for line in d.get("text", "").split("\n"))
            body = '<%s style="margin:0;padding-left:22px;list-style-type:%s">%s</%s>' % (ls[4], ls[3], items, ls[4])
            st[:] = [x.replace("white-space:pre-wrap", "white-space:normal") for x in st]
    if kind == "text" and d.get("htag") in ("h1", "h2", "h3", "h4", "h5", "h6") and not href:
        tag = d["htag"]
    return '<%s class="%s"%s style="%s">%s</%s>' % (tag, cls, attr, ";".join(st), body, tag)


def navbar_html(d, st, files, doc):
    """Navigation as nested lists; style rules go in the page's <style>."""
    from .model import nav_entries
    cls = "nv-" + d["id"]
    orient = d.get("orient", "horizontal")
    vertical = orient == "vertical"
    fam = "'%s',%s" % (d["font"], generic_family(d["font"]))
    col, hcol = d["color"], d.get("hcolor") or d["color"]
    pad = d.get("ipad", 14)
    just = {"left": "flex-start", "right": "flex-end"}.get(d.get("align"), "center")
    bar = ["background:" + css_color(d.get("fill", "")), "padding:0 8px",
           "align-items:" + ("flex-start" if vertical else "center"),
           "justify-content:" + ("flex-start" if vertical else just),
           "display:flex", "overflow:visible"]
    if d.get("radius"):
        bar.append("border-radius:%dpx" % d["radius"])
    if d.get("sw") and d.get("stroke"):
        bar.append("border:%dpx solid %s" % (d["sw"], d["stroke"]))
    rules = [
        ".%s{%s}" % (cls, ";".join(bar)),
        ".%s ul{list-style:none;margin:0;padding:0;display:flex;flex-direction:%s;gap:%dpx}"
        % (cls, "column" if vertical else "row", d.get("gap", 4)),
        ".%s{width:%dpx;height:%dpx}" % (cls, d["w"], d["h"]),
        ".%s li{position:relative}" % cls,
        ".%s a{display:block;padding:%dpx %dpx;color:%s;background:%s;border-radius:%dpx;"
        "font-family:%s;font-size:%dpx;font-weight:%s;font-style:%s;text-decoration:none;"
        "white-space:nowrap;transition:background .15s,color .15s}"
        % (cls, pad // 2, pad, col, css_color(d.get("ifill", "")), d.get("iradius", 0), fam,
           d["size"], "bold" if d.get("bold") else "normal",
           "italic" if d.get("italic") else "normal"),
    ]
    if d.get("ihover") or d.get("hcolor"):
        rules.append(".%s a:hover{background:%s;color:%s}"
                     % (cls, css_color(d.get("ihover", "")), hcol))
    on = ["color:" + (d.get("acolor") or col)] if d.get("active") else []
    if d.get("active"):
        on.append("background:" + d["active"])
    if d.get("uline"):
        on.append("border-bottom:3px solid " + d["uline"])
    if on:
        rules.append(".%s a.on{%s}" % (cls, ";".join(on)))
    if orient == "dropdown":
        rules += [".%s .sub{display:none;position:absolute;left:0;top:100%%;z-index:30;"
                  "flex-direction:column;gap:0;background:%s;min-width:100%%;"
                  "box-shadow:0 6px 14px rgba(0,0,0,.25)}" % (cls, d.get("fill") or "#fff"),
                  ".%s li:hover>.sub{display:flex}" % cls]
    elif vertical:
        rules.append(".%s .sub a{padding-left:%dpx}" % (cls, pad + 16))
    _page_css.extend(rules)

    entries = nav_entries(doc) if doc else []
    items, top = [], None
    for label, tgt, depth in entries:
        href = files.get(tgt[5:], "") if tgt.startswith("page:") else tgt
        a = '<a href="%s"%s>%s</a>' % (
            html.escape(href, quote=True),
            ' class="on" aria-current="page"' if tgt == "page:" + (_current or "") else "",
            html.escape(label))
        if depth == 0 or top is None:
            top = [a, []]
            items.append(top)
        elif orient in ("dropdown", "vertical"):
            top[1].append(a)
    lis = []
    for a, subs in items:
        sub_html = ('<ul class="sub">%s</ul>' % "".join("<li>%s</li>" % s for s in subs)) if subs else ""
        lis.append("<li>%s%s</li>" % (a, sub_html))
    st2 = [x for x in st if x.startswith(("left:", "top:", "transform:", "opacity:"))]
    return '<nav class="o %s" style="%s"><ul>%s</ul></nav>' % (cls, ";".join(st2), "".join(lis))


def abs_url(site_url, path):
    return (site_url.rstrip("/") + "/" + path.lstrip("/")) if site_url else path


def page_path(files, pid, clean):
    f = files.get(pid, "")
    if clean and f.endswith(("index.html", "index.php")):
        f = f[:f.rfind("index.")]
    return f


def head_html(doc, page, files, anames, clean):
    seo = getattr(doc, "seo", {}) or {}
    url = seo.get("site_url", "").strip()
    desc = (page.get("description") or seo.get("description") or "").strip()
    title = (page.get("title") or page["name"]).strip()
    full = "%s - %s" % (title, doc.site_title) if doc.site_title and title != doc.site_title else title
    out = ['<title>%s</title>' % html.escape(full)]
    if desc:
        out.append('<meta name="description" content="%s">' % html.escape(desc, quote=True))
    if page.get("keywords"):
        out.append('<meta name="keywords" content="%s">' % html.escape(page["keywords"], quote=True))
    if seo.get("author"):
        out.append('<meta name="author" content="%s">' % html.escape(seo["author"], quote=True))
    if page.get("robots"):
        out.append('<meta name="robots" content="%s">' % html.escape(page["robots"], quote=True))
    path = page_path(files, page["id"], clean)
    canon = abs_url(url, path) if url else ""
    if canon and not page.get("robots"):
        out.append('<link rel="canonical" href="%s">' % html.escape(canon, quote=True))
    og_asset = page.get("og_image") or seo.get("og_image")
    og = [("og:type", "website"), ("og:title", title), ("og:site_name", doc.site_title)]
    if desc:
        og.append(("og:description", desc))
    if canon:
        og.append(("og:url", canon))
    if og_asset in anames:
        og.append(("og:image", abs_url(url, "images/" + anames[og_asset])))
    for k, v in og:
        out.append('<meta property="%s" content="%s">' % (k, html.escape(v, quote=True)))
    out.append('<meta name="twitter:card" content="%s">'
               % ("summary_large_image" if og_asset in anames else "summary"))
    if seo.get("google_verify"):
        out.append('<meta name="google-site-verification" content="%s">'
                   % html.escape(seo["google_verify"], quote=True))
    if seo.get("bing_verify"):
        out.append('<meta name="msvalidate.01" content="%s">'
                   % html.escape(seo["bing_verify"], quote=True))
    if seo.get("favicon") in anames:
        out.append('<link rel="icon" href="images/%s">' % html.escape(anames[seo["favicon"]]))
    feed = getattr(doc, "feed", {}) or {}
    if feed.get("enabled"):
        out.append('<link rel="alternate" type="application/rss+xml" title="%s" href="feed.xml">'
                   % html.escape(feed.get("title") or doc.site_title, quote=True))
    ga = seo.get("analytics", "").strip()
    if re.match(r"^G-[A-Z0-9]+$", ga):
        out.append('<script async src="https://www.googletagmanager.com/gtag/js?id=%s"></script>'
                   '<script>window.dataLayer=window.dataLayer||[];function gtag(){dataLayer.push(arguments);}'
                   "gtag('js',new Date());gtag('config','%s');</script>" % (ga, ga))
    if seo.get("head_code"):
        out.append(seo["head_code"])
    if page.get("head_code"):
        out.append(page["head_code"])
    return "\n".join(out)


TOGGLE_JS = """<script>
document.addEventListener('click',function(e){
var t=e.target.closest('[data-toggle]');if(!t)return;e.preventDefault();
var id=t.getAttribute('data-toggle');
var list=[].slice.call(document.querySelectorAll('[data-grp="'+id+'"]'));
var one=document.getElementById(id);if(one)list.push(one);
list.forEach(function(el){el.style.display=(el.style.display==='none')?'':'none';});
});
</script>
"""


def page_html(doc, page, files, anames, clean=None):
    global _current
    if page.get("type") == "html":
        from .htmlpage import page_text
        return page_text(page)
    if clean is None:
        clean = getattr(doc, "clean_urls", True)
    del _page_css[:]
    del _page_js[:]
    _current = page["id"]
    cur_file = files[page["id"]]
    urls = page_urls(files, cur_file, clean)
    prefix = "../" * cur_file.count("/")
    items = doc.master_items(page) + page["items"]
    from . import databasemerge
    items, page = databasemerge.expand(doc, page, items)
    _page_items.clear()
    _page_items.update({i["id"]: i for i in items})
    objectprops.markup.targets = objectprops.targets(items)
    _extras.CONTEXT.update(doc=doc, shop_booted=False, index=search_index(doc, files, clean), prefix=prefix, forms=[], scripts=[],
                           salt=_extras.captcha_salt(doc.site_title, doc.form_email))
    body = "\n".join(item_html(i, urls, anames, doc) for i in items)
    extra_css = "".join(_page_css) + (page.get("css") or "")
    kinds = {i["kind"] for i in items}
    scripts = ""
    if "field" in kinds:
        mode = getattr(doc, "form_mode", "php")
        action = {"mailto": "mailto:" + doc.form_email,
                  "custom": getattr(doc, "form_action", "")}.get(mode, "send.php")
        enc = ' enctype="text/plain"' if mode == "mailto" else ""
        body = ('<form method="post" action="%s"%s class="frm">\n%s\n'
                '<input type="text" name="website" tabindex="-1" autocomplete="off" '
                'style="position:absolute;left:-9999px">\n'
                '<input type="hidden" name="_page" value="%s"></form>'
                % (html.escape(action, quote=True), enc, body,
                   html.escape(page["name"], quote=True)))
        scripts += ("<script>if(/[?&]sent=1/.test(location.search))alert('Thank you - your message "
                    "was sent.');else if(/[?&]sent=0/.test(location.search))alert('Sorry, the message "
                    "could not be sent.');else if(/[?&]sent=captcha/.test(location.search))alert('The answer to the question "
                    "was not right. Please try again.');</script>\n")
    from .pageitems import sound_html
    scripts += sound_html(page, anames)
    if _page_js:
        scripts += "<script>\n" + "\n".join(_page_js) + "\n</script>\n"
    if "gallery" in kinds or any(i.get("lightbox") for i in items):
        scripts += GALLERY_JS
    if "social" in kinds:
        scripts += SOCIAL_JS
    if any(i.get("link", "").startswith("toggle:") for i in items):
        scripts += TOGGLE_JS
    if "subscribe" in kinds:
        scripts += ("<script>if(/[?&]joined=1/.test(location.search))alert('Thank you - you are on "
                    "the list.');else if(/[?&]joined=0/.test(location.search))alert('Sorry, that "
                    "email address did not look right.');</script>\n")
    body += "\n" + "\n".join(_extras.CONTEXT["forms"])
    scripts += "\n".join(_extras.CONTEXT["scripts"])
    w, h = doc.width, page["h"]
    lang = html.escape((getattr(doc, "seo", {}) or {}).get("lang") or "en", quote=True)
    head = head_html(doc, page, files, anames, clean)
    out = """<!doctype html>
<html lang="%(lang)s">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">
%(head)s
<link rel="stylesheet" href="style.css">
<style>html,body{background:%(bg)s}.stage{width:%(w)dpx;height:%(h)dpx;background:%(bg)s}%(extra)s</style>
</head>
<body>
<div class="wrap"><div class="stage">
%(body)s
</div></div>
%(responsive)s
%(scripts)s</body>
</html>
""" % dict(lang=lang, head=head, responsive=RESPONSIVE_JS.replace('__W__', str(w)).replace('__H__', str(h)),
           extra=extra_css, scripts=scripts, bg=page.get("bg", "#fff"), w=w, h=h, body=body)
    if prefix:      # pages in a sub-folder reach the shared files one level up
        out = re.sub(r'(src|href|action|data-lb)="(images/|style\.css|feed\.xml|send\.php|subscribe\.php|sw-auth\.php)',
                     lambda m: '%s="%s%s' % (m.group(1), prefix, m.group(2)), out)
    return out


def search_index(doc, files, clean):
    """What the on-site search looks through: title, description and the words on
    each page. Private (member) and hidden pages are left out."""
    out = []
    for p in doc.pages:
        if p.get("type", "page") != "page" or p.get("protect") or "noindex" in (p.get("robots") or ""):
            continue
        words = [p.get("description") or ""]
        for it in p["items"]:
            k = it["kind"]
            if k in ("text", "button", "marquee", "arttext") and it.get("text"):
                words.append(it["text"])
            elif k == "table":
                words += [c for row in it.get("cells", []) for c in row]
        text = " ".join(" ".join(words).split())
        text = replace_tokens(text, token_values(doc, p))
        text = " ".join(re.sub(r"%\w+%", " ", text).split())
        out.append(dict(t=(p.get("title") or p["name"]), u=page_path(files, p["id"], clean) or "./",
                        x=text[:6000]))
    return out


def page_source(doc, page_id, clean=False):
    """The HTML of one page as a string (for the source viewer)."""
    files = page_files(doc, clean, php=False)
    page = next(p for p in doc.pages if p["id"] == page_id)
    return page_html(doc, page, files, asset_names(doc), clean)


RESPONSIVE_JS = """<script>
(function(){
var SW=__W__, SH=__H__;
var stage=document.querySelector('.stage'), wrap=document.querySelector('.wrap');
var host=stage.querySelector('form')||stage;
var ASPECT={image:1,video:1,map:1,gallery:1,rect:1,ellipse:1,line:1,table:1,slider:1};
var AUTOH={text:1,html:1};
var recs=[].slice.call(stage.querySelectorAll('.o')).map(function(el,i){
  var s=el.style;
  return {el:el,i:i,css:el.getAttribute('style')||'',x:parseFloat(s.left)||0,y:parseFloat(s.top)||0,
          w:parseFloat(s.width)||0,h:parseFloat(s.height)||0,k:el.getAttribute('data-k')||''};
});
var flow=null;
function restore(){
  if(flow){recs.forEach(function(r){r.el.setAttribute('style',r.css);host.appendChild(r.el);});
    flow.parentNode.removeChild(flow);flow=null;}
  stage.style.width=SW+'px';stage.style.height=SH+'px';
}
function desktop(W){
  restore();
  var k=Math.min(1,W/SW);
  stage.style.transformOrigin='0 0';
  stage.style.transform=k<1?'scale('+k+')':'';
  stage.style.margin=k<1?'0':'0 auto';
  wrap.style.height=(SH*k)+'px';
}
function inside(r,b){
  return r.x>=b.x-2&&r.y>=b.y-2&&r.x+r.w<=b.x+b.w+2&&r.y+r.h<=b.y+b.h+2&&b.w*b.h>r.w*r.h;
}
function order(blocks){
  // narrow blocks that share a column stay together; columns then read left to right
  var narrow=blocks.filter(function(b){return b.w<SW*0.7;});
  var wide=blocks.filter(function(b){return b.w>=SW*0.7;});
  var par=narrow.map(function(_,i){return i;});
  function find(i){while(par[i]!==i){par[i]=par[par[i]];i=par[i];}return i;}
  for(var i=0;i<narrow.length;i++)for(var j=i+1;j<narrow.length;j++){
    var a=narrow[i],b=narrow[j];
    var ov=Math.min(a.x+a.w,b.x+b.w)-Math.max(a.x,b.x);
    if(ov>0.5*Math.min(a.w,b.w)) par[find(i)]=find(j);
  }
  var groups={};
  narrow.forEach(function(b,i){var g=find(i);(groups[g]=groups[g]||[]).push(b);});
  var units=wide.map(function(b){return {y0:b.y,x0:b.x,list:[b]};});
  Object.keys(groups).forEach(function(g){
    var l=groups[g].sort(function(a,b){return a.y-b.y;});
    units.push({y0:l[0].y,x0:Math.min.apply(null,l.map(function(b){return b.x;})),list:l});
  });
  units.sort(function(a,b){return a.y0-b.y0||a.x0-b.x0;});
  var out=[];units.forEach(function(u){out=out.concat(u.list);});
  return out;
}
function leaf(el,r,w,into){
  var k=r.k;
  el.setAttribute('style',r.css);
  var st=el.style;
  st.position='relative';st.left='auto';st.top='auto';st.margin='0 auto 12px';
  st.width=Math.min(r.w,w)+'px';
  if(k==='navbar'){st.width=w+'px';st.height='auto';st.minHeight=r.h+'px';
    var ul=el.querySelector('ul'); if(ul&&!/column/.test(ul.style.flexDirection||'')){ul.style.flexWrap='wrap';}}
  else if(AUTOH[k]){st.height='auto';st.minHeight=Math.min(r.h,60)+'px';}
  else if(ASPECT[k]&&r.w>0){st.height=(r.h*Math.min(r.w,w)/r.w)+'px';}
  into.appendChild(el);
}
function mobile(W){
  restore();
  var pad=12, avail=W-2*pad;
  stage.style.transform='';stage.style.margin='0';
  stage.style.width='100%';stage.style.height='auto';wrap.style.height='auto';
  flow=document.createElement('div');
  flow.style.cssText='position:relative;padding:'+pad+'px;width:100%';
  host.appendChild(flow);
  var blocks=[];
  recs.slice().sort(function(a,b){return b.w*b.h-a.w*a.h;}).forEach(function(r){
    for(var i=0;i<blocks.length;i++){ if(inside(r,blocks[i])){blocks[i].kids.push(r);return;} }
    blocks.push({x:r.x,y:r.y,w:r.w,h:r.h,main:r,kids:[]});
  });
  blocks=order(blocks);
  blocks.forEach(function(b){
    var m=b.main;
    var k2=Math.min(1,avail/b.w);
    if(!b.kids.length){
      leaf(m.el,m,avail,flow);
    } else if(m.k==='rect'&&k2<0.9){
      // a wide panel with things on it: keep the panel, let its contents reflow inside
      var pe=m.el;
      pe.setAttribute('style',m.css);
      var ps=pe.style;
      ps.position='relative';ps.left='auto';ps.top='auto';ps.margin='0 auto '+pad+'px';
      ps.width=avail+'px';ps.height='auto';ps.padding=pad+'px '+pad+'px 0';
      b.kids.sort(function(a,c){return a.y-c.y||a.x-c.x;}).forEach(function(r){
        leaf(r.el,r,avail-2*pad,pe);
      });
      flow.appendChild(pe);
    } else {
      var outer=document.createElement('div');
      outer.style.cssText='position:relative;margin:0 auto '+pad+'px;width:'+(b.w*k2)+'px;height:'+(b.h*k2)+'px';
      var inner=document.createElement('div');
      inner.style.cssText='position:absolute;left:0;top:0;width:'+b.w+'px;height:'+b.h+'px;'
        +'transform:scale('+k2+');transform-origin:0 0';
      [m].concat(b.kids).sort(function(a,c){return a.i-c.i;}).forEach(function(r){
        r.el.setAttribute('style',r.css);
        r.el.style.left=(r.x-b.x)+'px';r.el.style.top=(r.y-b.y)+'px';
        inner.appendChild(r.el);
      });
      outer.appendChild(inner);flow.appendChild(outer);
    }
  });
}
function layout(){
  var W=document.documentElement.clientWidth||window.innerWidth;
  if(W<700) mobile(W); else desktop(W);
}
var t=null;
window.addEventListener('resize',function(){clearTimeout(t);t=setTimeout(layout,60);});
window.addEventListener('orientationchange',function(){setTimeout(layout,200);});
layout();
// touch screens have no hover: first tap opens a pop-up or drop-down menu
document.addEventListener('click',function(e){
  if(!window.matchMedia||!matchMedia('(hover: none)').matches)return;
  var ro=e.target.closest('.ro');
  if(ro){
    if(!ro.classList.contains('open')){ro.classList.add('open');if(ro.tagName==='A')e.preventDefault();}
    else if(ro.tagName!=='A'){ro.classList.remove('open');}
  }
  var h=e.target.closest('.pm, nav li');
  [].slice.call(document.querySelectorAll('.open')).forEach(function(x){if(x!==h&&!x.contains(e.target))x.classList.remove('open');});
  if(h&&h.querySelector(':scope > .pop, :scope > .sub')&&!h.classList.contains('open')){
    e.preventDefault();h.classList.add('open');}
});
})();
</script>
"""

GALLERY_JS = """<script>
(function(){
function items(){return [].slice.call(document.querySelectorAll('.gal .lb, [data-lb]'));}
function big(el){return el.getAttribute('data-lb')||el.getAttribute('href');}
function cap(el){var c=el.getAttribute('data-cap');if(c)return c;var i=el.querySelector('img');return i?i.alt:'';}
var list=[],cur=0,ov=null;
function show(i){
  cur=(i+list.length)%list.length;
  ov.querySelector('img').src=big(list[cur]);
  ov.querySelector('.cap').textContent=cap(list[cur]);
  var many=list.length>1;
  ov.querySelector('.pv').style.display=many?'block':'none';
  ov.querySelector('.nx').style.display=many?'block':'none';
}
function close(){if(ov){ov.remove();ov=null;document.removeEventListener('keydown',key);}}
function key(e){if(e.key==='Escape')close();else if(e.key==='ArrowLeft')show(cur-1);else if(e.key==='ArrowRight')show(cur+1);}
function open(el){
  list=items();cur=list.indexOf(el);if(cur<0)cur=0;
  ov=document.createElement('div');ov.setAttribute('role','dialog');ov.setAttribute('aria-modal','true');
  ov.style.cssText='position:fixed;inset:0;background:rgba(0,0,0,.88);display:flex;flex-direction:column;'+
    'align-items:center;justify-content:center;z-index:9999;cursor:zoom-out;padding:16px;box-sizing:border-box';
  var b='position:absolute;top:50%;transform:translateY(-50%);background:rgba(255,255,255,.18);color:#fff;'+
    'border:0;font-size:34px;width:48px;height:64px;cursor:pointer;border-radius:6px';
  ov.innerHTML='<img alt="" style="max-width:100%;max-height:calc(100% - 44px);object-fit:contain">'+
    '<div class="cap" style="color:#fff;font:16px sans-serif;margin-top:10px;text-align:center"></div>'+
    '<button class="pv" aria-label="Previous picture" style="'+b+';left:12px">&#8249;</button>'+
    '<button class="nx" aria-label="Next picture" style="'+b+';right:12px">&#8250;</button>'+
    '<button class="cl" aria-label="Close" style="position:absolute;top:10px;right:14px;background:none;'+
    'border:0;color:#fff;font-size:36px;cursor:pointer">&times;</button>';
  ov.addEventListener('click',function(e){
    if(e.target.classList.contains('pv')){e.stopPropagation();show(cur-1);}
    else if(e.target.classList.contains('nx')){e.stopPropagation();show(cur+1);}
    else close();
  });
  var sx=null;
  ov.addEventListener('touchstart',function(e){sx=e.touches[0].clientX;},{passive:true});
  ov.addEventListener('touchend',function(e){if(sx===null)return;var dx=e.changedTouches[0].clientX-sx;sx=null;
    if(Math.abs(dx)>50){show(cur+(dx<0?1:-1));}},{passive:true});
  document.body.appendChild(ov);document.addEventListener('keydown',key);show(cur);
}
document.addEventListener('click',function(e){
  var el=e.target.closest('.gal .lb, [data-lb]');
  if(el){e.preventDefault();open(el);}
});
})();
</script>
"""

SOCIAL_JS = """<script>
document.querySelectorAll('.social a').forEach(function(a){
if(a.dataset.base)a.href=a.dataset.base+encodeURIComponent(location.href);});
</script>
"""

CSS = """*{margin:0;padding:0;box-sizing:border-box}
html,body{min-height:100%}
.wrap{position:relative;overflow-x:hidden}
.stage{position:relative}
.o{position:absolute;display:block;color:inherit}
a.o{text-decoration:none}
.pop{display:none;position:absolute;left:0;top:100%;background:#fff;z-index:30;
min-width:100%;box-shadow:0 6px 14px rgba(0,0,0,.25);font:14px sans-serif}
.pm:hover .pop,.pm.open>.pop{display:block}
.ro{position:absolute}.ro .ro-b{opacity:0;transition:opacity .3s ease}
.ro:hover .ro-b,.ro.open .ro-b{opacity:1}
.ro-z{overflow:hidden}.ro-z img{transition:transform .35s ease}.ro-z:hover img,.ro-z.open img{transform:scale(1.08)}
.ro-br img{transition:filter .3s}.ro-br:hover img{filter:brightness(1.15) saturate(1.15)}
.sw-slider{background:#222;font-family:sans-serif}
.sw-slide{position:absolute;left:0;top:0;width:100%;height:100%;overflow:hidden}
.sw-prev,.sw-next{position:absolute;top:50%;transform:translateY(-50%);width:44px;height:56px;
border:0;border-radius:6px;background:rgba(0,0,0,.35);color:#fff;font-size:32px;cursor:pointer;z-index:3}
.sw-prev{left:10px}.sw-next{right:10px}
.sw-dots{position:absolute;left:0;right:0;bottom:12px;text-align:center;z-index:3}
.sw-dots button{width:12px;height:12px;border-radius:50%;border:0;margin:0 5px;padding:0;
background:#fff;cursor:pointer}
nav li.open>.sub{display:flex}
html,body{overflow-x:hidden;-webkit-text-size-adjust:100%}
.pop a{display:block;padding:8px 14px;color:#222;text-decoration:none;white-space:nowrap}
.pop a:hover{background:#eef3fb}
.mq{display:inline-block;padding-left:100%;white-space:nowrap;animation:mq linear infinite}
@keyframes mq{from{transform:translateX(0)}to{transform:translateX(-100%)}}
"""


def rfc822(date_text):
    import datetime
    import email.utils
    try:
        d = datetime.datetime.strptime(date_text, "%Y-%m-%d")
    except (ValueError, TypeError):
        d = datetime.datetime.utcnow()
    return email.utils.format_datetime(d.replace(tzinfo=datetime.timezone.utc))


def feed_xml(doc, files, anames, clean):
    """RSS 2.0 feed; with audio attached it is a podcast feed (iTunes tags)."""
    from xml.sax.saxutils import escape, quoteattr
    f = doc.feed
    seo = doc.seo
    base = seo.get("site_url", "").strip()
    link = f.get("link") or base or ""
    def esc(x):
        return escape(x or "")
    out = ['<?xml version="1.0" encoding="UTF-8"?>',
           '<rss version="2.0" xmlns:itunes="http://www.itunes.com/dtds/podcast-1.0.dtd" '
           'xmlns:atom="http://www.w3.org/2005/Atom">', "<channel>",
           "<title>%s</title>" % esc(f.get("title") or doc.site_title),
           "<link>%s</link>" % esc(link),
           "<description>%s</description>" % esc(f.get("description") or seo.get("description")
                                                   or doc.site_title),
           "<language>%s</language>" % esc(seo.get("lang") or "en")]
    if base:
        out.append('<atom:link href=%s rel="self" type="application/rss+xml"/>'
                   % quoteattr(abs_url(base, "feed.xml")))
    if f.get("author"):
        out.append("<itunes:author>%s</itunes:author>" % esc(f["author"]))
    if f.get("category"):
        out.append('<itunes:category text=%s/>' % quoteattr(f["category"]))
    out.append("<itunes:explicit>%s</itunes:explicit>" % ("true" if f.get("explicit") else "false"))
    if f.get("email"):
        out.append("<itunes:owner><itunes:email>%s</itunes:email></itunes:owner>" % esc(f["email"]))
    if f.get("image") in anames:
        out.append("<itunes:image href=%s/>" % quoteattr(abs_url(base, "images/" + anames[f["image"]])))
    for it in f.get("items", []):
        out.append("<item>")
        out.append("<title>%s</title>" % esc(it.get("title")))
        tgt = it.get("link", "")
        if tgt.startswith("page:"):
            tgt = abs_url(base, page_path(files, tgt[5:], clean)) if base else page_path(files, tgt[5:], clean)
        if tgt:
            out.append("<link>%s</link>" % esc(tgt))
        out.append("<description>%s</description>" % esc(it.get("description")))
        out.append("<pubDate>%s</pubDate>" % rfc822(it.get("date")))
        out.append('<guid isPermaLink="false">%s</guid>' % esc(it.get("id") or it.get("title")))
        au = it.get("audio_url", "")
        if it.get("asset") in anames:
            au = abs_url(base, "images/" + anames[it["asset"]])
        if au:
            ext = au.rsplit(".", 1)[-1].lower()
            mime = {"mp3": "audio/mpeg", "m4a": "audio/mp4", "ogg": "audio/ogg",
                    "wav": "audio/wav"}.get(ext, "audio/mpeg")
            size = len(doc.asset_bytes(it["asset"])) if it.get("asset") in anames else 0
            out.append('<enclosure url=%s length="%d" type="%s"/>' % (quoteattr(au), size, mime))
        out.append("</item>")
    out += ["</channel>", "</rss>", ""]
    return "\n".join(out)


def sitemap_xml(doc, files, clean):
    base = (doc.seo.get("site_url") or "").strip()
    if not base:
        return ""
    rows = []
    for p in doc.pages:
        if p.get("type", "page") not in ("page", "html") or p.get("protect") or \
                (p.get("robots") and "noindex" in p["robots"]):
            continue
        rows.append("<url><loc>%s</loc></url>" % html.escape(abs_url(base, page_path(files, p["id"], clean))))
    return ('<?xml version="1.0" encoding="UTF-8"?>\n'
            '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n%s\n</urlset>\n'
            % "\n".join(rows))


def optimised_bytes(doc, aid, max_w):
    """Shrink big pictures to twice their on-page width (sharp on retina screens)."""
    raw = doc.asset_bytes(aid)
    name = doc.assets[aid]["name"].lower()
    if not max_w or not name.endswith((".png", ".jpg", ".jpeg", ".bmp", ".webp")):
        return raw
    from PyQt5.QtCore import QBuffer, QByteArray, Qt
    from PyQt5.QtGui import QImage
    img = QImage()
    if not img.loadFromData(raw) or img.width() <= 2 * max_w:
        return raw
    img = img.scaledToWidth(2 * max_w, Qt.SmoothTransformation)
    buf = QBuffer(QByteArray())
    buf.open(QBuffer.WriteOnly)
    fmt = "PNG" if name.endswith(".png") else "JPG"
    img.save(buf, fmt, 88)
    data = bytes(buf.data())
    return data if data and len(data) < len(raw) else raw


def display_widths(doc):
    widths = {}
    for lst in [p["items"] for p in doc.pages] + doc.all_master_lists():
        for it in lst:
            if it["kind"] == "image" and it.get("asset"):
                widths[it["asset"]] = max(widths.get(it["asset"], 0), it["w"])
                if it.get("hover_asset"):
                    widths[it["hover_asset"]] = max(widths.get(it["hover_asset"], 0), it["w"])
            if it["kind"] == "slider":
                for pn in it.get("panels") or []:
                    if pn.get("asset"):
                        widths[pn["asset"]] = max(widths.get(pn["asset"], 0), it["w"])
            if it["kind"] == "gallery":
                cell = it["w"] / max(it.get("cols", 3), 1)
                for a in it.get("assets") or []:
                    widths[a] = max(widths.get(a, 0), cell)
    return widths


def _has_kind(doc, kind):
    return any(i["kind"] == kind for lst in [p["items"] for p in doc.pages] + doc.all_master_lists()
               for i in lst)


def export_site(doc, outdir, clean=None, optimise=True, preview=False):
    """Write the site to outdir; returns the list of files written. A preview
    leaves members-only pages as plain .html so they can be seen without PHP."""
    if clean is None:
        clean = getattr(doc, "clean_urls", True)
    os.makedirs(os.path.join(outdir, "images"), exist_ok=True)
    files = page_files(doc, clean, php=not preview)
    anames = asset_names(doc)
    _extras.CONTEXT["rss_ids"] = {}
    written = []
    _derived.clear()
    for page in doc.pages:
        if page.get("type", "page") == "link":
            continue
        path = os.path.join(outdir, files[page["id"]])
        os.makedirs(os.path.dirname(path), exist_ok=True)
        text = page_html(doc, page, files, anames, clean)
        if page.get("protect") and not preview:
            depth = files[page["id"]].count("/")
            allowed = ", ".join(phpgen._q(n) for n in (page.get("allow") or []))
            guard = ("<?php require __DIR__ . '/%ssw-auth.php'; "
                     "sw_require('%s', array(%s), %s); ?>\n"
                     % ("../" * depth, "../" * depth, allowed, phpgen._q(doc.site_title)))
            text = guard + text.replace("<?", "<?php echo '<?'; ?>")
        with open(path, "w", encoding="utf-8") as f:
            f.write(text)
        written.append(path)
    rss_ids = _extras.CONTEXT.get("rss_ids") or {}
    if rss_ids:
        rp = os.path.join(outdir, "rss-reader.php")
        with open(rp, "w", encoding="utf-8") as f:
            f.write(_extras.rss_php(rss_ids))
        written.append(rp)
    if any(i["kind"] == "field" for lst in [p["items"] for p in doc.pages] + doc.all_master_lists()
           for i in lst) and getattr(doc, "form_mode", "php") == "php":
        sp = os.path.join(outdir, "send.php")
        with open(sp, "w") as f:
            f.write(send_php(doc.form_email, doc))
        written.append(sp)
    if any(p.get("protect") for p in doc.pages) or _has_kind(doc, "login"):
        ap = os.path.join(outdir, "sw-auth.php")
        with open(ap, "w") as f:
            f.write(phpgen.auth_php(doc.members, doc.site_title))
        written.append(ap)
    if _has_kind(doc, "subscribe"):
        key = doc.list_key or "unset"
        token = phpgen.list_token(key)
        for name, text in (("subscribe.php", phpgen.subscribe_php(token, doc.form_email)),
                           ("subscribers.php", phpgen.subscribers_php(token, key))):
            p2 = os.path.join(outdir, name)
            with open(p2, "w") as f:
                f.write(text)
            written.append(p2)
    from . import webapps
    for name, text in webapps.files(doc).items():          # poll.php, blog-api.php, shop files...
        wp = os.path.join(outdir, name)
        os.makedirs(os.path.dirname(wp), exist_ok=True)
        with open(wp, "w", encoding="utf-8") as f:
            f.write(text)
        written.append(wp)
    css = os.path.join(outdir, "style.css")
    with open(css, "w") as f:
        f.write(CSS)
    written.append(css)
    widths = display_widths(doc) if optimise else {}
    for aid, name in anames.items():
        p = os.path.join(outdir, "images", name)
        with open(p, "wb") as f:
            f.write(optimised_bytes(doc, aid, widths.get(aid, 0)) if optimise
                    else doc.asset_bytes(aid))
        written.append(p)
    for fname, d in _derived.items():
        img = imagefx.derive(doc, d, token_values(doc), imagefx.export_width(d))
        if img is not None:
            p = os.path.join(outdir, "images", fname)
            with open(p, "wb") as f:
                f.write(imagefx.png_bytes(img))
            written.append(p)
    sm = sitemap_xml(doc, files, clean)
    if sm:
        with open(os.path.join(outdir, "sitemap.xml"), "w", encoding="utf-8") as f:
            f.write(sm)
        written.append(os.path.join(outdir, "sitemap.xml"))
    with open(os.path.join(outdir, "robots.txt"), "w") as f:
        f.write("User-agent: *\nAllow: /\n" +
                ("Sitemap: %s\n" % abs_url(doc.seo["site_url"], "sitemap.xml") if sm else ""))
    written.append(os.path.join(outdir, "robots.txt"))
    if doc.feed.get("enabled"):
        with open(os.path.join(outdir, "feed.xml"), "w", encoding="utf-8") as f:
            f.write(feed_xml(doc, files, anames, clean))
        written.append(os.path.join(outdir, "feed.xml"))
    return written
