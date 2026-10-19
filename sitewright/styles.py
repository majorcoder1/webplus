"""Button and navigation-bar style galleries (original designs), plus the
drawing code shared by the canvas and the gallery previews."""
from PyQt5.QtCore import QPointF, QRectF, Qt
from PyQt5.QtGui import (QBrush, QColor, QFontMetrics, QLinearGradient, QPainter,
                         QPen, QPixmap, QPolygonF)

from .extras import font_for

PALETTE = [("Blue", "#2b7de9"), ("Green", "#2e9e5b"), ("Orange", "#e8832a"),
           ("Red", "#d64545"), ("Purple", "#7a4fd1"), ("Slate", "#4b5868")]


def _shade(c, pct):
    q = QColor(c)
    return (q.lighter(pct) if pct > 100 else q.darker(200 - pct)).name()


def button_style(c, variant):
    """Button properties for colour `c`: flat, gradient, outline, pill or raised."""
    dark, light = _shade(c, 80), _shade(c, 125)
    base = dict(color="#ffffff", bold=True, shadow=False, fill2="", stroke="",
                sw=0, hfill=dark, hcolor="#ffffff", pfill=_shade(c, 65))
    if variant == "gradient":
        return dict(base, fill=light, fill2=dark, radius=6, hfill=c, pfill=dark)
    if variant == "outline":
        return dict(base, fill="", color=c, stroke=c, sw=2, radius=4,
                    hfill=c, hcolor="#ffffff", pfill=dark)
    if variant == "pill":
        return dict(base, fill=c, radius=999)
    if variant == "raised":
        return dict(base, fill=light, fill2=c, radius=8, shadow=True,
                    hfill=c, pfill=dark)
    return dict(base, fill=c, radius=4)


def button_styles():
    """30 styles: six colours x flat, gradient, outline, pill, raised."""
    return {"%s %s" % (name, v): button_style(c, v)
            for name, c in PALETTE
            for v in ("flat", "gradient", "outline", "pill", "raised")}


BUTTON_STYLES = button_styles()

_NAV = dict(orient="horizontal", fill="#1f3a5f", color="#ffffff", ifill="",
            ihover="#2f5a8f", hcolor="#ffffff", iradius=0, ipad=16, uline="",
            active="#2f5a8f", acolor="#ffffff", gap=4, radius=0, stroke="", sw=0,
            bold=True, size=15)

NAV_STYLES = {
    "Classic bar": dict(_NAV),
    "Dark underline": dict(_NAV, fill="#14171c", color="#cfd6df", ihover="",
                           hcolor="#ffffff", active="", acolor="#ffffff",
                           uline="#e8832a", gap=8),
    "Light underline": dict(_NAV, fill="#ffffff", color="#334155", ihover="",
                            hcolor="#2b7de9", active="", acolor="#2b7de9",
                            uline="#2b7de9", gap=8, stroke="#d9dee5", sw=1),
    "Tabs": dict(_NAV, fill="#e9edf2", color="#334155", ifill="#d5dce5",
                 ihover="#c3ccd8", hcolor="#1f2937", active="#ffffff",
                 acolor="#1f2937", iradius=8, gap=4),
    "Pills": dict(_NAV, fill="", color="#1f3a5f", ifill="#e8eef7", ihover="#cfe0f7",
                  hcolor="#1f3a5f", active="#1f3a5f", acolor="#ffffff", iradius=40,
                  gap=8),
    "Green bar": dict(_NAV, fill="#2e7d4f", ihover="#256b42", active="#256b42"),
    "Warm pills": dict(_NAV, fill="#fff6ec", color="#8a4b12", ifill="#fde3c4",
                       ihover="#f9cf9c", hcolor="#6b3a0e", active="#e8832a",
                       acolor="#ffffff", iradius=40, gap=8),
    "Drop-down bar": dict(_NAV, orient="dropdown"),
    "Vertical menu": dict(_NAV, orient="vertical", fill="#f4f6f9", color="#1f2937",
                          ihover="#e1e7ef", hcolor="#1f2937", active="#d3dcea",
                          acolor="#1f2937", gap=2, bold=False),
    "Vertical cards": dict(_NAV, orient="vertical", fill="", color="#1f2937",
                           ifill="#ffffff", ihover="#eef3fb", hcolor="#1f3a5f",
                           active="#2b7de9", acolor="#ffffff", iradius=8, gap=8,
                           bold=False),
}


# ------------------------------------------------------------------ drawing
def paint_button(p, r, d):
    p.setRenderHint(QPainter.Antialiasing)
    rad = min(d.get("radius", 0), min(r.width(), r.height()) / 2)
    if d.get("shadow"):
        p.setPen(Qt.NoPen)
        p.setBrush(QColor(0, 0, 0, 70))
        p.drawRoundedRect(r.translated(0, 3), rad, rad)
    if d.get("fill2") and d.get("fill"):
        g = QLinearGradient(r.topLeft(), r.bottomLeft())
        g.setColorAt(0, QColor(d["fill"]))
        g.setColorAt(1, QColor(d["fill2"]))
        brush = QBrush(g)
    else:
        brush = QBrush(QColor(d["fill"])) if d.get("fill") else Qt.NoBrush
    sw = d.get("sw", 0) if d.get("stroke") else 0
    pen = QPen(QColor(d["stroke"]), sw) if sw else Qt.NoPen
    p.setBrush(brush)
    p.setPen(pen)
    inset = sw / 2
    p.drawRoundedRect(r.adjusted(inset, inset, -inset, -inset), rad, rad)
    p.setFont(font_for(d))
    p.setPen(QColor(d.get("color", "#ffffff")))
    al = {"left": Qt.AlignLeft, "right": Qt.AlignRight}.get(d.get("align"), Qt.AlignHCenter)
    p.save()
    p.setClipRect(r)
    p.drawText(r.adjusted(10, 0, -10, 0), int(al | Qt.AlignVCenter | Qt.TextWordWrap),
               d.get("text", ""))
    p.restore()


