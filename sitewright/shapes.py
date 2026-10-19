"""Curved shapes: a path is a list of nodes. Each node is [x, y, in_x, in_y, out_x, out_y, smooth]
with every number between 0 and 1 across the object's box, so a shape scales with its frame.
A straight corner has both handles on the point itself."""
import math

from PyQt5.QtGui import QPainterPath

KAPPA = 0.5522847498


def node(x, y, ix=None, iy=None, ox=None, oy=None, smooth=False):
    return [x, y, x if ix is None else ix, y if iy is None else iy,
            x if ox is None else ox, y if oy is None else oy, bool(smooth)]


def is_corner(n):
    return n[2] == n[0] and n[3] == n[1] and n[4] == n[0] and n[5] == n[1]


def qpath(nodes, closed, w=1.0, h=1.0):
    path = QPainterPath()
    if not nodes:
        return path
    path.moveTo(nodes[0][0] * w, nodes[0][1] * h)
    pairs = list(zip(nodes, nodes[1:]))
    if closed and len(nodes) > 1:
        pairs.append((nodes[-1], nodes[0]))
    for a, b in pairs:
        if is_corner(a) and is_corner(b):
            path.lineTo(b[0] * w, b[1] * h)
        else:
            path.cubicTo(a[4] * w, a[5] * h, b[2] * w, b[3] * h, b[0] * w, b[1] * h)
    if closed:
        path.closeSubpath()
    return path


def _num(v):
    s = "%.4f" % v
    return s.rstrip("0").rstrip(".") if "." in s else s


def svg_d(nodes, closed, w=1.0, h=1.0):
    if not nodes:
        return ""
    out = ["M%s %s" % (_num(nodes[0][0] * w), _num(nodes[0][1] * h))]
    pairs = list(zip(nodes, nodes[1:]))
    if closed and len(nodes) > 1:
        pairs.append((nodes[-1], nodes[0]))
    for a, b in pairs:
        if is_corner(a) and is_corner(b):
            out.append("L%s %s" % (_num(b[0] * w), _num(b[1] * h)))
        else:
            out.append("C%s %s %s %s %s %s" % tuple(_num(v) for v in (
                a[4] * w, a[5] * h, b[2] * w, b[3] * h, b[0] * w, b[1] * h)))
    if closed:
        out.append("Z")
    return "".join(out)


def bounds(nodes, closed=True):
    r = qpath(nodes, closed).boundingRect()
    return r


def from_points(points, closed=True, handles=None):
    """Nodes (in the same units as the points) from a list of (x, y) or (x, y, ix, iy, ox, oy, smooth)."""
    out = []
    for p in points:
        out.append(node(*p) if len(p) != 7 else list(p))
    return out


def fit_to_box(nodes, closed, x, y):
    """Nodes in page pixels -> (x, y, w, h, normalised nodes) with the box hugging the shape."""
    r = qpath(nodes, closed).boundingRect()
    w, h = max(r.width(), 1.0), max(r.height(), 1.0)
    out = []
    for n in nodes:
        m = list(n)
        for i in (0, 2, 4):
            m[i] = (n[i] - r.left()) / w
        for i in (1, 3, 5):
            m[i] = (n[i] - r.top()) / h
        out.append(m)
    return r.left(), r.top(), w, h, out


def to_pixels(nodes, w, h):
    out = []
    for n in nodes:
        m = list(n)
        for i in (0, 2, 4):
            m[i] = n[i] * w
        for i in (1, 3, 5):
            m[i] = n[i] * h
        out.append(m)
    return out


def refit(d):
    """After a point moved: make the object's box hug the shape again, keeping it where it is on the page."""
    nodes = to_pixels(d["nodes"], d["w"], d["h"])
    left, top, w, h, norm = fit_to_box(nodes, d.get("closed", True), 0, 0)
    d["x"] = round(d["x"] + left, 2)
    d["y"] = round(d["y"] + top, 2)
    d["w"], d["h"] = round(w, 2), round(h, 2)
    d["nodes"] = norm


# -- ready-made shapes ------------------------------------------------------------------------------
def polygon(pts):
    return [node(x, y) for x, y in pts]


def ellipse():
    k = KAPPA / 2.0
    return [node(.5, 0, .5 - k, 0, .5 + k, 0, True), node(1, .5, 1, .5 - k, 1, .5 + k, True),
            node(.5, 1, .5 + k, 1, .5 - k, 1, True), node(0, .5, 0, .5 + k, 0, .5 - k, True)]


