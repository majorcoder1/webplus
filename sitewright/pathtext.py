"""Artistic text: words set along a curve - an arch, a bowl, a wave or a ring. The same shape is
used to draw it in the editor and to write it as SVG for the published page."""
import html
import math

from PyQt5.QtCore import QPointF
from PyQt5.QtGui import QColor, QFont, QFontMetricsF, QPainterPath, QPen

SHAPES = ["arc", "wave", "ring"]
STEPS = 160


def _geometry(d):
    """(points along the baseline, svg path text, where the text is centred as a fraction 0..1)."""
    w, h = float(d["w"]), float(d["h"])
    shape = d.get("shape", "arc")
    curve = max(-100, min(100, int(d.get("curve", 40)))) / 100.0
    if shape == "ring":
        r = max(min(w, h) * 0.5 - max(int(d.get("size", 40)), 1) * 0.55, 10)
        cx, cy = w / 2, h / 2
        pts = [QPointF(cx - r * math.cos(2 * math.pi * i / STEPS),
                       cy - r * math.sin(2 * math.pi * i / STEPS)) for i in range(STEPS + 1)]
        # starts at the left, runs clockwise over the top; two half circles make the SVG path
        svg = ("M %.2f,%.2f A %.2f,%.2f 0 1 1 %.2f,%.2f A %.2f,%.2f 0 1 1 %.2f,%.2f"
               % (cx - r, cy, r, r, cx + r, cy, r, r, cx - r, cy))
        return pts, svg, 0.25
    if shape == "wave":
        amp = curve * h * 0.3
        x0, x1 = w * 0.05, w * 0.95
        y0 = h * 0.5
        pts = [QPointF(x0 + (x1 - x0) * i / STEPS,
                       y0 - amp * math.sin(2 * math.pi * i / STEPS)) for i in range(STEPS + 1)]
        svg = "M " + " L ".join("%.2f,%.2f" % (p.x(), p.y()) for p in pts)
        return pts, svg, 0.5
    # arc
    chord = w * 0.9
    x0, x1 = w / 2 - chord / 2, w / 2 + chord / 2
    if abs(curve) < 0.02:
        y = h * 0.7
        pts = [QPointF(x0 + chord * i / STEPS, y) for i in range(STEPS + 1)]
        return pts, "M %.2f,%.2f L %.2f,%.2f" % (x0, y, x1, y), 0.5
    sag = abs(curve) * min(h * 0.6, chord / 2 * 0.98)
    rad = (chord * chord / 4 + sag * sag) / (2 * sag)
    up = curve > 0
    y_end = h * 0.85 if up else h * 0.15 + 0
    y_end = h * 0.9 if up else h * 0.1
    top = y_end - sag if up else y_end + sag
    cy = top + rad if up else top - rad
    cx = w / 2
    a0 = math.atan2(y_end - cy, x0 - cx)
    a1 = math.atan2(y_end - cy, x1 - cx)
    # walk left to right over the top (up: angle grows) or along the bottom (bowl: angle shrinks)
    if up and a1 < a0:
        a1 += 2 * math.pi
    if not up and a1 > a0:
        a1 -= 2 * math.pi
    angles = [a0 + (a1 - a0) * i / STEPS for i in range(STEPS + 1)]
    pts = [QPointF(cx + rad * math.cos(a), cy + rad * math.sin(a)) for a in angles]
    svg = "M %.2f,%.2f A %.2f,%.2f 0 0 %d %.2f,%.2f" % (x0, y_end, rad, rad, 1 if up else 0, x1, y_end)
    return pts, svg, 0.5


def baseline_path(d):
    pts, _svg, centre = _geometry(d)
    path = QPainterPath(pts[0])
    for p in pts[1:]:
        path.lineTo(p)
    return path, centre


def _font(d, scale=1.0):
    f = QFont(d.get("font", "Sans Serif"))
    f.setPixelSize(max(int(round(int(d.get("size", 40)) * scale)), 1))
    f.setBold(bool(d.get("bold")))
    f.setItalic(bool(d.get("italic")))
    return f


def fit_scale(d, path_len):
    """Shrink the letters when the words are longer than the curve."""
    fm = QFontMetricsF(_font(d))
    total = sum(fm.horizontalAdvance(c) for c in d.get("text", ""))
    return min(1.0, (path_len * 0.98) / total) if total > 0 else 1.0


def placements(d):
    """[(char, x, y, angle in degrees, advance)] for every letter, plus the font used."""
    path, centre = baseline_path(d)
    length = path.length()
    text = d.get("text", "")
    scale = fit_scale(d, length)
    font = _font(d, scale)
    fm = QFontMetricsF(font)
    advs = [fm.horizontalAdvance(c) for c in text]
    total = sum(advs)
    pos = centre * length - total / 2
    out = []
    for c, a in zip(text, advs):
        mid = max(0.0, min(length, pos + a / 2))
        t = path.percentAtLength(mid)
        pt = path.pointAtPercent(t)
        out.append((c, pt.x(), pt.y(), path.angleAtPercent(t), a))
        pos += a
    return out, font


def paint(p, r, d):
    items, font = placements(d)
    fill = QColor(d.get("color", "#222222"))
    outline = d.get("stroke") or ""
    sw = float(d.get("sw", 0) or 0)
    p.save()
    p.translate(r.left(), r.top())
    p.setRenderHint(p.Antialiasing)
    for ch, x, y, ang, adv in items:
        if ch.isspace():
            continue
        g = QPainterPath()
        g.addText(-adv / 2, 0, font, ch)
        p.save()
        p.translate(x, y)
        p.rotate(-ang)
        p.fillPath(g, fill)
        if outline and sw > 0:
            p.strokePath(g, QPen(QColor(outline), sw))
        p.restore()
    p.restore()


def svg_html(d, css):
    """The object as an inline SVG block for the published page."""
    pts, svg_d, centre = _geometry(d)
    path, _c = baseline_path(d)
    scale = fit_scale(d, path.length())
    size = max(int(round(int(d.get("size", 40)) * scale)), 1)
    pid = "ap-" + str(d.get("id", "x"))
    fam = "'%s',sans-serif" % html.escape(d.get("font", "sans-serif"), quote=True)
    stroke = ""
    if d.get("stroke") and d.get("sw"):
        stroke = ' stroke="%s" stroke-width="%s" paint-order="stroke"' % (d["stroke"], d["sw"])
    return ('<div class="o" style="%s"><svg xmlns="http://www.w3.org/2000/svg" width="100%%" height="100%%" '
            'viewBox="0 0 %d %d" style="overflow:visible"><defs><path id="%s" d="%s"/></defs>'
            '<text font-family="%s" font-size="%d" font-weight="%s" font-style="%s" fill="%s"%s>'
            '<textPath href="#%s" startOffset="%d%%" text-anchor="middle">%s</textPath></text></svg></div>'
            % (css, d["w"], d["h"], pid, svg_d, fam, size, "bold" if d.get("bold") else "normal",
               "italic" if d.get("italic") else "normal", d.get("color", "#222222"), stroke, pid,
               round(centre * 100), html.escape(d.get("text", ""))))
