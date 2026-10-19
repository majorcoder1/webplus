"""Picture effects: a transparent colour, a watermark written into the picture, and filter effects
(blur, glow, colour changes). The editor shows them with Pillow; the published page gets the same
filters as CSS, and pictures with a transparent colour or a watermark are written out as new files."""
import json
import math

from PyQt5.QtCore import QBuffer, QByteArray, QIODevice, QPointF, Qt
from PyQt5.QtGui import QColor, QFont, QFontMetricsF, QImage, QPainter

FX_DEFAULT = dict(blur=0, brightness=100, contrast=100, grayscale=0, sepia=0, hue=0, saturate=100,
                  invert=0, glow=0, glow_color="#ffd34a")
WM_DEFAULT = dict(text="© %year% %sitename%", pos="bottom-right", size=5, color="#ffffff",
                  opacity=70, shadow=True)
TR_DEFAULT = dict(color="#ffffff", tol=12, soft=6)
POSITIONS = [("bottom-right", "Bottom right"), ("bottom-left", "Bottom left"), ("top-right", "Top right"),
             ("top-left", "Top left"), ("center", "Centre"), ("tile", "Tiled across the picture")]
NO_DERIVE = (".gif", ".svg")


def have_pil():
    try:
        import PIL  # noqa: F401
        return True
    except ImportError:
        return False


# -- filter effects (settings -> CSS, and -> pixels) ----------------------------------------
def fx_values(fx):
    out = dict(FX_DEFAULT)
    out.update({k: v for k, v in (fx or {}).items() if k in FX_DEFAULT})
    return out


def fx_active(fx):
    v = fx_values(fx)
    return any(v[k] != FX_DEFAULT[k] for k in FX_DEFAULT if k != "glow_color")


def css_filter(fx):
    """The CSS 'filter' value for these settings ('' when nothing is changed)."""
    v = fx_values(fx)
    parts = []
    if v["blur"]:
        parts.append("blur(%gpx)" % v["blur"])
    if v["brightness"] != 100:
        parts.append("brightness(%g)" % (v["brightness"] / 100.0))
    if v["contrast"] != 100:
        parts.append("contrast(%g)" % (v["contrast"] / 100.0))
    if v["grayscale"]:
        parts.append("grayscale(%g)" % (v["grayscale"] / 100.0))
    if v["sepia"]:
        parts.append("sepia(%g)" % (v["sepia"] / 100.0))
    if v["hue"]:
        parts.append("hue-rotate(%gdeg)" % v["hue"])
    if v["saturate"] != 100:
        parts.append("saturate(%g)" % (v["saturate"] / 100.0))
    if v["invert"]:
        parts.append("invert(%g)" % (v["invert"] / 100.0))
    if v["glow"]:
        parts.append("drop-shadow(0 0 %gpx %s)" % (v["glow"], v["glow_color"]))
    return " ".join(parts)


def pad_for(fx):
    """Extra room around an object so a blur or glow is not cut off."""
    v = fx_values(fx)
    return int(math.ceil(v["blur"] * 3 + v["glow"] * 1.5 + 2)) if fx_active(fx) else 0


# -- QImage <-> Pillow ------------------------------------------------------------------------
def to_pil(img):
    from PIL import Image
    img = img.convertToFormat(QImage.Format_RGBA8888)
    ptr = img.constBits()
    ptr.setsize(img.byteCount())
    return Image.frombuffer("RGBA", (img.width(), img.height()), bytes(ptr), "raw", "RGBA", img.bytesPerLine(), 1)


def to_qimage(pil):
    pil = pil.convert("RGBA")
    data = pil.tobytes("raw", "RGBA")
    return QImage(data, pil.width, pil.height, 4 * pil.width, QImage.Format_RGBA8888).copy()


def png_bytes(img):
    ba = QByteArray()
    buf = QBuffer(ba)
    buf.open(QIODevice.WriteOnly)
    img.save(buf, "PNG")
    return bytes(ba)


