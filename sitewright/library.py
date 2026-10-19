"""The bundled picture library: Tabler icons, ambientCG and Poly Haven textures, Hero Patterns.
Credits and licences are in library/CREDITS.md."""
import json
import os

from PyQt5.QtCore import Qt
from PyQt5.QtGui import QColor, QImage, QPainter

ROOT = os.path.join(os.path.dirname(__file__), "library")

_cache = {}


def _json(name):
    if name not in _cache:
        try:
            with open(os.path.join(ROOT, name), encoding="utf-8") as f:
                _cache[name] = json.load(f)
        except (OSError, ValueError):
            _cache[name] = {}
    return _cache[name]


def icon_names(query=""):
    """Icon names matching the words in query (name, category or tags)."""
    idx = _json("icons.json")
    words = query.lower().split()
    out = []
    for name, (cat, tags) in idx.items():
        hay = (name.replace("-", " ") + " " + cat + " " + tags).lower()
        if all(w in hay for w in words):
            out.append(name)
    return sorted(out)


def icon_category(name):
    return (_json("icons.json").get(name) or ["", ""])[0]


def textures():
    """[(id, shown name, source)] sorted by name."""
    t = _json("textures.json")
    return sorted(((k, v["name"], v["source"]) for k, v in t.items()), key=lambda x: x[1])


def patterns():
    return list(_json("patterns.json") or [])


def path_for(group, key):
    sub = {"icon": "icons", "pattern": "patterns", "texture": "textures"}[group]
    ext = "jpg" if group == "texture" else "png"
    return os.path.join(ROOT, sub, key + "." + ext)


def tinted(path, ink, bg=None):
    """A black-on-clear picture (icon or pattern) recoloured; bg fills behind it if given."""
    src = QImage(path).convertToFormat(QImage.Format_ARGB32)
    out = QImage(src.size(), QImage.Format_ARGB32)
    out.fill(QColor(bg) if bg else Qt.transparent)
    mask = QImage(src.size(), QImage.Format_ARGB32)
    mask.fill(Qt.transparent)
    p = QPainter(mask)
    p.drawImage(0, 0, src)
    p.setCompositionMode(QPainter.CompositionMode_SourceIn)
    p.fillRect(mask.rect(), QColor(ink))
    p.end()
    p = QPainter(out)
    p.drawImage(0, 0, mask)
    p.end()
    return out


def png_bytes(img):
    from PyQt5.QtCore import QBuffer, QByteArray, QIODevice
    ba = QByteArray()
    buf = QBuffer(ba)
    buf.open(QIODevice.WriteOnly)
    img.save(buf, "PNG")
    return bytes(ba)