def rounded(r=0.2):
    """A box with rounded corners: each corner is two points joined by a curve."""
    k = r * (1 - KAPPA)
    return [node(r, 0, k, 0, r, 0), node(1 - r, 0, 1 - r, 0, 1 - k, 0),
            node(1, r, 1, k, 1, r), node(1, 1 - r, 1, 1 - r, 1, 1 - k),
            node(1 - r, 1, 1 - k, 1, 1 - r, 1), node(r, 1, r, 1, k, 1),
            node(0, 1 - r, 0, 1 - k, 0, 1 - r), node(0, r, 0, r, 0, k)]


def star(points=5, inner=0.4):
    pts = []
    for i in range(points * 2):
        ang = -math.pi / 2 + i * math.pi / points
        r = 0.5 if i % 2 == 0 else 0.5 * inner
        pts.append((0.5 + r * math.cos(ang), 0.5 + r * math.sin(ang)))
    return polygon(pts)


def regular(n, rot=-math.pi / 2):
    return polygon([(0.5 + 0.5 * math.cos(rot + i * 2 * math.pi / n),
                     0.5 + 0.5 * math.sin(rot + i * 2 * math.pi / n)) for i in range(n)])


def heart():
    # two lobes meeting at a point at the bottom
    return [node(.5, .28, .5, .28, .5, .12, True),
            node(.25, .0, .38, 0, .1, 0, True),
            node(0, .3, 0, .12, 0, .5, True),
            node(.5, 1.0),
            node(1, .3, 1, .5, 1, .12, True),
            node(.75, .0, .9, 0, .62, 0, True)]


PRESETS = {
    "rect": ("Rectangle", lambda: polygon([(0, 0), (1, 0), (1, 1), (0, 1)])),
    "rounded": ("Rounded rectangle", lambda: rounded(0.22)),
    "ellipse": ("Circle / oval", ellipse),
    "triangle": ("Triangle", lambda: polygon([(.5, 0), (1, 1), (0, 1)])),
    "diamond": ("Diamond", lambda: polygon([(.5, 0), (1, .5), (.5, 1), (0, .5)])),
    "pentagon": ("Pentagon", lambda: regular(5)),
    "hexagon": ("Hexagon", lambda: regular(6, 0)),
    "octagon": ("Octagon", lambda: regular(8, math.pi / 8)),
    "star": ("Star", lambda: star(5, 0.42)),
    "star4": ("Four-point star", lambda: star(4, 0.38)),
    "starburst": ("Starburst", lambda: star(12, 0.78)),
    "heart": ("Heart", heart),
    "arrow": ("Arrow", lambda: polygon([(0, .3), (.6, .3), (.6, 0), (1, .5), (.6, 1), (.6, .7), (0, .7)])),
    "cross": ("Cross", lambda: polygon([(.33, 0), (.67, 0), (.67, .33), (1, .33), (1, .67), (.67, .67),
                                          (.67, 1), (.33, 1), (.33, .67), (0, .67), (0, .33), (.33, .33)])),
    "speech": ("Speech bubble", lambda: polygon([(0, 0), (1, 0), (1, .75), (.45, .75), (.2, 1), (.25, .75), (0, .75)])),
    "ribbon": ("Banner", lambda: polygon([(0, .15), (.12, .15), (.12, 0), (.88, 0), (.88, .15), (1, .15),
                                          (.92, .5), (1, .85), (.88, .85), (.88, 1), (.12, 1), (.12, .85),
                                          (0, .85), (.08, .5)])),
    "chevron": ("Chevron", lambda: polygon([(0, 0), (.6, 0), (1, .5), (.6, 1), (0, 1), (.4, .5)])),
}


def preset_nodes(name):
    f = PRESETS.get(name)
    return f[1]() if f else PRESETS["rect"][1]()


def shape_nodes(spec):
    """Nodes and closed-flag for a crop/shape spec: a preset name, or {"nodes": [...], "closed": bool}."""
    if isinstance(spec, dict) and spec.get("nodes"):
        return spec["nodes"], spec.get("closed", True)
    return preset_nodes(spec if isinstance(spec, str) else "rect"), True


def hit_segment(nodes, closed, w, h, pt, tol=6.0):
    """Index of the node a new point would follow when the path is clicked at pt (pixels), or -1."""
    best, which = tol, -1
    pairs = list(zip(range(len(nodes)), range(1, len(nodes))))
    if closed and len(nodes) > 1:
        pairs.append((len(nodes) - 1, 0))
    for i, j in pairs:
        seg = qpath([nodes[i], nodes[j]], False, w, h)
        for k in range(0, 41):
            q = seg.pointAtPercent(k / 40.0)
            dist = math.hypot(q.x() - pt.x(), q.y() - pt.y())
            if dist < best:
                best, which = dist, i
    return which


def insert_node(nodes, closed, after, w, h, pt):
    """Add a corner point after node index `after` at pixel point pt."""
    n = node(pt.x() / w, pt.y() / h)
    nodes.insert(after + 1, n)
    return after + 1