def apply_fx(pil, fx):
    """The filter effects applied to a Pillow RGBA picture, in the same order as the CSS."""
    from PIL import Image, ImageEnhance, ImageFilter, ImageOps
    v = fx_values(fx)
    pil = pil.convert("RGBA")
    if v["blur"]:
        pil = pil.convert("RGBa").filter(ImageFilter.GaussianBlur(v["blur"])).convert("RGBA")   # premultiplied: no dark rim
    r, g, b, a = pil.split()
    rgb = Image.merge("RGB", (r, g, b))
    if v["brightness"] != 100:
        rgb = ImageEnhance.Brightness(rgb).enhance(v["brightness"] / 100.0)
    if v["contrast"] != 100:
        rgb = ImageEnhance.Contrast(rgb).enhance(v["contrast"] / 100.0)
    if v["grayscale"]:
        gray = rgb.convert("L").convert("RGB")
        rgb = Image.blend(rgb, gray, min(v["grayscale"], 100) / 100.0)
    if v["sepia"]:
        sep = rgb.convert("RGB", (0.393, 0.769, 0.189, 0, 0.349, 0.686, 0.168, 0, 0.272, 0.534, 0.131, 0))
        rgb = Image.blend(rgb, sep, min(v["sepia"], 100) / 100.0)
    if v["hue"]:
        h, s, val = rgb.convert("HSV").split()
        shift = int(round(v["hue"] * 255 / 360.0))
        h = h.point(lambda x: (x + shift) % 256)
        rgb = Image.merge("HSV", (h, s, val)).convert("RGB")
    if v["saturate"] != 100:
        rgb = ImageEnhance.Color(rgb).enhance(v["saturate"] / 100.0)
    if v["invert"]:
        rgb = Image.blend(rgb, ImageOps.invert(rgb), min(v["invert"], 100) / 100.0)
    out = Image.merge("RGBA", (*rgb.split(), a))
    if v["glow"]:
        col = QColor(v["glow_color"])
        glow_a = a.filter(ImageFilter.GaussianBlur(v["glow"] / 2.0)).point(lambda x: min(255, int(x * 1.6)))
        glow = Image.new("RGBA", out.size, (col.red(), col.green(), col.blue(), 0))
        glow.putalpha(glow_a)
        out = Image.alpha_composite(glow, out)
    return out


def render_with_fx(draw, w, h, fx, scale=1.0):
    """Draw something with draw(painter) onto a transparent picture w x h (plus room for the
    effect), apply the effects, and return (QImage, pad)."""
    pad = pad_for(fx)
    img = QImage(int(math.ceil((w + 2 * pad) * scale)), int(math.ceil((h + 2 * pad) * scale)), QImage.Format_RGBA8888)
    img.fill(Qt.transparent)
    p = QPainter(img)
    p.setRenderHint(QPainter.Antialiasing)
    p.setRenderHint(QPainter.SmoothPixmapTransform)
    p.scale(scale, scale)
    p.translate(pad, pad)
    draw(p)
    p.end()
    if not have_pil():
        return img, pad
    return to_qimage(apply_fx(to_pil(img), fx)), pad


# -- transparent colour -----------------------------------------------------------------------
def colour_key(pil, colour, tol, soft):
    """Make every pixel close to `colour` transparent. tol and soft are percentages."""
    from PIL import Image, ImageChops
    c = QColor(colour)
    pil = pil.convert("RGBA")
    r, g, b, a = pil.split()
    key = Image.new("RGB", pil.size, (c.red(), c.green(), c.blue()))
    diff = ImageChops.difference(Image.merge("RGB", (r, g, b)), key)
    dr, dg, db = diff.split()
    far = ImageChops.lighter(ImageChops.lighter(dr, dg), db)       # the biggest difference in any colour
    t = int(round(tol * 2.55))
    width = max(int(round(soft * 2.55)), 1)
    ramp = far.point(lambda v: 0 if v <= t else min(255, int((v - t) * 255 / width)))
    return Image.merge("RGBA", (r, g, b, ImageChops.multiply(a, ramp)))