def paint_nav(p, r, d, entries, current=None, hits=None):
    """entries: [(label, target, depth)]; `current` is the target to highlight."""
    p.setRenderHint(QPainter.Antialiasing)
    sw = d.get("sw", 0) if d.get("stroke") else 0
    p.setPen(QPen(QColor(d["stroke"]), sw) if sw else Qt.NoPen)
    p.setBrush(QColor(d["fill"]) if d.get("fill") else Qt.NoBrush)
    rad = d.get("radius", 0)
    p.drawRoundedRect(r, rad, rad) if rad else p.drawRect(r)

    f = font_for(d)
    fm = QFontMetrics(f)
    p.setFont(f)
    orient = d.get("orient", "horizontal")
    vertical = orient == "vertical"
    ipad = d.get("ipad", 14)
    gap = d.get("gap", 4)
    has_kids = {}
    top = None
    for i, (n, t, dep) in enumerate(entries):
        if dep == 0:
            top = i
            has_kids[i] = False
        elif top is not None:
            has_kids[top] = True
    rows = [(i, e) for i, e in enumerate(entries) if vertical or e[2] == 0]
    if not rows:
        return

    def draw_item(box, i, e):
        name, tgt, dep = e
        if hits is not None:
            hits.append((QRectF(box), tgt))            # where each entry is, for links in a PDF
        on = current is not None and tgt == current
        bg = (d.get("active") if on else d.get("ifill")) or ""
        if bg:
            p.setPen(Qt.NoPen)
            p.setBrush(QColor(bg))
            ir = d.get("iradius", 0)
            p.drawRoundedRect(box, min(ir, box.height() / 2), min(ir, box.height() / 2))
        p.setPen(QColor((d.get("acolor") if on and d.get("active") else d["color"])
                        or d["color"]))
        if vertical:
            p.drawText(box.adjusted(ipad + dep * 16, 0, -6, 0),
                       int(Qt.AlignVCenter | Qt.AlignLeft), name)
        else:
            p.drawText(box, int(Qt.AlignCenter), name)
        if d.get("uline") and (on or not d.get("active")):
            p.setPen(QPen(QColor(d["uline"]), 3))
            y = box.bottom() - 1
            p.drawLine(QPointF(box.left() + 4, y), QPointF(box.right() - 4, y))
        if orient == "dropdown" and has_kids.get(i):
            c = QPointF(box.right() - 10, box.center().y() + 1)
            p.setPen(Qt.NoPen)
            p.setBrush(QColor(d["color"]))
            p.drawPolygon(QPolygonF([QPointF(c.x() - 3, c.y() - 2), QPointF(c.x() + 3, c.y() - 2),
                                     QPointF(c.x(), c.y() + 2)]))

    p.save()
    p.setClipRect(r)
    if vertical:
        rh = fm.height() + ipad
        y = r.top() + 8
        for i, e in rows:
            draw_item(QRectF(r.left() + 8, y, r.width() - 16, rh), i, e)
            y += rh + gap
    else:
        ih = min(r.height() - 8, fm.height() + ipad)
        arrow = 14 if orient == "dropdown" else 0
        widths = [fm.horizontalAdvance(e[0]) + 2 * ipad + (arrow if has_kids.get(i) else 0)
                  for i, e in rows]
        total = sum(widths) + gap * (len(rows) - 1)
        x = {"left": r.left() + 8, "right": r.right() - 8 - total}.get(
            d.get("align"), r.center().x() - total / 2)
        for (i, e), w in zip(rows, widths):
            draw_item(QRectF(x, r.center().y() - ih / 2, w, ih), i, e)
            x += w + gap
    p.restore()


SAMPLE_NAV = [("Home", "page:a", 0), ("About", "page:b", 0),
              ("Services", "page:c", 0), ("Services 1", "page:c1", 1),
              ("Contact", "page:d", 0)]


def preview_button(props, text="Button", w=150, h=52):
    pm = QPixmap(w, h)
    pm.fill(QColor("#ffffff"))
    p = QPainter(pm)
    d = dict(font="Sans Serif", size=15, italic=False, align="center", text=text)
    d.update(props)
    paint_button(p, QRectF(10, 8, w - 20, h - 18), d)
    p.end()
    return pm


def preview_nav(props, w=300, h=70):
    vertical = props.get("orient") == "vertical"
    if vertical:
        h = 150
    pm = QPixmap(w, h)
    pm.fill(QColor("#ffffff"))
    p = QPainter(pm)
    d = dict(font="Sans Serif", italic=False, align="left", size=14)
    d.update(props)
    ents = SAMPLE_NAV
    paint_nav(p, QRectF(4, 6, w - 8, h - 12), d, ents, "page:a")
    p.end()
    return pm
