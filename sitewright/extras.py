"""Phase 3 objects: how they are drawn on the canvas and written as HTML."""
import html
import json
import re
from urllib.parse import quote

from PyQt5.QtCore import QPointF, QRectF, Qt
from PyQt5.QtGui import QColor, QFont, QPainterPath, QPen, QPolygonF

from . import webapps  # noqa: E402

EXTRA_KINDS = {"table", "gallery", "video", "map", "audio", "field", "social",
               "html", "marquee", "frame", "search", "searchresults", "subscribe",
               "login", "slider", "arttext", "hotspot", "popup", "rssreader", "repeater", "shape"}

NETS = {"facebook": ("f", "#3b5998", "Facebook"), "x": ("X", "#111111", "X"),
        "pinterest": ("P", "#c8232c", "Pinterest"), "email": ("@", "#5b6b7c", "Email"),
        "instagram": ("I", "#c13584", "Instagram"), "youtube": ("Y", "#d62828", "YouTube"),
        "rss": ("R", "#f26522", "RSS feed"),
        "whatsapp": ("W", "#25a244", "WhatsApp")}


PROFILE_DEFAULT = {"instagram": "https://www.instagram.com/",
                   "youtube": "https://www.youtube.com/", "rss": "feed.xml"}


def profile_url(d, net):
    """Where a profile-style button (Instagram, YouTube) goes; others use JS."""
    if net in PROFILE_DEFAULT:
        return d.get(net + "_url") or PROFILE_DEFAULT[net]
    return "#"


def share_url(net):
    """Share links are filled in by a tiny script with the page's own address."""
    return {"facebook": "https://www.facebook.com/sharer/sharer.php?u=",
            "x": "https://twitter.com/intent/tweet?url=",
            "pinterest": "https://pinterest.com/pin/create/button/?url=",
            "whatsapp": "https://wa.me/?text=",
            "instagram": "", "youtube": "", "rss": "",
            "email": "mailto:?subject=Check%20this%20out&body="}.get(net, "")


# ---------------------------------------------------------------- painting
def font_for(d, size=None):
    f = QFont(d.get("font", "Sans Serif"))
    f.setPixelSize(int(size or d.get("size", 15)))
    f.setBold(bool(d.get("bold")))
    f.setItalic(bool(d.get("italic")))
    return f


def paint_extra(p, r, d, win):
    kind = d["kind"]
    if kind in webapps.REGISTRY:
        return webapps.paint(p, r, d, win)
    {"table": paint_table, "gallery": paint_gallery, "video": paint_video,
     "map": paint_map, "audio": paint_audio, "field": paint_field,
     "social": paint_social, "html": paint_html, "frame": paint_frame,
     "search": paint_search, "searchresults": paint_results, "slider": paint_slider,
     "subscribe": paint_search, "login": paint_login,
     "marquee": paint_marquee, "arttext": paint_arttext,
     "hotspot": paint_hotspot, "popup": paint_popup,
     "rssreader": paint_rssreader, "repeater": paint_repeater, "shape": paint_shape}[kind](p, r, d, win)


def shape_nodes_of(d):
    from . import shapes
    if not d.get("nodes"):
        d["nodes"] = shapes.preset_nodes(d.get("preset", "star"))
    return d["nodes"]


def paint_shape(p, r, d, win):
    from . import shapes
    path = shapes.qpath(shape_nodes_of(d), d.get("closed", True), d["w"], d["h"])
    if d.get("shadow"):
        p.setPen(Qt.NoPen)
        p.setBrush(QColor(0, 0, 0, 70))
        p.drawPath(path.translated(0, 3))
    p.setBrush(QColor(d["fill"]) if d.get("fill") else Qt.NoBrush)
    sw = d.get("sw", 0) if d.get("stroke") else 0
    pen = QPen(QColor(d["stroke"]), sw) if sw else Qt.NoPen
    if sw:
        pen.setJoinStyle(Qt.RoundJoin)
        pen.setCapStyle(Qt.RoundCap)
        if d.get("sstyle") in ("dashed", "dotted"):
            pen.setStyle(Qt.DashLine if d["sstyle"] == "dashed" else Qt.DotLine)
    p.setPen(pen)
    p.drawPath(path)


def paint_repeater(p, r, d, win):
    from . import databasemerge as dm
    db = dm.find(win.doc, d.get("db"))
    p.setBrush(QColor(43, 125, 233, 18))
    p.setPen(QPen(QColor("#2b7de9"), 1, Qt.DashLine))
    p.drawRect(r.adjusted(.5, .5, -.5, -.5))
    cols = max(int(d.get("cols", 1)), 1)
    p.setPen(QColor("#2b7de9"))
    f = QFont()
    f.setPixelSize(11)
    f.setBold(True)
    p.setFont(f)
    note = "Repeating area: %s" % (db["name"] if db else "no database chosen")
    if db:
        note += " (%d record%s, %d across)" % (len(db["rows"]), "" if len(db["rows"]) == 1 else "s", cols)
    p.drawText(r.adjusted(6, 3, -6, -3), int(Qt.AlignLeft | Qt.AlignTop), note)
    p.setPen(QColor("#6b7686"))
    f.setBold(False)
    p.setFont(f)
    p.drawText(r.adjusted(6, 3, -6, -3), int(Qt.AlignLeft | Qt.AlignBottom),
               "This is the first record. Put text and pictures inside it.")


def paint_table(p, r, d, win):
    from . import tablecore as tc
    rows, cols = max(d["rows"], 1), max(d["cols"], 1)
    xs = tc.edges(d, r.width(), cols, "colw")
    ys = tc.edges(d, r.height(), rows, "rowh")
    spans, covered = tc.layout(d)
    pen = QPen(QColor(d["stroke"] or "#c8ced6"), max(d.get("sw", 1), 0) or 0)
    base = font_for(d)
    p.setFont(base)
    for i in range(rows):
        for c in range(cols):
            if (i, c) in covered:
                continue
            rs, cs = spans.get((i, c), (1, 1))
            cell = QRectF(r.left() + xs[c], r.top() + ys[i], xs[c + cs] - xs[c], ys[i + rs] - ys[i])
            head = d.get("header") and i == 0
            f = tc.cell_fmt(d, i, c)
            if f.get("fill"):
                fill = f["fill"]
            elif head:
                fill = d["hfill"]
            elif d.get("band") and (i - (1 if d.get("header") else 0)) % 2 == 1:
                fill = d["band"]
            else:
                fill = d["fill"] or "#ffffff"
            p.setBrush(QColor(fill))
            p.setPen(pen if d.get("sw") else Qt.NoPen)
            p.drawRect(cell)
            p.setPen(QColor(f.get("color") or (d["hcolor"] if head else d["color"])))
            fnt = QFont(base)
            if "bold" in f:
                fnt.setBold(bool(f["bold"]))
            if "italic" in f:
                fnt.setItalic(bool(f["italic"]))
            p.setFont(fnt)
            al = {"left": Qt.AlignLeft, "center": Qt.AlignHCenter,
                  "right": Qt.AlignRight}.get(f.get("align"), Qt.AlignLeft)
            va = {"top": Qt.AlignTop, "bottom": Qt.AlignBottom}.get(f.get("valign"), Qt.AlignVCenter)
            p.save()
            p.setClipRect(cell)
            p.drawText(cell.adjusted(8, 3, -8, -3), int(va | al), tc.text_at(d, i, c))
            p.restore()
    # the chosen cells, shown only while this table is selected for editing
    if getattr(win, "table_marks", None) is d:
        r1, c1, r2, c2 = tc.clamp_sel(d)
        box = QRectF(r.left() + xs[c1], r.top() + ys[r1], xs[c2 + 1] - xs[c1], ys[r2 + 1] - ys[r1])
        p.setBrush(QColor(43, 125, 233, 45))
        p.setPen(QPen(QColor("#2b7de9"), 2, Qt.DashLine))
        p.drawRect(box)