# -- watermark --------------------------------------------------------------------------------
def wm_values(wm):
    out = dict(WM_DEFAULT)
    out.update({k: v for k, v in (wm or {}).items() if k in WM_DEFAULT})
    return out


def draw_watermark(img, wm, text):
    """Write the watermark text into a QImage (in place)."""
    v = wm_values(wm)
    if not text.strip():
        return img
    p = QPainter(img)
    p.setRenderHint(QPainter.Antialiasing)
    f = QFont("Sans Serif")
    f.setPixelSize(max(int(img.width() * v["size"] / 100.0), 6))
    f.setBold(True)
    p.setFont(f)
    fm = QFontMetricsF(f)
    tw, th = fm.horizontalAdvance(text), fm.height()
    margin = img.width() * 0.02
    col = QColor(v["color"])
    col.setAlpha(int(255 * max(0, min(100, v["opacity"])) / 100.0))
    shadow = QColor(0, 0, 0, int(col.alpha() * 0.6))

    def put(x, y):
        if v["shadow"]:
            p.setPen(shadow)
            p.drawText(QPointF(x + 1.5, y + fm.ascent() + 1.5), text)
        p.setPen(col)
        p.drawText(QPointF(x, y + fm.ascent()), text)

    pos = v["pos"]
    if pos == "tile":
        step_x, step_y = tw + margin * 4, th * 3
        y, row = 0.0, 0
        while y < img.height():
            x = -(tw / 2.0) if row % 2 else 0.0
            while x < img.width():
                p.save()
                p.translate(x, y)
                p.rotate(-20)
                put(0, 0)
                p.restore()
                x += step_x
            y += step_y
            row += 1
    else:
        x = {"left": margin, "right": img.width() - tw - margin}.get(pos.split("-")[-1], (img.width() - tw) / 2.0)
        if pos == "center":
            x = (img.width() - tw) / 2.0
        y = {"top": margin, "bottom": img.height() - th - margin}.get(pos.split("-")[0], (img.height() - th) / 2.0)
        put(x, y)
    p.end()
    return img


# -- the whole picture pipeline ---------------------------------------------------------------
def is_derived(doc, d):
    """Does this picture object need its own processed file?"""
    a = doc.assets.get(d.get("asset"))
    return bool(a) and not a["name"].lower().endswith(NO_DERIVE) and bool(d.get("transp") or d.get("watermark"))


def derive(doc, d, tokens=None, max_w=0):
    """The picture of an image object with its transparent colour and watermark: a QImage (or None)."""
    raw = doc.asset_bytes(d.get("asset"))
    img = QImage()
    if not raw or not img.loadFromData(raw):
        return None
    img = img.convertToFormat(QImage.Format_RGBA8888)
    if max_w and img.width() > max_w:
        img = img.scaledToWidth(max_w, Qt.SmoothTransformation).convertToFormat(QImage.Format_RGBA8888)
    if d.get("transp") and have_pil():
        t = dict(TR_DEFAULT, **d["transp"])
        img = to_qimage(colour_key(to_pil(img), t["color"], t["tol"], t["soft"]))
    if d.get("watermark"):
        from . import export
        text = export.replace_tokens(wm_values(d["watermark"])["text"], tokens or {})
        img = draw_watermark(img, d["watermark"], text)
    return img


def cache_key(doc, d, max_w):
    return json.dumps([d.get("asset"), d.get("transp"), d.get("watermark"), max_w,
                       doc.site_title], sort_keys=True, default=str)


def export_width(d):
    """The widest the published copy needs to be: twice the frame, for sharp screens, but never huge."""
    return int(min(max(d.get("w", 0), 1) * 2 + 1, 3000))
