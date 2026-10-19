"""Colour schemes (12 colours), site themes, and recolouring a whole site.

A scheme is a list of 12 colours. Applying one swaps every colour in the site
that equals a colour of the old scheme for the matching colour of the new one,
so colours you picked yourself are left alone.
"""
from .model import DEFAULT_SCHEME
from .styles import NAV_STYLES, button_style

SCHEME_SIZE = 12
SCHEME_LABELS = ["Background", "Text", "Dark", "Main", "Accent", "Light accent",
                 "Success", "Alert", "Highlight", "Muted", "Border", "Panel"]


SCHEMES = {
    "Default": DEFAULT_SCHEME,
    "Ocean": ["#ffffff", "#17324d", "#0b3c5d", "#1d70a2", "#f2a541", "#5aa9d6",
              "#2e9e83", "#d9534f", "#6c63c7", "#4f6b7f", "#a8bccb", "#eaf3f9"],
    "Forest": ["#fbfdf9", "#1e2d1f", "#1f4d2c", "#3a8d4f", "#d99a2b", "#7cc08c",
               "#2f8f6b", "#c0452f", "#7b5ea7", "#5a6b5c", "#b4c4b6", "#edf5ec"],
    "Sunset": ["#fffaf5", "#33211a", "#6b2d1f", "#e0572f", "#f2b138", "#f08a5d",
               "#4f9d69", "#b3203c", "#8e4fa3", "#7a5f55", "#d6bfb2", "#fdeee2"],
    "Slate": ["#ffffff", "#1c2128", "#2b323b", "#4b6b8a", "#c98a2e", "#8aa4bf",
              "#4a8f6a", "#b8453d", "#6b6bb5", "#5d6672", "#b9c0c8", "#f0f2f5"],
    "Berry": ["#fffafd", "#2a1a2a", "#4a1d49", "#a02c7c", "#e8a33d", "#d27fb5",
              "#3e9a82", "#c43a4b", "#6a4fb0", "#76607a", "#d5bfd3", "#f8ecf6"],
    "Sand": ["#fffdf8", "#2f2a22", "#5b4a2f", "#b0793a", "#3f7f87", "#d9b98a",
             "#6a9a4c", "#b5502f", "#7d6aa8", "#80745f", "#d8ccb4", "#f6efe0"],
    "Midnight": ["#12151c", "#e9edf3", "#0a0c11", "#4c8dff", "#ffb347", "#2a3550",
                 "#43c59e", "#ff6b6b", "#9d7bff", "#8a94a6", "#2c3342", "#1a1f2a"],
}

# fonts chosen to exist on most computers and to fall back sensibly on the web
THEMES = {
    "Ocean": dict(scheme="Ocean", heading="Georgia", body="Verdana",
                  button="flat", nav="Classic bar"),
    "Forest": dict(scheme="Forest", heading="Trebuchet MS", body="Verdana",
                   button="gradient", nav="Green bar"),
    "Sunset": dict(scheme="Sunset", heading="Georgia", body="Arial",
                   button="pill", nav="Warm pills"),
    "Slate": dict(scheme="Slate", heading="Arial", body="Arial",
                  button="outline", nav="Light underline"),
    "Berry": dict(scheme="Berry", heading="Palatino Linotype", body="Trebuchet MS",
                  button="raised", nav="Pills"),
    "Midnight": dict(scheme="Midnight", heading="Trebuchet MS", body="Verdana",
                     button="flat", nav="Dark underline"),
}

COLOR_KEYS = ("fill", "fill2", "stroke", "color", "hfill", "hcolor", "pfill",
              "ifill", "ihover", "active", "acolor", "uline", "hover")


def _all_items(doc):
    for p in doc.pages:
        yield from p["items"]
    for lst in doc.all_master_lists():
        yield from lst


def recolor(doc, old, new):
    """Swap every colour equal to old[i] for new[i], across the whole site."""
    m = {}
    for o, n in zip(old, new):
        m.setdefault(o.lower(), n)
    for it in _all_items(doc):
        for k in COLOR_KEYS:
            v = it.get(k)
            if isinstance(v, str) and v.lower() in m:
                it[k] = m[v.lower()]
    for p in doc.pages:
        v = p.get("bg", "")
        if v.lower() in m:
            p["bg"] = m[v.lower()]


def apply_scheme(doc, new):
    recolor(doc, doc.scheme, new)
    doc.scheme = list(new)


def apply_theme(doc, name):
    t = THEMES[name]
    new = SCHEMES[t["scheme"]]
    apply_scheme(doc, new)
    for p in doc.pages:
        p["bg"] = new[0]
    for it in _all_items(doc):
        k = it["kind"]
        if k in ("text", "button", "navbar", "table", "field", "marquee", "arttext"):
            heading = k == "text" and it.get("size", 0) >= 26
            it["font"] = t["heading"] if heading else t["body"]
        if k == "text" and it.get("color", "").lower() in ("#222222", new[1].lower()):
            it["color"] = new[1]
        if k == "button":
            it.update(button_style(new[3], t["button"]))
        if k == "navbar":
            it.update(NAV_STYLES[t["nav"]])
            it["fill"] = new[2] if NAV_STYLES[t["nav"]].get("fill") else ""
            it["active"] = new[3] if NAV_STYLES[t["nav"]].get("active") else ""
            it["ihover"] = new[3] if NAV_STYLES[t["nav"]].get("ihover") else ""
            if NAV_STYLES[t["nav"]].get("uline"):
                it["uline"] = new[4]
    return new


def preview_theme(name, w=320, h=78):
    """A small picture of a theme: its 12 colours, fonts and a button."""
    from PyQt5.QtCore import QRectF, Qt
    from PyQt5.QtGui import QColor, QFont, QPainter, QPixmap
    from .styles import paint_button
    t = THEMES[name]
    sc = SCHEMES[t["scheme"]]
    pm = QPixmap(w, h)
    pm.fill(QColor(sc[0]))
    p = QPainter(pm)
    p.setRenderHint(QPainter.Antialiasing)
    for i, c in enumerate(sc):
        p.fillRect(QRectF(8 + i * 14, h - 18, 14, 10), QColor(c))
    f = QFont(t["heading"])
    f.setPixelSize(20)
    f.setBold(True)
    p.setFont(f)
    p.setPen(QColor(sc[1]))
    p.drawText(QRectF(8, 4, w - 140, 30), int(Qt.AlignVCenter | Qt.AlignLeft), name)
    f2 = QFont(t["body"])
    f2.setPixelSize(12)
    p.setFont(f2)
    p.drawText(QRectF(8, 34, w - 140, 20), int(Qt.AlignVCenter | Qt.AlignLeft),
               "Body text sample")
    d = dict(font=t["body"], size=13, italic=False, align="center", text="Button")
    d.update(button_style(sc[3], t["button"]))
    paint_button(p, QRectF(w - 120, 12, 108, 34), d)
    p.end()
    return pm