def paint_gallery(p, r, d, win):
    ids = d.get("assets") or []
    cols = max(d.get("cols", 3), 1)
    gap = d.get("gap", 10)
    n = max(len(ids), cols)
    rows = (n + cols - 1) // cols
    cw = (r.width() - gap * (cols - 1)) / cols
    ch = (r.height() - gap * (rows - 1)) / rows
    p.fillRect(r, QColor("#f2f4f7"))
    for i in range(n):
        cell = QRectF(r.left() + (i % cols) * (cw + gap),
                      r.top() + (i // cols) * (ch + gap), cw, ch)
        pm = win.pixmap(ids[i]) if i < len(ids) else None
        if pm is None or pm.isNull():
            p.fillRect(cell, QColor("#dfe3e8"))
            p.setPen(QPen(QColor("#9aa3ad"), 1))
            p.drawRect(cell)
            continue
        p.save()
        p.setClipRect(cell)
        k = max(cw / pm.width(), ch / pm.height()) if d.get("fit") != "contain" \
            else min(cw / pm.width(), ch / pm.height())
        w, h = pm.width() * k, pm.height() * k
        p.drawPixmap(QRectF(cell.center().x() - w / 2, cell.center().y() - h / 2, w, h),
                     pm, QRectF(pm.rect()))
        p.restore()


def paint_video(p, r, d, win):
    p.fillRect(r, QColor("#1b1f26"))
    c = r.center()
    s = min(r.width(), r.height()) / 8
    p.setBrush(QColor(255, 255, 255, 230))
    p.setPen(Qt.NoPen)
    p.drawPolygon(QPolygonF([QPointF(c.x() - s * .6, c.y() - s), QPointF(c.x() - s * .6, c.y() + s),
                             QPointF(c.x() + s, c.y())]))
    p.setPen(QColor("#cfd6df"))
    p.setFont(font_for({}, 12))
    p.drawText(r.adjusted(8, 0, -8, -8), int(Qt.AlignBottom | Qt.AlignHCenter),
               d.get("url") or "Video: set an address in Properties")


def paint_slider(p, r, d, win):
    panels = d.get("panels") or []
    cur = panels[max(0, min(len(panels) - 1, int(d.get("start", 1)) - 1))] if panels else {}
    bg = QColor(cur.get("bg") or "#1f3a5f")
    p.fillRect(r, bg)
    pm = win.pixmap(cur.get("asset")) if cur.get("asset") else None
    if pm is not None and not pm.isNull():
        k = max(r.width() / pm.width(), r.height() / pm.height())
        w, h = pm.width() * k, pm.height() * k
        p.drawPixmap(QRectF(r.center().x() - w / 2, r.center().y() - h / 2, w, h), pm,
                     QRectF(pm.rect()))
    if cur.get("overlay_op"):
        c = QColor(cur.get("overlay") or "#000000")
        c.setAlpha(int(255 * cur["overlay_op"] / 100))
        p.fillRect(r, c)
    col = QColor(cur.get("color") or "#ffffff")
    al = {"left": Qt.AlignLeft, "right": Qt.AlignRight}.get(cur.get("align"), Qt.AlignHCenter)
    f = font_for({"font": "Sans Serif", "bold": True}, max(18, int(r.height() * 0.11)))
    p.setFont(f)
    p.setPen(col)
    inner = r.adjusted(r.width() * .12, r.height() * .22, -r.width() * .12, -r.height() * .22)
    p.drawText(QRectF(inner.left(), inner.top(), inner.width(), inner.height() * .35),
               int(al | Qt.AlignVCenter), cur.get("heading", ""))
    p.setFont(font_for({"font": "Sans Serif"}, max(12, int(r.height() * 0.058))))
    p.drawText(QRectF(inner.left(), inner.top() + inner.height() * .38, inner.width(),
                      inner.height() * .35), int(al | Qt.AlignTop | Qt.TextWordWrap),
               cur.get("text", ""))
    if cur.get("btn"):
        bw = min(180, inner.width())
        bx = {"left": inner.left(), "right": inner.right() - bw}.get(
            cur.get("align"), inner.center().x() - bw / 2)
        b = QRectF(bx, r.bottom() - r.height() * .30 - 18, bw, 34)
        p.setPen(Qt.NoPen)
        p.setBrush(QColor(255, 255, 255, 235))
        p.drawRoundedRect(b, 5, 5)
        p.setPen(QColor("#1f3a5f"))
        p.drawText(b, int(Qt.AlignCenter), cur["btn"])
    if d.get("arrows", True):
        for x, dx in ((r.left() + 10, 1), (r.right() - 10, -1)):
            c = QPointF(x + dx * 14, r.center().y())
            p.setBrush(QColor(0, 0, 0, 90))
            p.setPen(Qt.NoPen)
            p.drawEllipse(c, 16, 16)
            p.setPen(QPen(QColor("white"), 2.4))
            p.drawLine(QPointF(c.x() + dx * 4, c.y() - 7), QPointF(c.x() - dx * 4, c.y()))
            p.drawLine(QPointF(c.x() - dx * 4, c.y()), QPointF(c.x() + dx * 4, c.y() + 7))
    if d.get("dots", True) and len(panels) > 1:
        n = len(panels)
        x0 = r.center().x() - (n - 1) * 9
        for i in range(n):
            p.setPen(Qt.NoPen)
            p.setBrush(QColor(255, 255, 255, 240 if i == max(0, int(d.get("start", 1)) - 1) else 120))
            p.drawEllipse(QPointF(x0 + i * 18, r.bottom() - 14), 5, 5)
    p.setPen(QPen(QColor(255, 255, 255, 160), 1))
    p.setFont(font_for({}, 11))
    p.drawText(r.adjusted(8, 6, -8, 0), int(Qt.AlignTop | Qt.AlignRight),
               "Slider  %d panel(s)" % len(panels))


def _box(p, r, d):
    p.setBrush(QColor(d.get("fill") or "#ffffff"))
    p.setPen(QPen(QColor(d["stroke"]), d.get("sw", 1)) if d.get("stroke") and d.get("sw")
             else Qt.NoPen)
    p.drawRoundedRect(r, d.get("radius", 4), d.get("radius", 4))


def _button(p, r, d, text):
    p.setPen(Qt.NoPen)
    p.setBrush(QColor(d.get("btnfill") or "#2b7de9"))
    p.drawRoundedRect(r, d.get("radius", 4), d.get("radius", 4))
    f = font_for(d)
    f.setBold(True)
    p.setFont(f)
    p.setPen(QColor(d.get("btncolor") or "#ffffff"))
    p.drawText(r, int(Qt.AlignCenter), text)


def paint_search(p, r, d, win):
    """Search box and mailing-list sign-up: a text box with a button beside it."""
    bw = min(max(90, len(d.get("btn", "")) * 11 + 30), r.width() * 0.4)
    box = QRectF(r.left(), r.top(), r.width() - bw - 6, r.height())
    _box(p, box, d)
    p.setFont(font_for(d))
    p.setPen(QColor("#8a929c"))
    p.drawText(box.adjusted(12, 0, -8, 0), int(Qt.AlignVCenter | Qt.AlignLeft), d.get("label", ""))
    _button(p, QRectF(r.right() - bw, r.top(), bw, r.height()), d, d.get("btn", ""))


def paint_results(p, r, d, win):
    p.setBrush(QColor("#fafbfc"))
    p.setPen(QPen(QColor("#c4cad3"), 1, Qt.DashLine))
    p.drawRect(r.adjusted(.5, .5, -.5, -.5))
    y = r.top() + 14
    for i in range(3):
        p.setPen(QColor("#1a5fb4"))
        f = font_for(d, 17)
        f.setUnderline(True)
        p.setFont(f)
        p.drawText(QPointF(r.left() + 14, y + 16), "Search result %d" % (i + 1))
        p.setPen(QColor("#667085"))
        p.setFont(font_for(d, 13))
        p.drawText(QPointF(r.left() + 14, y + 36), "A short piece of the page with your words in it...")
        y += 62
    p.setPen(QColor("#8a929c"))
    p.setFont(font_for(d, 12))
    p.drawText(r.adjusted(14, 0, -14, -8), int(Qt.AlignBottom | Qt.AlignLeft),
               "Results appear here when someone searches")


def paint_login(p, r, d, win):
    _box(p, r, d)
    p.setFont(font_for(d, int(d.get("size", 15)) + 2))
    p.setPen(QColor(d.get("color", "#222")))
    p.drawText(QRectF(r.left() + 14, r.top() + 8, r.width() - 28, 26),
               int(Qt.AlignVCenter | Qt.AlignLeft), d.get("title", ""))
    for i, hint in enumerate(("User name", "Password")):
        b = QRectF(r.left() + 14, r.top() + 44 + i * 42, r.width() - 28, 34)
        p.setBrush(QColor("#ffffff"))
        p.setPen(QPen(QColor("#9aa3ad"), 1))
        p.drawRoundedRect(b, 4, 4)
        p.setPen(QColor("#8a929c"))
        p.setFont(font_for(d))
        p.drawText(b.adjusted(10, 0, 0, 0), int(Qt.AlignVCenter | Qt.AlignLeft), hint)
    _button(p, QRectF(r.left() + 14, r.bottom() - 46, 110, 34), d, d.get("btn", "Log in"))


def paint_frame(p, r, d, win):
    p.fillRect(r, QColor("#eef2f7"))
    p.setPen(QPen(QColor("#9aa7b6"), 1, Qt.DashLine))
    p.drawRect(r.adjusted(.5, .5, -.5, -.5))
    p.setPen(QColor("#44566c"))
    p.setFont(font_for({}, 14))
    p.drawText(r.adjusted(10, 10, -10, -10), int(Qt.AlignCenter | Qt.TextWordWrap),
               "Web page frame\n" + (d.get("url") or "Set the page address in Properties"))


def paint_map(p, r, d, win):
    p.fillRect(r, QColor("#dcebd5"))
    p.setPen(QPen(QColor("#ffffff"), 6))
    p.drawLine(QPointF(r.left(), r.center().y()), QPointF(r.right(), r.top() + r.height() * .35))
    p.drawLine(QPointF(r.left() + r.width() * .4, r.top()), QPointF(r.left() + r.width() * .55, r.bottom()))
    c = r.center()
    p.setPen(Qt.NoPen)
    p.setBrush(QColor("#d9453d"))
    path = QPainterPath()
    path.addEllipse(QPointF(c.x(), c.y() - 14), 12, 12)
    p.drawPath(path)
    p.drawPolygon(QPolygonF([QPointF(c.x() - 9, c.y() - 7), QPointF(c.x() + 9, c.y() - 7),
                             QPointF(c.x(), c.y() + 12)]))
    p.setBrush(QColor("white"))
    p.drawEllipse(QPointF(c.x(), c.y() - 14), 4, 4)
    p.setPen(QColor("#33402f"))
    p.setFont(font_for({}, 13))
    p.drawText(r.adjusted(8, 0, -8, -8), int(Qt.AlignBottom | Qt.AlignHCenter),
               d.get("address") or "Map: set an address in Properties")


def paint_audio(p, r, d, win):
    p.setBrush(QColor("#eef1f5"))
    p.setPen(QPen(QColor("#c4cad3"), 1))
    p.drawRoundedRect(r.adjusted(.5, .5, -.5, -.5), r.height() / 2, r.height() / 2)
    cy = r.center().y()
    p.setBrush(QColor("#2b7de9"))
    p.setPen(Qt.NoPen)
    p.drawEllipse(QPointF(r.left() + 24, cy), 12, 12)
    p.setBrush(QColor("white"))
    p.drawPolygon(QPolygonF([QPointF(r.left() + 21, cy - 6), QPointF(r.left() + 21, cy + 6),
                             QPointF(r.left() + 29, cy)]))
    p.setPen(QPen(QColor("#b5bcc7"), 3))
    p.drawLine(QPointF(r.left() + 50, cy), QPointF(r.right() - 20, cy))


def paint_field(p, r, d, win):
    t = d.get("ftype", "text")
    p.setFont(font_for(d))
    ink = QColor(d.get("color", "#222222"))
    border = QPen(QColor(d["stroke"]), d.get("sw", 1)) if d.get("stroke") and d.get("sw") else Qt.NoPen
    if t in ("checkbox", "radio"):
        s = min(18, r.height() - 6)
        box = QRectF(r.left() + 2, r.center().y() - s / 2, s, s)
        p.setBrush(QColor("white"))
        p.setPen(QPen(QColor("#6b7480"), 1.5))
        p.drawEllipse(box) if t == "radio" else p.drawRoundedRect(box, 3, 3)
        p.setPen(ink)
        p.drawText(QRectF(box.right() + 8, r.top(), r.width() - s - 12, r.height()),
                   int(Qt.AlignVCenter | Qt.AlignLeft), d.get("label") or "Option")
        return
    if t == "recaptcha":
        p.setBrush(QColor("#f9f9f9"))
        p.setPen(QPen(QColor("#d3d3d3"), 1))
        p.drawRoundedRect(r.adjusted(.5, .5, -.5, -.5), 3, 3)
        p.setPen(QPen(QColor("#c1c1c1"), 2))
        p.setBrush(QColor("white"))
        p.drawRoundedRect(QRectF(r.left() + 14, r.center().y() - 12, 24, 24), 2, 2)
        p.setPen(QColor("#444444"))
        f = QFont()
        f.setPixelSize(14)
        p.setFont(f)
        p.drawText(QRectF(r.left() + 50, r.top(), r.width() - 110, r.height()),
                   int(Qt.AlignVCenter | Qt.AlignLeft), "I'm not a robot")
        p.setPen(QColor("#9aa0a6"))
        f.setPixelSize(9)
        p.setFont(f)
        p.drawText(QRectF(r.right() - 64, r.top() + 4, 60, r.height() - 8),
                   int(Qt.AlignHCenter | Qt.AlignBottom), "reCAPTCHA")
        return
    if t == "submit":
        p.setBrush(QColor(d.get("fill") or "#2b7de9"))
        p.setPen(Qt.NoPen)
        p.drawRoundedRect(r, d.get("radius", 4), d.get("radius", 4))
        p.setPen(QColor(d.get("color") or "#ffffff"))
        f = font_for(d)
        f.setBold(True)
        p.setFont(f)
        p.drawText(r, int(Qt.AlignCenter), d.get("label") or "Send")
        return
    p.setBrush(QColor(d.get("fill") or "#ffffff"))
    p.setPen(border)
    p.drawRoundedRect(r.adjusted(.5, .5, -.5, -.5), d.get("radius", 4), d.get("radius", 4))
    p.setPen(QColor("#8a929c"))
    hint = d.get("label") or {"email": "Email address", "date": "Choose a date",
                              "file": "Choose a file...", "select": "Choose...",
                              "textarea": "Your message"}.get(t, "Type here")
    al = Qt.AlignTop if t == "textarea" else Qt.AlignVCenter
    p.drawText(r.adjusted(10, 8 if t == "textarea" else 0, -26, 0),
               int(al | Qt.AlignLeft), hint)
    if t in ("select", "date"):
        c = QPointF(r.right() - 14, r.center().y())
        p.setBrush(QColor("#6b7480"))
        p.setPen(Qt.NoPen)
        p.drawPolygon(QPolygonF([QPointF(c.x() - 5, c.y() - 3), QPointF(c.x() + 5, c.y() - 3),
                                 QPointF(c.x(), c.y() + 4)]))


def paint_social(p, r, d, win):
    nets = d.get("nets") or []
    size = min(r.height(), 44)
    x = r.left()
    f = font_for({}, int(size * .45))
    f.setBold(True)
    p.setFont(f)
    for n in nets:
        ch, col, _ = NETS.get(n, ("?", "#555555", n))
        box = QRectF(x, r.top() + (r.height() - size) / 2, size, size)
        p.setBrush(QColor(col))
        p.setPen(Qt.NoPen)
        p.drawRoundedRect(box, size * .2, size * .2)
        p.setPen(QColor("white"))
        p.drawText(box, int(Qt.AlignCenter), ch)
        x += size + 8


def paint_html(p, r, d, win):
    p.setBrush(QColor("#f7f2e0"))
    p.setPen(QPen(QColor("#b9a24a"), 1, Qt.DashLine))
    p.drawRect(r.adjusted(.5, .5, -.5, -.5))
    p.setPen(QColor("#6b5d1e"))
    p.setFont(font_for({"font": "Monospace"}, 13))
    p.save()
    p.setClipRect(r)
    p.drawText(r.adjusted(8, 6, -8, -6), int(Qt.AlignTop | Qt.AlignLeft | Qt.TextWordWrap),
               "HTML\n" + d.get("code", ""))
    p.restore()


def paint_rssreader(p, r, d, win):
    p.fillRect(r, QColor("#ffffff"))
    p.setPen(QPen(QColor("#c8ced6"), 1))
    p.drawRect(r.adjusted(.5, .5, -.5, -.5))
    f = font_for(d)
    p.setFont(f)
    y = r.top() + 8
    host = re.sub(r"^https?://", "", d.get("url", "")).split("/")[0] or "your feed address"
    p.setPen(QColor("#6b7686"))
    p.drawText(QRectF(r.left() + 10, y, r.width() - 20, 20), int(Qt.AlignLeft | Qt.AlignVCenter),
               "RSS reader: headlines from " + host)
    y += 30
    line_h = f.pixelSize() * 1.5
    for n in range(max(1, min(int(d.get("count", 5)), 8))):
        if y + line_h > r.bottom() - 4:
            break
        p.setPen(QColor(d.get("color", "#222222")))
        ff = QFont(f)
        ff.setBold(True)
        p.setFont(ff)
        p.drawText(QRectF(r.left() + 10, y, r.width() - 20, line_h), int(Qt.AlignLeft | Qt.AlignVCenter),
                   "A headline from the feed (%d)" % (n + 1))
        y += line_h
        p.setFont(f)
        if d.get("show_date"):
            p.setPen(QColor("#8a929c"))
            p.drawText(QRectF(r.left() + 10, y, r.width() - 20, line_h * .8), int(Qt.AlignLeft | Qt.AlignVCenter),
                       "Oct %d, 2026" % (17 - n))
            y += line_h * .8
        y += 6


def rss_id(url):
    """A small number for each feed address, so the page only ever asks for a number."""
    ids = CONTEXT.setdefault("rss_ids", {})
    return ids.setdefault(url, len(ids) + 1)


RSS_PHP = """<?php
// Headlines for the RSS reader boxes. Only the feeds listed here can be fetched, nothing else.
$feeds = array(
%(feeds)s
);
$id = isset($_GET['f']) ? (int)$_GET['f'] : 0;
$n = isset($_GET['n']) ? max(1, min(20, (int)$_GET['n'])) : 5;
header('Content-Type: application/json; charset=utf-8');
if (!isset($feeds[$id])) { http_response_code(404); echo '[]'; exit; }
$cache = sys_get_temp_dir() . '/sw-rss-' . md5($feeds[$id]) . '.xml';
if (!is_file($cache) || time() - filemtime($cache) > 900) {
    $ctx = stream_context_create(array('http' => array('timeout' => 8, 'user_agent' => 'Mozilla/5.0 (feed reader)')));
    $xml = @file_get_contents($feeds[$id], false, $ctx);
    if ($xml !== false && strlen($xml) < 2000000) { @file_put_contents($cache, $xml); }
}
$xml = is_file($cache) ? file_get_contents($cache) : '';
libxml_use_internal_errors(true);
$doc = $xml !== '' ? simplexml_load_string($xml, 'SimpleXMLElement', LIBXML_NONET | LIBXML_NOCDATA) : false;
$out = array();
function sw_clean($s, $max) {
    $s = trim(preg_replace('/\\s+/', ' ', html_entity_decode(strip_tags((string)$s), ENT_QUOTES, 'UTF-8')));
    return function_exists('mb_substr') ? mb_substr($s, 0, $max) : substr($s, 0, $max);
}
function sw_date($s) { $t = strtotime((string)$s); return $t ? date('M j, Y', $t) : ''; }
if ($doc !== false) {
    if (isset($doc->channel->item)) {
        foreach ($doc->channel->item as $it) {
            $out[] = array('title' => sw_clean($it->title, 200), 'link' => trim((string)$it->link),
                           'desc' => sw_clean($it->description, 300), 'date' => sw_date($it->pubDate));
        }
    } elseif (isset($doc->entry)) {
        foreach ($doc->entry as $e) {
            $href = '';
            foreach ($e->link as $l) { if ((string)$l['rel'] === '' || (string)$l['rel'] === 'alternate') { $href = (string)$l['href']; break; } }
            $out[] = array('title' => sw_clean($e->title, 200), 'link' => $href,
                           'desc' => sw_clean(isset($e->summary) ? $e->summary : $e->content, 300),
                           'date' => sw_date(isset($e->updated) ? $e->updated : $e->published));
        }
    }
}
echo json_encode(array_slice($out, 0, $n));
"""


def rss_php(ids):
    rows = ",\n".join("    %d => %s" % (i, _php_str(u)) for u, i in sorted(ids.items(), key=lambda kv: kv[1]))
    return RSS_PHP % {"feeds": rows}


RSS_JS = r"""<script>
(function(){
var el=document.getElementById(__ID__);
function line(parent,cls,text){var d=document.createElement('div');d.className=cls;d.textContent=text;parent.appendChild(d);return d;}
fetch(__URL__).then(function(r){return r.json();}).then(function(items){
  el.textContent='';
  if(!items.length){el.textContent='No headlines found.';return;}
  items.forEach(function(it){
    var box=document.createElement('div');box.style.margin='0 0 12px 0';
    var a=document.createElement('a');a.textContent=it.title||it.link;
    if(/^https?:\/\//i.test(it.link||'')){a.href=it.link;a.target='_blank';a.rel='noopener';}
    a.style.fontWeight='bold';a.style.color='inherit';box.appendChild(a);
    if(__DATE__&&it.date){var s=line(box,'rss-date',it.date);s.style.opacity='.6';s.style.fontSize='.85em';}
    if(__DESC__&&it.desc){line(box,'rss-desc',it.desc);}
    el.appendChild(box);
  });
}).catch(function(){el.textContent='Headlines will appear here once the site is published.';});
})();
</script>"""


HOT_SHAPES = ["rect", "ellipse", "rounded", "triangle", "diamond"]
HOT_CLIP = {"triangle": "polygon(50% 0,100% 100%,0 100%)",
            "diamond": "polygon(50% 0,100% 50%,50% 100%,0 50%)"}


def hotspot_path(shape, r):
    path = QPainterPath()
    if shape == "ellipse":
        path.addEllipse(r)
    elif shape == "rounded":
        path.addRoundedRect(r, min(r.width(), r.height()) * 0.25, min(r.width(), r.height()) * 0.25)
    elif shape == "triangle":
        path.addPolygon(QPolygonF([QPointF(r.center().x(), r.top()), r.bottomRight(), r.bottomLeft()]))
        path.closeSubpath()
    elif shape == "diamond":
        path.addPolygon(QPolygonF([QPointF(r.center().x(), r.top()), QPointF(r.right(), r.center().y()),
                                   QPointF(r.center().x(), r.bottom()), QPointF(r.left(), r.center().y())]))
        path.closeSubpath()
    else:
        path.addRect(r)
    return path


def paint_hotspot(p, r, d, win):
    path = hotspot_path(d.get("shape", "rect"), r.adjusted(.5, .5, -.5, -.5))
    p.setBrush(QColor(43, 125, 233, 60))
    p.setPen(QPen(QColor("#2b7de9"), 1.5, Qt.DashLine))
    p.drawPath(path)
    p.setPen(QColor("#1f64c0"))
    f = QFont()
    f.setPixelSize(max(min(int(r.height() / 4), 14), 9))
    p.setFont(f)
    p.drawText(r, int(Qt.AlignCenter), "Hotspot" + (" \u2192" if d.get("link") else ""))


def popup_rect(d):
    """Where the pop-up appears, in the object's own coordinates."""
    w, h = d.get("pop_w", 260), d.get("pop_h", 180)
    side = d.get("side", "right")
    if side == "left":
        return QRectF(-w - 10, 0, w, h)
    if side == "above":
        return QRectF(0, -h - 10, w, h)
    if side == "below":
        return QRectF(0, d["h"] + 10, w, h)
    return QRectF(d["w"] + 10, 0, w, h)


def paint_popup(p, r, d, win):
    pm = win.pixmap(d.get("asset"))
    p.save()
    p.setClipRect(r)
    if pm is None or pm.isNull():
        p.fillRect(r, QColor("#eef1f5"))
        p.setPen(QColor("#6b7686"))
        p.drawText(r.adjusted(6, 6, -6, -6), int(Qt.AlignCenter | Qt.TextWordWrap),
                   "Pop-up rollover\nChoose a picture in Edit properties")
    else:
        k = max(r.width() / pm.width(), r.height() / pm.height()) if d.get("fit") != "contain" \
            else min(r.width() / pm.width(), r.height() / pm.height())
        tw, th = pm.width() * k, pm.height() * k
        p.drawPixmap(QRectF(r.center().x() - tw / 2, r.center().y() - th / 2, tw, th), pm, QRectF(pm.rect()))
    p.restore()
    p.setPen(QPen(QColor("#2b7de9"), 1, Qt.DashLine))
    p.setBrush(Qt.NoBrush)
    p.drawRect(r.adjusted(.5, .5, -.5, -.5))
    p.fillRect(QRectF(r.left(), r.bottom() - 16, 70, 16), QColor("#2b7de9"))
    p.setPen(QColor("white"))
    f = QFont()
    f.setPixelSize(10)
    p.setFont(f)
    p.drawText(QRectF(r.left(), r.bottom() - 16, 70, 16), int(Qt.AlignCenter), "Pop-up " + d.get("side", "right"))
    if getattr(win, "popup_preview", None) is d:
        pr = popup_rect(d).translated(r.topLeft())
        pm2 = win.pixmap(d.get("pop_asset"))
        p.setBrush(QColor("#ffffff"))
        p.setPen(QPen(QColor("#2b7de9"), 2))
        p.drawRect(pr)
        if pm2 is not None and not pm2.isNull():
            p.drawPixmap(pr.adjusted(2, 2, -2, -2), pm2, QRectF(pm2.rect()))
        else:
            p.setPen(QColor("#222222"))
            p.drawText(pr.adjusted(8, 8, -8, -8), int(Qt.AlignLeft | Qt.AlignTop | Qt.TextWordWrap),
                       d.get("pop_text") or "(the pop-up text)")


def paint_arttext(p, r, d, win):
    from . import pathtext
    pathtext.paint(p, r, d)


def paint_marquee(p, r, d, win):
    if d.get("fill"):
        p.fillRect(r, QColor(d["fill"]))
    p.setFont(font_for(d))
    p.setPen(QColor(d.get("color", "#222222")))
    p.save()
    p.setClipRect(r)
    p.drawText(r.adjusted(10, 0, -10, 0), int(Qt.AlignVCenter | Qt.AlignLeft), d.get("text", ""))
    p.restore()
    p.setPen(QPen(QColor("#9aa3ad"), 1, Qt.DotLine))
    p.drawRect(r.adjusted(.5, .5, -.5, -.5))


# ---------------------------------------------------------------- HTML
def esc(s):
    return html.escape(s or "", quote=True)


def video_embed(url, d=None):
    u = (url or "").strip()
    d = d or {}
    m = re.search(r"(?:youtube\.com/watch\?.*v=|youtu\.be/|youtube\.com/embed/)([\w-]{6,})", u)
    if not m and re.fullmatch(r"[\w-]{11}", u):        # a bare video ID is fine too
        m = re.match(r"([\w-]{11})", u)
    if m:
        vid = m.group(1)
        q = []
        if d.get("autoplay"):
            q.append("autoplay=1&mute=1")           # browsers only autoplay muted video
        if d.get("loop"):
            q.append("loop=1&playlist=" + vid)
        if d.get("related") is False:
            q.append("rel=0")
        if d.get("fullscreen") is False:
            q.append("fs=0")
        if d.get("hd"):
            q.append("vq=hd720")
        if d.get("showinfo") is False:
            q.append("modestbranding=1")
        # always https: an http embed is blocked by modern browsers
        return ("iframe", "https://www.youtube.com/embed/%s%s" % (vid, ("?" + "&".join(q)) if q else ""))
    m = re.search(r"vimeo\.com/(?:video/)?(\d+)", u)
    if m:
        return ("iframe", "https://player.vimeo.com/video/" + m.group(1))
    if re.search(r"\.(mp4|webm|ogg)(\?|$)", u, re.I):
        return ("video", u)
    return ("iframe", u) if u else ("none", "")


def text_css(d):
    return ("font-family:'%s',sans-serif;font-size:%dpx;color:%s;font-weight:%s;font-style:%s"
            % (d.get("font", "sans-serif"), d.get("size", 15), d.get("color", "#222"),
               "bold" if d.get("bold") else "normal",
               "italic" if d.get("italic") else "normal"))


def export_extra(d, st, tag, attr, files, anames):
    """HTML for one Phase 3 object. `st` is the common position/size style list."""
    kind = d["kind"]
    css = ";".join(st)
    if kind in webapps.REGISTRY:
        return webapps.export(d, css, files, anames, tag, attr)
    if kind == "shape":
        from . import shapes
        w, h = max(d["w"], 1), max(d["h"], 1)
        sw = d.get("sw", 0) if d.get("stroke") else 0
        dash = {"dashed": ' stroke-dasharray="%d %d"' % (sw * 3, sw * 2),
                "dotted": ' stroke-dasharray="%d %d"' % (sw, sw * 2)}.get(d.get("sstyle"), "") if sw else ""
        svg = ('<svg width="100%%" height="100%%" viewBox="0 0 %d %d" preserveAspectRatio="none" '
               'style="overflow:visible;display:block"><path d="%s" fill="%s" stroke="%s" stroke-width="%s" '
               'stroke-linejoin="round" stroke-linecap="round" vector-effect="non-scaling-stroke"%s/></svg>'
               % (round(w), round(h), shapes.svg_d(shape_nodes_of(d), d.get("closed", True), w, h),
                  d.get("fill") or "none", d.get("stroke") or "none", sw, dash))
        return '<%s class="o"%s style="%s">%s</%s>' % (tag, attr, css, svg, tag)
    if kind == "repeater":
        return ""                       # filled in by Database Merge before the page is written
    if kind == "table":
        from . import tablecore as tc
        rows_n, cols_n = max(d["rows"], 1), max(d["cols"], 1)
        spans, covered = tc.layout(d)
        colw = tc.fractions(d, "colw", cols_n)
        rowh = tc.fractions(d, "rowh", rows_n)
        rows = []
        for i in range(rows_n):
            cells = []
            for c in range(cols_n):
                if (i, c) in covered:
                    continue
                rs, cs = spans.get((i, c), (1, 1))
                f = tc.cell_fmt(d, i, c)
                head = d.get("header") and i == 0
                bd = ("border:%dpx solid %s;" % (d["sw"], d["stroke"])) if d.get("sw") else ""
                if f.get("fill"):
                    bg = f["fill"]
                elif head:
                    bg = d["hfill"]
                elif d.get("band") and (i - (1 if d.get("header") else 0)) % 2 == 1:
                    bg = d["band"]
                else:
                    bg = d.get("fill") or "transparent"
                col = f.get("color") or (d["hcolor"] if head else d["color"])
                extra = "text-align:%s;vertical-align:%s;" % (
                    f.get("align", "left"), {"top": "top", "bottom": "bottom"}.get(f.get("valign"), "middle"))
                if "bold" in f:
                    extra += "font-weight:%s;" % ("bold" if f["bold"] else "normal")
                if "italic" in f:
                    extra += "font-style:%s;" % ("italic" if f["italic"] else "normal")
                span = (' rowspan="%d"' % rs if rs > 1 else "") + (' colspan="%d"' % cs if cs > 1 else "")
                tag_ = "th" if head else "td"
                cells.append('<%s%s style="%sbackground:%s;color:%s;padding:0 8px;%s">%s</%s>'
                             % (tag_, span, bd, bg, col, extra, esc(tc.text_at(d, i, c)).replace("\n", "<br>"), tag_))
            rows.append('<tr style="height:%.3f%%">%s</tr>' % (rowh[i] * 100, "".join(cells)))
        group = "<colgroup>%s</colgroup>" % "".join('<col style="width:%.3f%%">' % (w * 100) for w in colw)
        return ('<table class="o" style="%s;border-collapse:collapse;table-layout:fixed;%s">%s%s</table>'
                % (css, text_css(d), group, "".join(rows)))
    if kind == "gallery":
        imgs = []
        for aid in d.get("assets") or []:
            src = "images/" + anames.get(aid, "missing.png")
            imgs.append('<a class="lb" href="%s"><img src="%s" alt="" style="width:100%%;height:100%%;'
                        'object-fit:%s;display:block;border-radius:%dpx"></a>'
                        % (esc(src), esc(src), "contain" if d.get("fit") == "contain" else "cover",
                           d.get("radius", 0)))
        return ('<div class="o gal" style="%s;display:grid;grid-template-columns:repeat(%d,1fr);'
                'gap:%dpx;grid-auto-rows:1fr">%s</div>'
                % (css, max(d.get("cols", 3), 1), d.get("gap", 10), "".join(imgs)))
    if kind == "video":
        how, src = video_embed(d.get("url"), d)
        if how == "video":
            inner = '<video src="%s" controls style="width:100%%;height:100%%"></video>' % esc(src)
        elif how == "iframe":
            inner = ('<iframe src="%s" style="width:100%%;height:100%%;border:0" '
                     'allowfullscreen loading="lazy"></iframe>' % esc(src))
        else:
            inner = ""
        return '<div class="o" style="%s;background:#000">%s</div>' % (css, inner)
    if kind in ("search", "subscribe", "login", "searchresults"):
        return special_html(d, css, files)
    if kind == "slider":
        return slider_html(d, css, files, anames)
    if kind == "frame":
        src = (d.get("url") or "").strip()
        if src.startswith("http://"):
            src = "https://" + src[7:]
        return ('<div class="o" style="%s"><iframe src="%s" style="width:100%%;height:100%%;border:0" '
                'loading="lazy"></iframe></div>' % (css, esc(src)))
    if kind == "map":
        src = "https://maps.google.com/maps?q=%s&z=%d&output=embed" % (
            quote(d.get("address", "")), d.get("zoom", 14))
        return ('<div class="o" style="%s"><iframe src="%s" style="width:100%%;height:100%%;border:0" '
                'loading="lazy"></iframe></div>' % (css, esc(src)))
    if kind == "audio":
        src = ("images/" + anames[d["asset"]]) if d.get("asset") in anames else d.get("url", "")
        return '<div class="o" style="%s"><audio src="%s" controls style="width:100%%"></audio></div>' % (css, esc(src))
    if kind == "field":
        return field_html(d, css)
    if kind == "social":
        links = "".join('<a href="%s" data-net="%s" data-base="%s" target="_blank" rel="noopener" '
                        'style="display:inline-block;width:%dpx;height:%dpx;line-height:%dpx;'
                        'text-align:center;border-radius:20%%;background:%s;color:#fff;'
                        'font:bold %dpx sans-serif;text-decoration:none;margin-right:8px" '
                        'aria-label="%s">%s</a>'
                        % (esc(profile_url(d, n)), n, esc(share_url(n)), min(d["h"], 44),
                           min(d["h"], 44), min(d["h"], 44),
                           NETS.get(n, ("?", "#555", n))[1], int(min(d["h"], 44) * .45),
                           NETS.get(n, ("?", "#555", n))[2], NETS.get(n, ("?",))[0])
                        for n in d.get("nets") or [])
        return '<div class="o social" style="%s">%s</div>' % (css, links)
    if kind == "html":
        return '<div class="o" style="%s">%s</div>' % (css, d.get("code", ""))
    if kind == "arttext":
        from . import pathtext
        return pathtext.svg_html(d, css)
    if kind == "rssreader":
        rid = "rss-" + str(d.get("id", "x"))
        fid = rss_id(d.get("url", "").strip()) if d.get("url", "").strip() else 0
        url = "%srss-reader.php?f=%d&n=%d" % (CONTEXT["prefix"], fid, max(1, min(int(d.get("count", 5)), 20)))
        CONTEXT["scripts"].append(RSS_JS.replace("__ID__", json.dumps(rid)).replace("__URL__", json.dumps(url))
                                  .replace("__DATE__", "true" if d.get("show_date") else "false")
                                  .replace("__DESC__", "true" if d.get("show_desc") else "false"))
        return ('<div class="o rss" id="%s" style="%s;overflow:auto;box-sizing:border-box;padding:6px 10px;%s">'
                'Loading headlines...</div>' % (rid, css, text_css(d)))
    if kind == "hotspot":
        from .export import resolve_link
        href = resolve_link(d.get("link", ""), files) if d.get("link") else ""
        extra = ""
        if d.get("shape") == "ellipse":
            extra = "border-radius:50%"
        elif d.get("shape") == "rounded":
            extra = "border-radius:%dpx" % int(min(d["w"], d["h"]) * 0.25)
        elif d.get("shape") in HOT_CLIP:
            extra = "clip-path:" + HOT_CLIP[d["shape"]]
        tip = ' title="%s" aria-label="%s"' % (esc(d.get("tip", "")), esc(d.get("tip", ""))) if d.get("tip") else ""
        blank = ' target="_blank" rel="noopener"' if href.startswith(("http://", "https://")) else ""
        tag_ = "a" if href else "div"
        hattr = ' href="%s"%s' % (esc(href), blank) if href else ""
        return '<%s class="o hs"%s%s style="%s;display:block;%s"></%s>' % (tag_, hattr, tip, css, extra, tag_)
    if kind == "popup":
        from .export import _page_css
        for rule in (".pr{overflow:visible}", ".pr .pr-pop{display:none;position:absolute;z-index:60;"
                     "box-shadow:0 6px 18px rgba(0,0,0,.35);background:#fff;overflow:hidden;box-sizing:border-box}",
                     ".pr:hover .pr-pop,.pr:focus-within .pr-pop{display:block}"):
            if rule not in _page_css:
                _page_css.append(rule)
        place = {"left": "right:100%%;top:0;margin-right:10px", "above": "bottom:100%%;left:0;margin-bottom:10px",
                 "below": "top:100%%;left:0;margin-top:10px"}.get(d.get("side"), "left:100%%;top:0;margin-left:10px")
        base = ""
        if d.get("asset") in anames:
            base = ('<img src="images/%s" alt="%s" style="width:100%%;height:100%%;object-fit:%s;display:block">'
                    % (esc(anames[d["asset"]]), esc(d.get("alt", "")),
                       "contain" if d.get("fit") == "contain" else "cover"))
        if d.get("pop_asset") in anames:
            inner = ('<img src="images/%s" alt="" style="width:100%%;height:100%%;object-fit:contain;display:block">'
                     % esc(anames[d["pop_asset"]]))
        else:
            inner = '<div style="padding:10px;white-space:pre-wrap;color:#222;font:15px sans-serif">%s</div>' % esc(d.get("pop_text", ""))
        pop = '<div class="pr-pop" style="width:%dpx;height:%dpx;%s">%s</div>' % (
            d.get("pop_w", 260), d.get("pop_h", 180), place % (), inner)
        tag_, hattr = "div", ""
        if d.get("link"):
            from .export import resolve_link
            tag_, hattr = "a", ' href="%s"' % esc(resolve_link(d["link"], files))
        return '<%s class="o pr"%s style="%s;display:block" tabindex="0">%s%s</%s>' % (tag_, hattr, css, base, pop, tag_)
    if kind == "marquee":
        bg = ";background:" + d["fill"] if d.get("fill") else ""
        return ('<div class="o" style="%s;overflow:hidden%s"><div class="mq" style="%s;'
                'line-height:%dpx;animation-duration:%ds">%s</div></div>'
                % (css, bg, text_css(d), d["h"], max(d.get("speed", 10), 1), esc(d.get("text", ""))))
    return ""


def captcha_salt(site_title, form_email):
    import hashlib
    return hashlib.sha256(("%s|%s|sw-captcha" % (site_title, form_email)).encode("utf-8")).hexdigest()[:20]


def captcha_hash(answer, salt):
    import hashlib
    return hashlib.sha256((str(answer).strip().lower() + salt).encode("utf-8")).hexdigest()


def field_html(d, css):
    t = d.get("ftype", "text")
    if t == "recaptcha":
        if '<script src="https://www.google.com/recaptcha/api.js"' not in "".join(CONTEXT["scripts"]):
            CONTEXT["scripts"].append('<script src="https://www.google.com/recaptcha/api.js" async defer></script>')
        return '<div class="o g-recaptcha" data-sitekey="%s" style="%s"></div>' % (esc(d.get("rc_site", "")), css)
    if t == "captcha":
        box = ("%s;%s;box-sizing:border-box;padding:0 10px;background:%s;border:%s;border-radius:%dpx"
               % (css, text_css(d), d.get("fill") or "#fff",
                  ("%dpx solid %s" % (d["sw"], d["stroke"])) if d.get("sw") and d.get("stroke") else "0",
                  d.get("radius", 4)))
        return ('<input class="o" type="text" name="captcha_answer" placeholder="%s" aria-label="%s" required '
                'autocomplete="off" style="%s"><input type="hidden" name="_cap" value="%s">'
                % (esc(d.get("label", "")), esc(d.get("label", "")), box,
                   captcha_hash(d.get("answer", ""), CONTEXT.get("salt", ""))))
    name = esc(re.sub(r"[^A-Za-z0-9_]", "_", d.get("name") or "field"))
    req = " required" if d.get("required") else ""
    label = esc(d.get("label", ""))
    base = text_css(d)
    if t in ("checkbox", "radio"):
        return ('<label class="o" style="%s;display:flex;align-items:center;gap:8px;%s">'
                '<input type="%s" name="%s" value="%s"%s>%s</label>'
                % (css, base, t, name, label or "yes", req, label))
    if t == "submit":
        return ('<button class="o" type="submit" style="%s;%s;font-weight:bold;border:0;'
                'border-radius:%dpx;background:%s;color:%s;cursor:pointer">%s</button>'
                % (css, text_css(dict(d, bold=True)), d.get("radius", 4),
                   d.get("fill") or "#2b7de9", d.get("color") or "#fff", label or "Send"))
    box = ("%s;%s;box-sizing:border-box;padding:0 10px;background:%s;border:%s;border-radius:%dpx"
           % (css, base, d.get("fill") or "#fff",
              ("%dpx solid %s" % (d["sw"], d["stroke"])) if d.get("sw") and d.get("stroke") else "0",
              d.get("radius", 4)))
    if t == "textarea":
        return ('<textarea class="o" name="%s" placeholder="%s"%s style="%s;padding:8px 10px;resize:none">'
                '</textarea>' % (name, label, req, box))
    if t == "select":
        opts = "".join("<option>%s</option>" % esc(o.strip())
                       for o in (d.get("options") or "").splitlines() if o.strip())
        return '<select class="o" name="%s"%s style="%s">%s</select>' % (name, req, box, opts)
    return ('<input class="o" type="%s" name="%s" placeholder="%s"%s style="%s">'
            % (t if t in ("text", "email", "date", "file") else "text", name, label, req, box))


SEND_PHP = """<?php
// Sends the contact form to the site owner's address, then returns to the page.
$to = %(to)s;
if ($_SERVER['REQUEST_METHOD'] !== 'POST' || $to === '') { http_response_code(400); exit('Form not set up.'); }
if (!empty($_POST['website'])) { header('Location: ' . ($_SERVER['HTTP_REFERER'] ?? '/')); exit; }  // spam trap
%(checks)s
$lines = [];
foreach ($_POST as $k => $v) {
    if (in_array($k, array('website', '_page', '_cap', 'captcha_answer', 'g-recaptcha-response'), true)) continue;
    $k = preg_replace('/[^A-Za-z0-9_ ]/', '', (string)$k);
    $lines[] = $k . ': ' . trim(strip_tags(is_array($v) ? implode(', ', $v) : (string)$v));
}
$from = 'noreply@' . preg_replace('/^www\\./', '', $_SERVER['HTTP_HOST'] ?? 'localhost');
$reply = isset($_POST['email']) ? filter_var($_POST['email'], FILTER_VALIDATE_EMAIL) : false;
$headers = "From: $from\\r\\n" . ($reply ? "Reply-To: $reply\\r\\n" : '');
$ok = mail($to, 'New message from your website', implode("\\n", $lines), $headers);
$back = $_SERVER['HTTP_REFERER'] ?? '/';
header('Location: ' . $back . (strpos($back, '?') === false ? '?' : '&') . ($ok ? 'sent=1' : 'sent=0'));
"""


CAPTCHA_CHECK = """// CAPTCHA: the visitor must give the answer written in the page (case does not matter).
if (isset($_POST['_cap'])) {
    $ans = strtolower(trim((string)(isset($_POST['captcha_answer']) ? $_POST['captcha_answer'] : '')));
    if (!hash_equals((string)$_POST['_cap'], hash('sha256', $ans . %(salt)s))) {
        $back = isset($_SERVER['HTTP_REFERER']) ? $_SERVER['HTTP_REFERER'] : '/';
        header('Location: ' . $back . (strpos($back, '?') === false ? '?' : '&') . 'sent=captcha'); exit;
    }
}
"""

RECAPTCHA_CHECK = """// reCAPTCHA: ask Google whether the visitor passed.
$rcsecret = %(secret)s;
if ($rcsecret !== '') {
    $resp = isset($_POST['g-recaptcha-response']) ? (string)$_POST['g-recaptcha-response'] : '';
    $ok_rc = false;
    if ($resp !== '') {
        $ctx = stream_context_create(array('http' => array('method' => 'POST', 'timeout' => 8,
            'header' => 'Content-type: application/x-www-form-urlencoded',
            'content' => http_build_query(array('secret' => $rcsecret, 'response' => $resp,
                         'remoteip' => isset($_SERVER['REMOTE_ADDR']) ? $_SERVER['REMOTE_ADDR'] : '')))));
        $json = @file_get_contents('https://www.google.com/recaptcha/api/siteverify', false, $ctx);
        $data = $json ? json_decode($json, true) : null;
        $ok_rc = is_array($data) && !empty($data['success']);
    }
    if (!$ok_rc) {
        $back = isset($_SERVER['HTTP_REFERER']) ? $_SERVER['HTTP_REFERER'] : '/';
        header('Location: ' . $back . (strpos($back, '?') === false ? '?' : '&') . 'sent=captcha'); exit;
    }
}
"""


def _php_str(s):
    return "'" + str(s).replace("\\", "\\\\").replace("'", "\\'") + "'"


def send_php(email, doc=None):
    checks = ""
    if doc is not None:
        fields = [i for lst in [p["items"] for p in doc.pages] + doc.all_master_lists()
                  for i in lst if i.get("kind") == "field"]
        if any(i.get("ftype") == "captcha" for i in fields):
            checks += CAPTCHA_CHECK % {"salt": _php_str(captcha_salt(doc.site_title, doc.form_email))}
        rc = [i for i in fields if i.get("ftype") == "recaptcha" and i.get("rc_secret")]
        if rc:
            checks += RECAPTCHA_CHECK % {"secret": _php_str(rc[0]["rc_secret"])}
    return SEND_PHP % {"to": "'" + email.replace("\\", "").replace("'", "") + "'", "checks": checks}


# ---------------------------------------------------------------- search, sign-up, login
CONTEXT = {"index": [], "prefix": "", "forms": [], "scripts": [], "salt": ""}

RESULTS_JS = """<script>
(function(){
var IDX=__IDX__, P=__PREFIX__, EMPTY=__EMPTY__;
var box=document.getElementById(__ID__);
var q=(new URLSearchParams(location.search).get('q')||'').trim();
if(!box||!q)return;
var words=q.toLowerCase().split(/\\s+/).filter(Boolean);
var hits=[];
IDX.forEach(function(p){
  var t=(p.t||'').toLowerCase(),b=(p.x||'').toLowerCase(),score=0,all=true;
  words.forEach(function(w){
    var inT=t.indexOf(w)>=0,c=0,i=-1;
    while((i=b.indexOf(w,i+1))>=0&&c<20)c++;
    if(!inT&&!c)all=false;
    score+=(inT?8:0)+c;
  });
  if(all&&score>0)hits.push({p:p,s:score});
});
hits.sort(function(a,b){return b.s-a.s;});
function el(tag,txt,css){var e=document.createElement(tag);if(txt!==undefined)e.textContent=txt;if(css)e.style.cssText=css;return e;}
box.innerHTML='';
box.appendChild(el('div',hits.length+(hits.length===1?' result':' results')+' for "'+q+'"',
  'margin-bottom:10px;color:#667085;font-size:14px'));
if(!hits.length){box.appendChild(el('div',EMPTY));return;}
hits.slice(0,30).forEach(function(h){
  var a=el('a',h.p.t||h.p.u,'display:block;font-weight:bold;font-size:1.1em;color:#1a5fb4');
  a.href=P+h.p.u;
  var x=h.p.x||'',i=x.toLowerCase().indexOf(words[0]),st=Math.max(0,i-60);
  box.appendChild(a);
  box.appendChild(el('div',(st>0?'...':'')+x.substr(st,170)+(x.length>st+170?'...':''),
    'color:#555;margin:2px 0 14px;font-size:.9em'));
});
})();
</script>
"""


def _field_css(d):
    return ("box-sizing:border-box;height:100%%;flex:1;min-width:0;padding:0 12px;%s;"
            "background:%s;color:%s;border:%s;border-radius:%dpx"
            % (text_css(d), d.get("fill") or "#fff", d.get("color", "#222"),
               ("%dpx solid %s" % (d["sw"], d["stroke"])) if d.get("stroke") and d.get("sw") else "0",
               d.get("radius", 4)))


def _btn_css(d):
    return ("height:100%%;border:0;border-radius:%dpx;background:%s;color:%s;%s;font-weight:bold;"
            "padding:0 16px;cursor:pointer" % (d.get("radius", 4), d.get("btnfill") or "#2b7de9",
                                               d.get("btncolor") or "#fff",
                                               text_css(dict(d, bold=True, color=d.get("btncolor") or "#fff"))))


def special_html(d, css, files):
    import json
    kind = d["kind"]
    fid = "sw-%s-%s" % (kind, d["id"])
    forms, scripts = CONTEXT["forms"], CONTEXT["scripts"]
    if kind == "search":
        link = d.get("link", "")
        action = files.get(link[5:], "") if link.startswith("page:") else link
        forms.append('<form id="%s" method="get" action="%s" role="search"></form>'
                     % (fid, esc(action)))
        return ('<div class="o" style="%s;display:flex;gap:6px">'
                '<input type="search" name="q" form="%s" placeholder="%s" aria-label="%s" '
                'required style="%s"><button type="submit" form="%s" style="%s">%s</button></div>'
                % (css, fid, esc(d.get("label")), esc(d.get("label")), _field_css(d), fid,
                   _btn_css(d), esc(d.get("btn"))))
    if kind == "subscribe":
        forms.append('<form id="%s" method="post" action="subscribe.php">'
                     '<input type="text" name="website" tabindex="-1" autocomplete="off" '
                     'style="position:absolute;left:-9999px"></form>' % fid)
        return ('<div class="o" style="%s;display:flex;gap:6px">'
                '<input type="email" name="email" form="%s" placeholder="%s" aria-label="%s" '
                'required style="%s"><button type="submit" form="%s" style="%s">%s</button></div>'
                % (css, fid, esc(d.get("label")), esc(d.get("label")), _field_css(d), fid,
                   _btn_css(d), esc(d.get("btn"))))
    if kind == "login":
        forms.append('<form id="%s" method="post" action="sw-auth.php">'
                     '<input type="hidden" name="action" value="login">'
                     '<input type="hidden" name="return" value=""></form>' % fid)
        scripts.append("<script>document.querySelector('#%s input[name=return]').value="
                       "location.pathname+location.search;</script>" % fid)
        field = ("display:block;width:100%%;box-sizing:border-box;height:34px;padding:0 10px;"
                 "margin-bottom:8px;border:1px solid #9aa3ad;border-radius:4px;font-size:%dpx"
                 % d.get("size", 15))
        return ('<div class="o" style="%s;padding:14px;background:%s;border:%s;border-radius:%dpx;%s">'
                '<div style="font-weight:bold;margin-bottom:8px">%s</div>'
                '<input name="user" form="%s" placeholder="User name" autocomplete="username" required style="%s">'
                '<input type="password" name="pass" form="%s" placeholder="Password" '
                'autocomplete="current-password" required style="%s">'
                '<button type="submit" form="%s" style="height:34px;%s">%s</button></div>'
                % (css, d.get("fill") or "#fff",
                   ("%dpx solid %s" % (d["sw"], d["stroke"])) if d.get("stroke") and d.get("sw") else "0",
                   d.get("radius", 6), text_css(d), esc(d.get("title")), fid, field, fid, field, fid,
                   _btn_css(d).replace("height:100%", "height:34px"), esc(d.get("btn"))))
    # search results
    scripts.append(RESULTS_JS.replace("__IDX__", json.dumps(CONTEXT["index"]).replace("</", "<\\/"))
                   .replace("__PREFIX__", json.dumps(CONTEXT["prefix"]))
                   .replace("__EMPTY__", json.dumps(d.get("empty", "")))
                   .replace("__ID__", json.dumps(fid)))
    return '<div class="o" id="%s" style="%s;%s;overflow:auto"></div>' % (fid, css, text_css(d))


# ---------------------------------------------------------------- slider
SLIDER_JS = """<script>
(function(){
var root=document.getElementById(__ID__);if(!root)return;
var slides=[].slice.call(root.querySelectorAll('.sw-slide')),n=slides.length;
if(!n)return;
var cur=Math.max(0,Math.min(n-1,(parseInt(root.getAttribute('data-start'),10)||1)-1));
var anim=root.getAttribute('data-anim')||'slide';
var speed=parseInt(root.getAttribute('data-speed'),10)||600;
var loop=parseInt(root.getAttribute('data-loop'),10)||5000;
var auto=root.getAttribute('data-auto')==='1',pause=root.getAttribute('data-pause')==='1';
var reduce=window.matchMedia&&matchMedia('(prefers-reduced-motion: reduce)').matches;
var dots=[].slice.call(root.querySelectorAll('.sw-dots button')),busy=false,timer=null;
function pos(el,x,y,o,s,anim_){
  el.style.transition=anim_?'transform '+speed+'ms ease,opacity '+speed+'ms ease':'none';
  el.style.transform='translate('+x+'%,'+y+'%) scale('+s+')';
  el.style.opacity=o;
  el.style.visibility=(o>0||x!==0||y!==0)?'visible':'hidden';
}
function rest(el){
  pos(el,anim==='slide'?100:0,anim==='vslide'?100:0,0,anim==='zoom'?1.08:1,false);
}
slides.forEach(function(s,k){if(k===cur)pos(s,0,0,1,1,false);else rest(s);});
function mark(){dots.forEach(function(d,k){d.setAttribute('aria-current',k===cur?'true':'false');
  d.style.opacity=k===cur?1:.5;});}
mark();
var pending=null;
function go(to,dir){
  if(busy){pending=[to,dir];return;}          // a click during a change is not lost
  if(to===cur||n<2)return;
  if(dir===undefined)dir=(to>cur)?1:-1;
  var a=slides[cur],b=slides[to];busy=true;
  if(anim==='fade'||anim==='zoom'){
    pos(b,0,0,0,anim==='zoom'?1.08:1,false);b.offsetWidth;
    pos(a,0,0,0,1,true);pos(b,0,0,1,1,true);
  }else{
    var x=anim==='slide'?dir*100:0,y=anim==='vslide'?dir*100:0;
    pos(b,x,y,1,1,false);b.offsetWidth;
    pos(a,-x,-y,1,1,true);pos(b,0,0,1,1,true);
  }
  cur=to;mark();
  setTimeout(function(){
    busy=false;slides.forEach(function(s,k){if(k!==cur)rest(s);});
    if(pending){var p=pending;pending=null;go(p[0],p[1]);}
  },speed+40);
}
function next(){go((cur+1)%n,1);}
function prev(){go((cur-1+n)%n,-1);}
function start(){stop();if(auto&&!reduce&&n>1)timer=setInterval(next,loop);}
function stop(){if(timer){clearInterval(timer);timer=null;}}
var pv=root.querySelector('.sw-prev'),nx=root.querySelector('.sw-next');
if(pv)pv.addEventListener('click',function(){prev();start();});
if(nx)nx.addEventListener('click',function(){next();start();});
dots.forEach(function(d,k){d.addEventListener('click',function(){go(k,k>cur?1:-1);start();});});
if(pause){root.addEventListener('mouseenter',stop);root.addEventListener('mouseleave',start);
  root.addEventListener('focusin',stop);root.addEventListener('focusout',start);}
root.addEventListener('keydown',function(e){
  if(e.key==='ArrowLeft'){prev();start();}else if(e.key==='ArrowRight'){next();start();}});
var sx=null;
root.addEventListener('touchstart',function(e){sx=e.touches[0].clientX;},{passive:true});
root.addEventListener('touchend',function(e){
  if(sx===null)return;var dx=e.changedTouches[0].clientX-sx;sx=null;
  if(Math.abs(dx)>40){if(dx<0)next();else prev();start();}},{passive:true});
document.addEventListener('visibilitychange',function(){if(document.hidden)stop();else start();});
function scale(){root.style.setProperty('--k',root.clientWidth/__DW__);}
if(window.ResizeObserver)new ResizeObserver(scale).observe(root);
window.addEventListener('resize',scale);scale();
start();
})();
</script>
"""


def slider_html(d, css, files, anames):
    import json
    panels = d.get("panels") or []
    fid = "sw-slider-" + d["id"]
    slides, dots = [], []
    for i, pn in enumerate(panels):
        bg = "background:" + (pn.get("bg") or "#1f3a5f")
        img = ""
        if pn.get("asset") in anames:
            img = ('<img src="images/%s" alt="" style="position:absolute;inset:0;width:100%%;'
                   'height:100%%;object-fit:cover">' % esc(anames[pn["asset"]]))
        ov = ""
        if pn.get("overlay_op"):
            r, g, b = [int((pn.get("overlay") or "#000000").lstrip("#")[j:j + 2], 16)
                       for j in (0, 2, 4)]
            ov = ('<div style="position:absolute;inset:0;background:rgba(%d,%d,%d,%.2f)"></div>'
                  % (r, g, b, pn["overlay_op"] / 100))
        al = pn.get("align", "left")
        just = {"left": "flex-start", "right": "flex-end"}.get(al, "center")
        href = files.get(pn.get("link", "")[5:], "") if pn.get("link", "").startswith("page:") \
            else pn.get("link", "")
        btn = ""
        if pn.get("btn"):
            btn = ('<a href="%s" style="display:inline-block;margin-top:calc(var(--k,1)*16px);'
                   'padding:calc(var(--k,1)*10px) calc(var(--k,1)*22px);background:#fff;color:#1f3a5f;'
                   'border-radius:6px;font-weight:bold;text-decoration:none;'
                   'font-size:calc(var(--k,1)*16px)">%s</a>' % (esc(href or "#"), esc(pn["btn"])))
        cap = ('<div style="position:absolute;inset:0;display:flex;flex-direction:column;'
               'justify-content:center;align-items:%s;text-align:%s;padding:0 12%%;color:%s">'
               '<div style="font-size:calc(var(--k,1)*44px);font-weight:bold;line-height:1.15">%s</div>'
               '<div style="font-size:calc(var(--k,1)*20px);margin-top:calc(var(--k,1)*10px)">%s</div>'
               '%s</div>' % (just, al, pn.get("color") or "#fff", esc(pn.get("heading")),
                             esc(pn.get("text")), btn))
        slides.append('<div class="sw-slide" role="group" aria-label="Slide %d of %d" '
                      'style="%s">%s%s%s</div>' % (i + 1, len(panels), bg, img, ov, cap))
        dots.append('<button type="button" aria-label="Show slide %d"></button>' % (i + 1))
    arrows = ""
    if d.get("arrows", True):
        arrows = ('<button type="button" class="sw-prev" aria-label="Previous slide">&#8249;</button>'
                  '<button type="button" class="sw-next" aria-label="Next slide">&#8250;</button>')
    dotbar = '<div class="sw-dots">%s</div>' % "".join(dots) if d.get("dots", True) and len(panels) > 1 else ""
    CONTEXT["scripts"].append(SLIDER_JS.replace("__ID__", json.dumps(fid))
                              .replace("__DW__", str(max(d.get("w", 760), 1))))
    return ('<div class="o sw-slider" id="%s" tabindex="0" role="region" aria-roledescription="carousel" '
            'aria-label="Slideshow" data-anim="%s" data-auto="%d" data-loop="%d" data-speed="%d" '
            'data-start="%d" data-pause="%d" style="%s;overflow:hidden">%s%s%s</div>'
            % (fid, esc(d.get("anim", "slide")), 1 if d.get("autoplay", True) else 0,
               int(d.get("loop", 5000)), int(d.get("speed", 600)), int(d.get("start", 1)),
               1 if d.get("pause", True) else 0, css, "".join(slides), arrows, dotbar))


from . import model as _model  # noqa: E402,F401  (makes sure the web-app kinds are registered)
EXTRA_KINDS |= set(webapps.REGISTRY)          # polls, blog, shop objects
